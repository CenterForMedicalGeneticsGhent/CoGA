import pytest
from fastapi import HTTPException

from app.routers import cram
from app.services import family_package_import as fpi


def test_s3_source_authorization(monkeypatch):
    monkeypatch.setattr(
        fpi.settings, "family_import_roots", ["s3://bucket/families", "/data/families"]
    )
    assert fpi._ensure_authorized_s3_source("s3://bucket/families/F1") == "s3://bucket/families/F1"
    assert fpi._authorized_s3_roots() == ["s3://bucket/families"]
    with pytest.raises(HTTPException):
        fpi._ensure_authorized_s3_source("s3://other-bucket/families/F1")


def test_s3_source_rejected_without_configured_root(monkeypatch):
    monkeypatch.setattr(fpi.settings, "family_import_roots", ["/data/families"])
    with pytest.raises(HTTPException):
        fpi._ensure_authorized_s3_source("s3://bucket/families/F1")


def test_staged_package_source_local_is_passthrough(tmp_path):
    with fpi.staged_package_source(str(tmp_path)) as (root, source_uri):
        assert root == str(tmp_path)
        assert source_uri is None


def test_cram_manifest_uses_presigned_urls_in_s3_mode(monkeypatch):
    monkeypatch.setattr(cram, "storage_is_s3", lambda: True)
    monkeypatch.setattr(cram, "object_key", lambda *parts: "/".join(parts))
    # Pretend the CRAM + index objects exist (but not the BAM ones).
    monkeypatch.setattr(cram, "object_exists", lambda key: ".cram" in key)
    monkeypatch.setattr(
        cram, "presigned_get_url", lambda key, filename=None: f"https://s3.example/{key}?sig=abc"
    )

    entry = cram._resolve_alignment_manifest_entry("F1", "S1")
    assert entry is not None
    assert entry.format == "cram"
    assert entry.url == "https://s3.example/F1/S1.cram?sig=abc"
    assert entry.index_url == "https://s3.example/F1/S1.cram.crai?sig=abc"


def test_cram_manifest_relative_urls_in_local_mode(monkeypatch):
    monkeypatch.setattr(cram, "storage_is_s3", lambda: False)
    monkeypatch.setattr(cram, "_alignment_exists", lambda fam, sample, ext, suffix="": ext == "cram")
    entry = cram._resolve_alignment_manifest_entry("F1", "S1")
    assert entry is not None
    assert entry.url == "/cram/F1/S1.cram"
    assert entry.index_url == "/cram/F1/S1.cram.crai"
