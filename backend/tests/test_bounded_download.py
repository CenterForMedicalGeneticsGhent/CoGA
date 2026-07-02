"""Bounded outbound download + gunzip (Refs #336).

Reference/gene/phenotype refreshes pull gzip files from external hosts and decompress
them in memory. These tests prove the caps hold: a tiny "bomb" that inflates to tens of
MiB is aborted at the ceiling instead of exhausting worker memory, an oversized transfer
is stopped mid-stream, and the optional-file (404) and upstream-error paths are preserved.
"""
from __future__ import annotations

import gzip

import httpx
import pytest

from backend.app.services.bounded_download import (
    download_bounded_bytes,
    gunzip_bounded,
)


# --- gunzip_bounded --------------------------------------------------------------------


def test_gunzip_bounded_roundtrips_valid_gzip() -> None:
    payload = b"gene\tdisease\n" * 5000
    assert gunzip_bounded(gzip.compress(payload), source="t") == payload


def test_gunzip_bounded_rejects_oversized_output() -> None:
    payload = b"x" * 10_000
    with pytest.raises(ValueError, match="expands beyond"):
        gunzip_bounded(gzip.compress(payload), max_bytes=1_000, source="t")


def test_gunzip_bounded_rejects_invalid_stream() -> None:
    with pytest.raises(ValueError, match="not valid gzip"):
        gunzip_bounded(b"this is not gzip", source="t")


def test_gunzip_bounded_halts_decompression_bomb_at_cap() -> None:
    # ~64 MiB of zeros compresses to a few KiB; the cap must abort long before it inflates.
    bomb = gzip.compress(b"\x00" * (64 << 20))
    assert len(bomb) < (1 << 20)  # compressed stays tiny
    with pytest.raises(ValueError, match="expands beyond"):
        gunzip_bounded(bomb, max_bytes=(1 << 20), source="bomb")


# --- download_bounded_bytes ------------------------------------------------------------


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_download_bounded_bytes_returns_full_body() -> None:
    async with _client(lambda req: httpx.Response(200, content=b"hello world")) as client:
        assert await download_bounded_bytes(client, "https://x/y", source="t") == b"hello world"


@pytest.mark.asyncio
async def test_download_bounded_bytes_aborts_over_cap() -> None:
    async with _client(lambda req: httpx.Response(200, content=b"x" * 5_000)) as client:
        with pytest.raises(ValueError, match="exceeds"):
            await download_bounded_bytes(client, "https://x/y", max_bytes=1_000, source="t")


@pytest.mark.asyncio
async def test_download_bounded_bytes_optional_404_returns_none() -> None:
    async with _client(lambda req: httpx.Response(404)) as client:
        assert await download_bounded_bytes(client, "https://x/y", none_on_404=True) is None


@pytest.mark.asyncio
async def test_download_bounded_bytes_404_without_flag_raises() -> None:
    async with _client(lambda req: httpx.Response(404)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await download_bounded_bytes(client, "https://x/y")


@pytest.mark.asyncio
async def test_download_bounded_bytes_5xx_raises() -> None:
    async with _client(lambda req: httpx.Response(503)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await download_bounded_bytes(client, "https://x/y")
