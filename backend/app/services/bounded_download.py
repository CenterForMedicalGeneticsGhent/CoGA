"""Bounded outbound download + gzip decompression for reference-data fetches.

The reference / gene / phenotype refresh paths pull files from external hosts and
``gzip.decompress()`` them fully in memory. A compromised, MITM'd, or simply misbehaving
upstream could return a decompression bomb (a tiny ``.gz`` that inflates to gigabytes) and
OOM the worker. These helpers cap both the compressed bytes read and the decompressed
size. Unlike ``upload_safety`` (which handles CLIENT uploads and raises HTTP 4xx), an
oversized/invalid response here is a server-side / upstream fault, so we raise
``ValueError`` for the caller to surface as a 5xx / failed refresh.

The ceilings are generous — real reference/gene/phenotype files are tens-to-hundreds of
MB — so they only stop a runaway from exhausting worker memory, never a legitimate file.
"""
from __future__ import annotations

import zlib

import httpx

_READ_CHUNK = 1 << 20  # 1 MiB per streamed chunk
_DECOMP_STEP = 1 << 20  # bound decompressed output produced per step

# OOM-protection ceilings (not tight limits).
MAX_DOWNLOAD_BYTES = 1 << 30  # 1 GiB of compressed/raw response
MAX_DECOMPRESSED_BYTES = 4 << 30  # 4 GiB after gunzip


async def download_bounded_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    source: str | None = None,
    none_on_404: bool = False,
) -> bytes | None:
    """Stream a GET into memory, aborting if it exceeds ``max_bytes``.

    Streaming (vs ``response.content``) means an oversized body is stopped mid-transfer
    instead of being buffered whole first. ``none_on_404`` returns None for a 404 (the
    "optional file" pattern). Raises ``httpx.HTTPError`` on transport/status errors (the
    caller keeps its own upstream-error handling) and ``ValueError`` when the cap trips.
    """
    label = source or url
    chunks: list[bytes] = []
    total = 0
    async with client.stream("GET", url) as response:
        if none_on_404 and response.status_code == 404:
            return None
        response.raise_for_status()
        async for chunk in response.aiter_bytes(_READ_CHUNK):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"{label} download exceeds {max_bytes} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def gunzip_bounded(
    data: bytes, *, max_bytes: int = MAX_DECOMPRESSED_BYTES, source: str | None = None
) -> bytes:
    """Gzip-decompress with a hard cap on the OUTPUT, stopping a decompression bomb.

    ``decompress(..., max_length)`` caps output per call and parks the rest in
    ``unconsumed_tail``, so a bomb is halted at the cap instead of inflating fully before
    its size is known. Raises ``ValueError`` on an oversized or invalid gzip stream.
    """
    label = source or "gzip stream"
    decompressor = zlib.decompressobj(wbits=31)  # gzip framing
    out = bytearray()
    pending = data
    try:
        while pending:
            out += decompressor.decompress(pending, _DECOMP_STEP)
            if len(out) > max_bytes:
                raise ValueError(f"{label} expands beyond {max_bytes} bytes")
            pending = decompressor.unconsumed_tail
        out += decompressor.flush()
    except zlib.error as exc:
        raise ValueError(f"{label} is not valid gzip") from exc
    if len(out) > max_bytes:
        raise ValueError(f"{label} expands beyond {max_bytes} bytes")
    return bytes(out)
