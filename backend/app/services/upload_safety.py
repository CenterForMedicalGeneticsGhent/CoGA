"""Bounded reading/decompression for user uploads.

Several admin upload endpoints used to ``await file.read()`` the whole upload into
memory and then ``gzip.decompress()`` it — also fully in memory — with no size cap.
A small, highly compressible ``.gz`` ("decompression bomb") could therefore inflate
to exhaust the worker's memory (DoS). ``decode_upload_text`` reads the upload and
decompresses it with explicit caps on both the bytes read and the decompressed size,
rejecting oversized input with HTTP 413 instead of buffering it without limit.

The small-variant ingestion path streams line-by-line via ``gzip.open`` and is already
memory-safe; this helper brings the remaining full-buffer decoders (SV, reference,
BED, repeat-expansion, PED) up to the same standard.
"""

from __future__ import annotations

import zlib

from fastapi import HTTPException, UploadFile

from ..core.config import settings

_GZIP_MAGIC = b"\x1f\x8b"
_READ_CHUNK = 1 << 20  # 1 MiB per read
_DECOMP_STEP = 1 << 20  # bound decompressed output produced per step


async def _read_upload_bounded(file: UploadFile, max_bytes: int, *, kind: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"{kind} upload exceeds the maximum allowed size",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _gunzip_bounded(data: bytes, max_bytes: int, *, kind: str) -> bytes:
    # wbits=31 selects gzip framing. decompress(..., max_length) caps output per call
    # and parks the rest in unconsumed_tail, so a bomb is stopped at the cap instead
    # of inflating fully before the size is known.
    decompressor = zlib.decompressobj(wbits=31)
    out = bytearray()
    pending = data
    try:
        while pending:
            out += decompressor.decompress(pending, _DECOMP_STEP)
            if len(out) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"{kind} upload expands beyond the maximum allowed size",
                )
            pending = decompressor.unconsumed_tail
        out += decompressor.flush()
    except zlib.error as exc:
        raise HTTPException(
            status_code=400, detail=f"{kind} file is not valid gzip"
        ) from exc
    if len(out) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"{kind} upload expands beyond the maximum allowed size",
        )
    return bytes(out)


async def decode_upload_text(file: UploadFile, *, kind: str) -> str:
    """Read an upload (optionally gzip) into UTF-8 text with bounded memory.

    Caps both the bytes read (``MAX_UPLOAD_BYTES``) and the decompressed size
    (``MAX_DECOMPRESSED_UPLOAD_BYTES``); oversized input is rejected with HTTP 413.
    Raises 400 if the content is neither valid UTF-8 text nor valid gzip.
    """
    raw = await _read_upload_bounded(file, settings.max_upload_bytes, kind=kind)
    if raw[:2] == _GZIP_MAGIC:
        raw = _gunzip_bounded(raw, settings.max_decompressed_upload_bytes, kind=kind)
    try:
        return raw.decode()
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{kind} file must be UTF-8 text or gzipped UTF-8 text",
        ) from exc
