from datetime import timedelta
from pathlib import Path

import pytest

from app.core import object_storage as s
from app.core.config import Settings


# --- Scheme-agnostic remote URI helpers -------------------------------------

def test_is_remote_uri():
    assert s.is_remote_uri("s3://bucket/key")
    assert s.is_remote_uri("S3://Bucket/Key")
    assert s.is_remote_uri("gs://bucket/key")
    assert s.is_remote_uri("GS://Bucket/Key")
    assert not s.is_remote_uri("/data/families/F1")
    assert not s.is_remote_uri(None)
    assert not s.is_remote_uri(123)


def test_parse_remote_uri_s3_and_gcs():
    s3 = s.parse_remote_uri("s3://bucket/families/F1")
    assert (s3.scheme, s3.bucket, s3.key) == ("s3", "bucket", "families/F1")
    assert s3.uri == "s3://bucket/families/F1"

    gcs = s.parse_remote_uri("gs://bucket/families/F1")
    assert (gcs.scheme, gcs.bucket, gcs.key) == ("gs", "bucket", "families/F1")
    assert gcs.uri == "gs://bucket/families/F1"


def test_parse_remote_uri_rejects_local():
    with pytest.raises(ValueError):
        s.parse_remote_uri("/data/families/F1")


def test_join_remote_uri_preserves_scheme_and_collapses_slashes():
    assert s.join_remote_uri("s3://bucket/families/F1", "S1.cram") == "s3://bucket/families/F1/S1.cram"
    assert s.join_remote_uri("gs://bucket/families/F1", "S1.cram") == "gs://bucket/families/F1/S1.cram"
    assert (
        s.join_remote_uri("gs://bucket/families/F1/", "sub/", "/x.vcf.gz")
        == "gs://bucket/families/F1/sub/x.vcf.gz"
    )


def test_object_key_honours_prefix_per_backend(monkeypatch):
    monkeypatch.setattr(s.settings, "storage_backend", "s3")
    monkeypatch.setattr(s.settings, "s3_prefix", "families")
    assert s.object_key("F1", "S1.cram") == "families/F1/S1.cram"

    monkeypatch.setattr(s.settings, "storage_backend", "gcs")
    monkeypatch.setattr(s.settings, "gcs_prefix", "phi")
    assert s.object_key("F1", "S1.cram") == "phi/F1/S1.cram"

    monkeypatch.setattr(s.settings, "gcs_prefix", "")
    assert s.object_key("F1", "S1.cram") == "F1/S1.cram"


# --- Backend flags ----------------------------------------------------------

def test_backend_flags(monkeypatch):
    monkeypatch.setattr(s.settings, "storage_backend", "local")
    assert not s.storage_is_remote() and not s.storage_is_s3() and not s.storage_is_gcs()

    monkeypatch.setattr(s.settings, "storage_backend", "s3")
    assert s.storage_is_remote() and s.storage_is_s3() and not s.storage_is_gcs()

    monkeypatch.setattr(s.settings, "storage_backend", "gcs")
    assert s.storage_is_remote() and s.storage_is_gcs() and not s.storage_is_s3()


# --- Settings validation ----------------------------------------------------

def test_storage_backend_defaults_to_local():
    assert Settings(_env_file=None).storage_backend == "local"


def test_s3_backend_requires_bucket():
    with pytest.raises(Exception):
        Settings(_env_file=None, APP_ENV="development", STORAGE_BACKEND="s3")


def test_s3_backend_with_bucket_is_valid():
    settings = Settings(
        _env_file=None, APP_ENV="development", STORAGE_BACKEND="s3", S3_BUCKET="my-bucket"
    )
    assert settings.storage_backend == "s3"
    assert settings.s3_bucket == "my-bucket"


def test_gcs_backend_requires_bucket():
    with pytest.raises(Exception):
        Settings(_env_file=None, APP_ENV="development", STORAGE_BACKEND="gcs")


def test_gcs_backend_with_bucket_is_valid():
    settings = Settings(
        _env_file=None, APP_ENV="development", STORAGE_BACKEND="gcs", GCS_BUCKET="my-bucket"
    )
    assert settings.storage_backend == "gcs"
    assert settings.gcs_bucket == "my-bucket"


def test_invalid_storage_backend_rejected():
    with pytest.raises(Exception):
        Settings(_env_file=None, APP_ENV="development", STORAGE_BACKEND="azure")


# --- Backward-compatible S3-named aliases -----------------------------------

def test_deprecated_s3_aliases_still_resolve():
    assert s.is_s3_uri is s.is_remote_uri
    assert s.parse_s3_uri is s.parse_remote_uri
    assert s.join_s3_uri is s.join_remote_uri
    assert s.list_s3_package_candidates is s.list_remote_package_candidates
    assert s.S3Location is s.RemoteLocation


# --- GCS backend (clients mocked: google-cloud-storage not exercised) --------

def _use_gcs(monkeypatch, bucket="phi-bucket"):
    monkeypatch.setattr(s.settings, "storage_backend", "gcs")
    monkeypatch.setattr(s.settings, "gcs_bucket", bucket)


def test_gcs_object_exists(monkeypatch):
    _use_gcs(monkeypatch)

    class _Blob:
        def __init__(self, key):
            self._key = key

        def exists(self):
            return self._key == "F1/S1.cram"

    class _Bucket:
        def blob(self, key):
            return _Blob(key)

    class _Client:
        def bucket(self, name):
            assert name == "phi-bucket"
            return _Bucket()

    monkeypatch.setattr(s, "_gcs_client", lambda: _Client())
    assert s.object_exists("F1/S1.cram") is True
    assert s.object_exists("F1/missing.cram") is False


def test_gcs_signed_url_uses_iam_signing(monkeypatch):
    _use_gcs(monkeypatch)
    captured: dict = {}

    class _Blob:
        def generate_signed_url(self, **kwargs):
            captured.update(kwargs)
            return "https://signed.example/x"

    class _Bucket:
        def blob(self, key):
            captured["key"] = key
            return _Blob()

    class _Client:
        def bucket(self, name):
            captured["bucket"] = name
            return _Bucket()

    monkeypatch.setattr(s, "_gcs_client", lambda: _Client())
    monkeypatch.setattr(s, "_gcs_signing_credentials", lambda: ("sa@proj.iam.gserviceaccount.com", "tok123"))

    url = s.presigned_get_url("F1/S1.cram", filename="S1.cram", expires=120)
    assert url == "https://signed.example/x"
    assert captured["bucket"] == "phi-bucket"
    assert captured["key"] == "F1/S1.cram"
    assert captured["version"] == "v4"
    assert captured["method"] == "GET"
    assert captured["service_account_email"] == "sa@proj.iam.gserviceaccount.com"
    assert captured["access_token"] == "tok123"
    assert captured["expiration"] == timedelta(seconds=120)
    assert 'filename="S1.cram"' in captured["response_disposition"]


def test_gcs_download_prefix(monkeypatch, tmp_path):
    _use_gcs(monkeypatch)

    class _Blob:
        def __init__(self, name):
            self.name = name

        def download_to_filename(self, target):
            Path(target).write_text("data")

    class _Client:
        def list_blobs(self, bucket, prefix=None, delimiter=None):
            assert bucket == "phi-bucket"
            assert prefix == "fam/F1/"
            return [
                _Blob("fam/F1/manifest.yaml"),
                _Blob("fam/F1/sub/x.vcf.gz"),
                _Blob("fam/F1/"),  # the "directory" placeholder is skipped
            ]

    monkeypatch.setattr(s, "_gcs_client", lambda: _Client())

    written = s.download_prefix("gs://phi-bucket/fam/F1", tmp_path)
    assert written == 2
    assert (tmp_path / "manifest.yaml").read_text() == "data"
    assert (tmp_path / "sub" / "x.vcf.gz").exists()


def test_gcs_list_package_candidates(monkeypatch):
    _use_gcs(monkeypatch)

    class _Blob:
        def __init__(self, name):
            self.name = name

    class _BlobPage(list):
        def __init__(self, items, prefixes=()):
            super().__init__(items)
            self.prefixes = list(prefixes)

    class _Client:
        def list_blobs(self, bucket, prefix=None, delimiter=None):
            if delimiter == "/":
                return _BlobPage([], prefixes=["fam/F1/", "fam/F2/", "fam/empty/"])
            if prefix == "fam/F1/":
                return _BlobPage([_Blob("fam/F1/manifest.yaml")])
            if prefix == "fam/F2/":
                return _BlobPage([_Blob("fam/F2/trio.ped")])
            return _BlobPage([])  # fam/empty/ has neither manifest nor ped

    monkeypatch.setattr(s, "_gcs_client", lambda: _Client())

    candidates = {c["name"]: c for c in s.list_remote_package_candidates("gs://phi-bucket/fam")}
    assert set(candidates) == {"F1", "F2"}
    assert candidates["F1"]["has_manifest"] and not candidates["F1"]["has_ped"]
    assert candidates["F2"]["has_ped"] and not candidates["F2"]["has_manifest"]
    assert candidates["F1"]["uri"] == "gs://phi-bucket/fam/F1"
