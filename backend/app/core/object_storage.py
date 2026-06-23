"""Object-storage abstraction: local filesystem (dev) or AWS S3 (production).

Controlled by ``STORAGE_BACKEND`` (``local`` by default, or ``s3``). In s3 mode the
raw family data lives in an S3 bucket and is read two ways:

- IGV alignments (CRAM/BAM + indexes) are served as short-lived **presigned URLs**
  so the browser fetches bytes directly from S3 (native HTTP range support).
- Family-package sources are **staged** to a temp directory for an import job, so
  the existing path-based import logic runs unchanged, then cleaned up.

Object keys mirror the local layout (``<family_id>/<file>``) under the optional
``S3_PREFIX``. Credentials come from the standard AWS chain (env vars / instance
role); ``boto3`` is imported lazily so local-mode deployments need not install it.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from .config import settings

# Worker threads used to download objects under a prefix concurrently. Package
# staging is dominated by per-object latency, so a small pool gives a large speedup
# without overwhelming the client connection pool.
_DOWNLOAD_PREFIX_MAX_WORKERS = 12


def storage_is_s3() -> bool:
    return settings.storage_backend == "s3"


def is_s3_uri(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("s3://")


@dataclass(frozen=True)
class S3Location:
    bucket: str
    key: str

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}" if self.key else f"s3://{self.bucket}"


def parse_s3_uri(uri: str) -> S3Location:
    parsed = urlparse(str(uri))
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Not an s3:// URI: {uri!r}")
    return S3Location(bucket=parsed.netloc, key=parsed.path.lstrip("/"))


def join_s3_uri(base: str, *parts: str) -> str:
    """Append path segments to an s3:// URI (collapsing slashes)."""
    location = parse_s3_uri(base)
    extra = [str(part).strip("/") for part in parts if str(part).strip("/")]
    key = "/".join(segment for segment in [location.key.strip("/"), *extra] if segment)
    return S3Location(location.bucket, key).uri


def object_key(*parts: str) -> str:
    """Key within the configured bucket, under the optional ``S3_PREFIX``."""
    prefix = (settings.s3_prefix or "").strip("/")
    segments = [prefix, *[str(part).strip("/") for part in parts if str(part).strip("/")]]
    return "/".join(segment for segment in segments if segment)


@lru_cache(maxsize=1)
def _client():
    import boto3  # lazy: only needed in s3 mode
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=settings.s3_region or None,
        endpoint_url=settings.s3_endpoint_url or None,
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    if not settings.s3_bucket:
        raise RuntimeError("STORAGE_BACKEND=s3 but S3_BUCKET is not configured")
    return settings.s3_bucket


def object_exists(key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        _client().head_object(Bucket=_bucket(), Key=key)
        return True
    except ClientError:
        return False


def presigned_get_url(key: str, *, filename: str | None = None, expires: int | None = None) -> str:
    params: dict[str, str] = {"Bucket": _bucket(), "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'inline; filename="{filename}"'
    return _client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires or settings.s3_presign_expiry_seconds,
    )


def download_prefix(uri: str, dest_dir: Path) -> int:
    """Download every object under an s3:// prefix into ``dest_dir`` preserving the
    relative key layout. Returns the number of files written. Blocking — call from a
    worker thread in async contexts."""
    location = parse_s3_uri(uri)
    base = location.key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    client = _client()
    paginator = client.get_paginator("list_objects_v2")

    # List first, creating parent dirs single-threaded (avoids mkdir races), then
    # download the objects concurrently — staging is latency-bound, not CPU-bound.
    downloads: list[tuple[str, str]] = []
    for page in paginator.paginate(Bucket=location.bucket, Prefix=base_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            relative = key[len(base_prefix):] if base_prefix and key.startswith(base_prefix) else key
            if not relative:
                continue
            target = dest_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            downloads.append((key, str(target)))

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


def list_s3_package_candidates(root_uri: str) -> list[dict[str, object]]:
    """List immediate sub-prefixes under an s3:// root that look like family
    packages (contain a manifest or a ``*.ped``).

    Returns dicts with ``name``, ``uri`` (the s3:// folder), ``has_manifest`` and
    ``has_ped``. Blocking — call from a worker thread in async contexts."""
    location = parse_s3_uri(root_uri)
    base = location.key.rstrip("/")
    base_prefix = f"{base}/" if base else ""
    client = _client()
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
        has_manifest = any(
            leaf in ("manifest.yaml", "manifest.yml", "manifest.json") for leaf in leaf_names
        )
        has_ped = any(leaf.endswith(".ped") for leaf in leaf_names)
        if not has_manifest and not has_ped:
            continue
        candidates.append(
            {
                "name": name,
                "uri": join_s3_uri(root_uri, name),
                "has_manifest": has_manifest,
                "has_ped": has_ped,
            }
        )
    return candidates
