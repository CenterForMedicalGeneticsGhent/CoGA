"""Object-storage abstraction: local filesystem (dev) or a cloud object store
(production) — AWS S3 or Google Cloud Storage.

Controlled by ``STORAGE_BACKEND`` (``local`` by default, ``s3``, or ``gcs``). In a
remote mode the raw family data lives in a bucket and is read two ways:

- IGV alignments (CRAM/BAM + indexes) are served as short-lived **presigned/signed
  URLs** so the browser fetches bytes directly from the store (native HTTP range
  support).
- Family-package sources are **staged** to a temp directory for an import job, so
  the existing path-based import logic runs unchanged, then cleaned up.

Object keys mirror the local layout (``<family_id>/<file>``) under the optional
``STORAGE_PREFIX`` (``S3_PREFIX`` / ``GCS_PREFIX``). Remote URIs use the store's
native scheme: ``s3://`` or ``gs://``.

Credentials:

- **S3** — the standard AWS chain (env vars / instance role).
- **GCS** — Application Default Credentials (Workload Identity on Cloud Run). Signed
  URLs are produced with IAM ``SignBlob`` so **no private key** is needed; the
  runtime service account must have ``roles/iam.serviceAccountTokenCreator`` on
  itself and the IAM Credentials API (``iamcredentials.googleapis.com``) enabled.

The cloud SDKs (``boto3`` / ``google-cloud-storage``) are imported lazily so a
deployment need not install whichever backend it does not use.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from .config import settings

# Worker threads used to download objects under a prefix concurrently. Package
# staging is dominated by per-object latency, so a small pool gives a large speedup
# without overwhelming the client connection pool.
_DOWNLOAD_PREFIX_MAX_WORKERS = 12

# Remote URI schemes understood by the package-import path.
_REMOTE_SCHEMES = ("s3", "gs")

# Manifest filenames that mark a folder as an importable family package.
_MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "manifest.json")


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def storage_backend() -> str:
    return settings.storage_backend


def storage_is_remote() -> bool:
    """True when a cloud object store (S3 or GCS) backs raw family data."""
    return settings.storage_backend in ("s3", "gcs")


def storage_is_s3() -> bool:
    return settings.storage_backend == "s3"


def storage_is_gcs() -> bool:
    return settings.storage_backend == "gcs"


# ---------------------------------------------------------------------------
# Scheme-agnostic remote URI helpers (s3:// or gs://)
# ---------------------------------------------------------------------------

def is_remote_uri(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return any(lowered.startswith(f"{scheme}://") for scheme in _REMOTE_SCHEMES)


@dataclass(frozen=True)
class RemoteLocation:
    scheme: str
    bucket: str
    key: str

    @property
    def uri(self) -> str:
        return f"{self.scheme}://{self.bucket}/{self.key}" if self.key else f"{self.scheme}://{self.bucket}"


def parse_remote_uri(uri: str) -> RemoteLocation:
    parsed = urlparse(str(uri))
    if parsed.scheme not in _REMOTE_SCHEMES or not parsed.netloc:
        raise ValueError(f"Not a remote object-store URI (s3:// or gs://): {uri!r}")
    return RemoteLocation(scheme=parsed.scheme, bucket=parsed.netloc, key=parsed.path.lstrip("/"))


def join_remote_uri(base: str, *parts: str) -> str:
    """Append path segments to a remote URI (collapsing slashes), preserving scheme."""
    location = parse_remote_uri(base)
    extra = [str(part).strip("/") for part in parts if str(part).strip("/")]
    key = "/".join(segment for segment in [location.key.strip("/"), *extra] if segment)
    return RemoteLocation(location.scheme, location.bucket, key).uri


# ---------------------------------------------------------------------------
# Bucket / key resolution for the configured backend
# ---------------------------------------------------------------------------

def _configured_bucket() -> str:
    if storage_is_gcs():
        if not settings.gcs_bucket:
            raise RuntimeError("STORAGE_BACKEND=gcs but GCS_BUCKET is not configured")
        return settings.gcs_bucket
    if not settings.s3_bucket:
        raise RuntimeError("STORAGE_BACKEND=s3 but S3_BUCKET is not configured")
    return settings.s3_bucket


def _configured_prefix() -> str:
    return (settings.gcs_prefix if storage_is_gcs() else settings.s3_prefix) or ""


def object_key(*parts: str) -> str:
    """Key within the configured bucket, under the optional storage prefix."""
    prefix = _configured_prefix().strip("/")
    segments = [prefix, *[str(part).strip("/") for part in parts if str(part).strip("/")]]
    return "/".join(segment for segment in segments if segment)


# ---------------------------------------------------------------------------
# Clients (lazy)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _s3_client():
    import boto3  # lazy: only needed in s3 mode
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=settings.s3_region or None,
        endpoint_url=settings.s3_endpoint_url or None,
        config=Config(
            signature_version="s3v4",
            connect_timeout=settings.s3_connect_timeout_seconds,
            read_timeout=settings.s3_read_timeout_seconds,
            # Adaptive mode adds client-side throttling-aware backoff on top of retries,
            # so a slow/throttling object store fails fast and bounded instead of hanging.
            retries={"mode": "adaptive", "max_attempts": settings.s3_max_attempts},
        ),
    )


@lru_cache(maxsize=1)
def _gcs_client():
    from google.cloud import storage  # lazy: only needed in gcs mode

    return storage.Client()


# ---------------------------------------------------------------------------
# Object existence
# ---------------------------------------------------------------------------

def object_exists(key: str) -> bool:
    if storage_is_gcs():
        return _gcs_client().bucket(_configured_bucket()).blob(key).exists()

    from botocore.exceptions import ClientError

    try:
        _s3_client().head_object(Bucket=_configured_bucket(), Key=key)
        return True
    except ClientError:
        return False


# ---------------------------------------------------------------------------
# Presigned / signed download URLs
# ---------------------------------------------------------------------------

def presigned_get_url(key: str, *, filename: str | None = None, expires: int | None = None) -> str:
    expires_in = expires or settings.s3_presign_expiry_seconds
    if storage_is_gcs():
        return _gcs_signed_get_url(key, filename=filename, expires=expires_in)

    params: dict[str, str] = {"Bucket": _configured_bucket(), "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'inline; filename="{filename}"'
    return _s3_client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )


def _gcs_signing_credentials() -> tuple[str, str]:
    """Return ``(service_account_email, access_token)`` for IAM-based V4 signing.

    Under Workload Identity there is no private key on disk, so signed URLs are
    produced via the IAM ``signBlob`` API. The signer is the active ADC service
    account, which must hold ``roles/iam.serviceAccountTokenCreator`` on itself.
    """
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    email = getattr(credentials, "service_account_email", None) or getattr(
        credentials, "signer_email", None
    )
    if not email or not getattr(credentials, "token", None):
        raise RuntimeError(
            "Cannot determine a signing service account for GCS signed URLs. The "
            "runtime needs an attached service account with "
            "roles/iam.serviceAccountTokenCreator on itself and the IAM Credentials "
            "API enabled."
        )
    return email, credentials.token


def _gcs_signed_get_url(key: str, *, filename: str | None, expires: int) -> str:
    blob = _gcs_client().bucket(_configured_bucket()).blob(key)
    disposition = f'inline; filename="{filename}"' if filename else None
    signer_email, access_token = _gcs_signing_credentials()
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expires),
        method="GET",
        response_disposition=disposition,
        service_account_email=signer_email,
        access_token=access_token,
    )


# ---------------------------------------------------------------------------
# Prefix download (package staging)
# ---------------------------------------------------------------------------

def download_prefix(uri: str, dest_dir: Path) -> int:
    """Download every object under a remote prefix into ``dest_dir`` preserving the
    relative key layout. Returns the number of files written. Blocking — call from a
    worker thread in async contexts."""
    location = parse_remote_uri(uri)
    if location.scheme == "gs":
        return _gcs_download_prefix(location, dest_dir)
    return _s3_download_prefix(location, dest_dir)


def _plan_downloads(base_key: str, names: list[str], dest_dir: Path) -> list[tuple[str, str]]:
    """Map remote object names under ``base_key`` to local targets, creating parent
    dirs single-threaded (avoids mkdir races) before the concurrent transfer."""
    base = base_key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    downloads: list[tuple[str, str]] = []
    for name in names:
        if name.endswith("/"):
            continue
        relative = name[len(base_prefix):] if base_prefix and name.startswith(base_prefix) else name
        if not relative:
            continue
        target = dest_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        downloads.append((name, str(target)))
    return downloads


def _s3_download_prefix(location: RemoteLocation, dest_dir: Path) -> int:
    client = _s3_client()
    base = location.key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    paginator = client.get_paginator("list_objects_v2")

    names: list[str] = []
    for page in paginator.paginate(Bucket=location.bucket, Prefix=base_prefix):
        for obj in page.get("Contents", []):
            names.append(obj["Key"])

    downloads = _plan_downloads(location.key, names, dest_dir)
    if not downloads:
        return 0

    def _download(item: tuple[str, str]) -> None:
        key, target = item
        client.download_file(location.bucket, key, target)

    max_workers = min(_DOWNLOAD_PREFIX_MAX_WORKERS, len(downloads))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # Consume the iterator so any download error propagates (as it did serially).
        for _ in pool.map(_download, downloads):
            pass
    return len(downloads)


def _gcs_download_prefix(location: RemoteLocation, dest_dir: Path) -> int:
    client = _gcs_client()
    base = location.key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    blobs = list(client.list_blobs(location.bucket, prefix=base_prefix))
    by_name = {blob.name: blob for blob in blobs}

    downloads = _plan_downloads(location.key, list(by_name), dest_dir)
    if not downloads:
        return 0

    def _download(item: tuple[str, str]) -> None:
        name, target = item
        by_name[name].download_to_filename(target)

    max_workers = min(_DOWNLOAD_PREFIX_MAX_WORKERS, len(downloads))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for _ in pool.map(_download, downloads):
            pass
    return len(downloads)


# ---------------------------------------------------------------------------
# Package discovery under a remote root
# ---------------------------------------------------------------------------

def _is_package_leaf_set(leaf_names: list[str]) -> tuple[bool, bool]:
    has_manifest = any(leaf in _MANIFEST_NAMES for leaf in leaf_names)
    has_ped = any(leaf.endswith(".ped") for leaf in leaf_names)
    return has_manifest, has_ped


def list_remote_package_candidates(root_uri: str) -> list[dict[str, object]]:
    """List immediate sub-prefixes under a remote root that look like family
    packages (contain a manifest or a ``*.ped``).

    Returns dicts with ``name``, ``uri`` (the remote folder), ``has_manifest`` and
    ``has_ped``. Blocking — call from a worker thread in async contexts."""
    location = parse_remote_uri(root_uri)
    if location.scheme == "gs":
        return _gcs_list_package_candidates(root_uri, location)
    return _s3_list_package_candidates(root_uri, location)


def _s3_list_package_candidates(root_uri: str, location: RemoteLocation) -> list[dict[str, object]]:
    base = location.key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    client = _s3_client()
    listing = client.list_objects_v2(
        Bucket=location.bucket, Prefix=base_prefix, Delimiter="/"
    )
    candidates: list[dict[str, object]] = []
    for entry in listing.get("CommonPrefixes", []):
        child_prefix = str(entry.get("Prefix", ""))
        name = child_prefix[len(base_prefix):].strip("/")
        if not name:
            continue
        child = client.list_objects_v2(Bucket=location.bucket, Prefix=child_prefix)
        leaf_names = [
            str(obj.get("Key", "")).rsplit("/", 1)[-1] for obj in child.get("Contents", [])
        ]
        has_manifest, has_ped = _is_package_leaf_set(leaf_names)
        if not has_manifest and not has_ped:
            continue
        candidates.append(
            {
                "name": name,
                "uri": join_remote_uri(root_uri, name),
                "has_manifest": has_manifest,
                "has_ped": has_ped,
            }
        )
    return candidates


def _gcs_list_package_candidates(root_uri: str, location: RemoteLocation) -> list[dict[str, object]]:
    client = _gcs_client()
    base = location.key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    iterator = client.list_blobs(location.bucket, prefix=base_prefix, delimiter="/")
    # Consuming the page iterator populates ``prefixes`` (the common sub-folders).
    for _ in iterator:
        pass
    candidates: list[dict[str, object]] = []
    for child_prefix in sorted(iterator.prefixes):
        name = child_prefix[len(base_prefix):].strip("/")
        if not name:
            continue
        child_blobs = client.list_blobs(location.bucket, prefix=child_prefix)
        leaf_names = [blob.name.rsplit("/", 1)[-1] for blob in child_blobs]
        has_manifest, has_ped = _is_package_leaf_set(leaf_names)
        if not has_manifest and not has_ped:
            continue
        candidates.append(
            {
                "name": name,
                "uri": join_remote_uri(root_uri, name),
                "has_manifest": has_manifest,
                "has_ped": has_ped,
            }
        )
    return candidates


# ---------------------------------------------------------------------------
# Deprecated S3-named aliases (kept for backward compatibility). New code should
# use the scheme-neutral names above.
# ---------------------------------------------------------------------------

is_s3_uri = is_remote_uri
parse_s3_uri = parse_remote_uri
join_s3_uri = join_remote_uri
list_s3_package_candidates = list_remote_package_candidates
S3Location = RemoteLocation
