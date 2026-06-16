"""Shared helpers for the small- and structural-variant review-PG services.

These were byte-for-byte duplicated across small_variant_review_pg and
structural_variant_review_pg (and re-implemented in several other service
modules); they live here as the single source of truth.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Sequence
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder


def _require_uuid(value: str, detail: str) -> str:
    try:
        UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=detail) from exc
    return value


def _normalize_tags(tags: Iterable[str]) -> list[str]:
    return sorted({str(tag).strip() for tag in tags if str(tag).strip()})


def _json_payload(value: Any) -> str:
    return json.dumps(jsonable_encoder(value if value is not None else {}))


def _merge_tag_metadata(
    *,
    existing_metadata: dict[str, Any] | None,
    previous_tags: Sequence[str],
    next_tags: Sequence[str],
    username: str,
    timestamp: datetime,
) -> dict[str, dict[str, Any]]:
    previous = set(_normalize_tags(previous_tags))
    merged: dict[str, dict[str, Any]] = {}
    for tag in _normalize_tags(next_tags):
        if tag in previous and isinstance((existing_metadata or {}).get(tag), dict):
            merged[tag] = {
                "updated_by": (existing_metadata or {})[tag].get("updated_by"),
                "updated_at": (existing_metadata or {})[tag].get("updated_at"),
            }
        else:
            merged[tag] = {
                "updated_by": username,
                "updated_at": timestamp,
            }
    return merged
