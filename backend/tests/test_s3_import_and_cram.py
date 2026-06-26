import asyncio
import types

import pytest
from fastapi import HTTPException

from app.routers import cram
from app.services import family_package_import as fpi


def _family_with_samples(*sample_ids):
    return types.SimpleNamespace(
        members=[types.SimpleNamespace(sample_id=s) for s in sample_ids]
    )


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


# --- PHI alignment access control (REQ-SEC-007, risk H11) -------------------
# A CRAM/BAM (or its presigned URL) must only be served after the family+sample
# access check passes. get_family_record enforces project scoping; the sample
# must belong to the family. The check must run BEFORE any bytes/URL are issued.


def test_alignment_denied_when_family_not_accessible_before_serving(monkeypatch):
    async def _deny(session, family_id, user):
        raise HTTPException(status_code=403, detail="Forbidden")

    served = {"called": False}

    def _serve_spy(*args, **kwargs):
        served["called"] = True
        return "should-not-be-reached"

    monkeypatch.setattr(cram, "get_family_record", _deny)
    monkeypatch.setattr(cram, "_serve_alignment", _serve_spy)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(cram.get_cram("F1", "S1", session=None, user=object()))

    assert exc.value.status_code == 403
    # The access failure must short-circuit before the file/presigned URL is issued.
    assert served["called"] is False


def test_alignment_denied_for_sample_outside_the_family(monkeypatch):
    async def _ok(session, family_id, user):
        return _family_with_samples("S1", "S2")

    monkeypatch.setattr(cram, "get_family_record", _ok)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            cram._ensure_accessible_alignment_sample(None, "F1", "S_FOREIGN", object())
        )

    assert exc.value.status_code == 404


def test_alignment_allowed_for_a_member_sample(monkeypatch):
    async def _ok(session, family_id, user):
        return _family_with_samples("S1", "S2")

    monkeypatch.setattr(cram, "get_family_record", _ok)

    # A sample that belongs to the family passes the gate without raising.
    assert (
        asyncio.run(
            cram._ensure_accessible_alignment_sample(None, "F1", "S1", object())
        )
        is None
    )
