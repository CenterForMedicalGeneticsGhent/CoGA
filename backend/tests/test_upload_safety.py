from __future__ import annotations

import gzip
import io

import pytest
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.upload_safety import decode_upload_text


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data))


@pytest.mark.asyncio
async def test_plain_text_under_cap_round_trips():
    text = "chrom\tstart\tend\nchr1\t1\t2\n"
    out = await decode_upload_text(_upload(text.encode()), kind="BED")
    assert out == text


@pytest.mark.asyncio
async def test_gzipped_text_is_decompressed():
    text = "##fileformat=VCFv4.2\n"
    out = await decode_upload_text(_upload(gzip.compress(text.encode())), kind="SV")
    assert out == text


@pytest.mark.asyncio
async def test_oversized_plain_upload_rejected(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 64)
    with pytest.raises(HTTPException) as exc:
        await decode_upload_text(_upload(b"x" * 1000), kind="BED")
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_gzip_bomb_rejected_by_decompressed_cap(monkeypatch):
    # ~8 MiB of zeros compresses to a few KB; cap the decompressed size low so the
    # bomb is stopped at the cap instead of inflating fully into memory.
    monkeypatch.setattr(settings, "max_upload_bytes", 100 * 1024 * 1024)
    monkeypatch.setattr(settings, "max_decompressed_upload_bytes", 1 * 1024 * 1024)
    bomb = gzip.compress(b"\x00" * (8 * 1024 * 1024))
    assert len(bomb) < 1 * 1024 * 1024  # tiny compressed payload
    with pytest.raises(HTTPException) as exc:
        await decode_upload_text(_upload(bomb), kind="Reference")
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_corrupt_gzip_rejected_as_bad_request():
    # gzip magic byte prefix but an invalid header/body.
    data = b"\x1f\x8b" + b"\x00" * 32
    with pytest.raises(HTTPException) as exc:
        await decode_upload_text(_upload(data), kind="TRGT")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_non_utf8_plain_rejected_as_bad_request():
    with pytest.raises(HTTPException) as exc:
        await decode_upload_text(_upload(b"\xff\xfe\x00bad"), kind="PED")
    assert exc.value.status_code == 400
