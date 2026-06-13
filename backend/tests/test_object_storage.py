import pytest
from fastapi import HTTPException

from app.core import object_storage as s
from app.core.config import Settings


def test_is_s3_uri():
    assert s.is_s3_uri("s3://bucket/key")
    assert s.is_s3_uri("S3://Bucket/Key")
    assert not s.is_s3_uri("/data/families/F1")
    assert not s.is_s3_uri(None)
    assert not s.is_s3_uri(123)


def test_parse_s3_uri():
    loc = s.parse_s3_uri("s3://bucket/families/F1")
    assert (loc.bucket, loc.key) == ("bucket", "families/F1")
    assert loc.uri == "s3://bucket/families/F1"


def test_parse_s3_uri_rejects_local():
    with pytest.raises(ValueError):
        s.parse_s3_uri("/data/families/F1")


def test_join_s3_uri_collapses_slashes():
    assert s.join_s3_uri("s3://bucket/families/F1", "S1.cram") == "s3://bucket/families/F1/S1.cram"
    assert (
        s.join_s3_uri("s3://bucket/families/F1/", "sub/", "/x.vcf.gz")
        == "s3://bucket/families/F1/sub/x.vcf.gz"
    )


def test_object_key_honours_prefix(monkeypatch):
    monkeypatch.setattr(s.settings, "s3_prefix", "families")
    assert s.object_key("F1", "S1.cram") == "families/F1/S1.cram"
    monkeypatch.setattr(s.settings, "s3_prefix", "")
    assert s.object_key("F1", "S1.cram") == "F1/S1.cram"


def test_storage_backend_defaults_to_local():
    assert Settings(_env_file=None).storage_backend == "local"


def test_s3_backend_requires_bucket():
    with pytest.raises(Exception):
        Settings(_env_file=None, APP_ENV="development", STORAGE_BACKEND="s3")


def test_s3_backend_with_bucket_is_valid():
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        STORAGE_BACKEND="s3",
        S3_BUCKET="my-bucket",
    )
    assert settings.storage_backend == "s3"
    assert settings.s3_bucket == "my-bucket"


def test_invalid_storage_backend_rejected():
    with pytest.raises(Exception):
        Settings(_env_file=None, APP_ENV="development", STORAGE_BACKEND="gcs")
