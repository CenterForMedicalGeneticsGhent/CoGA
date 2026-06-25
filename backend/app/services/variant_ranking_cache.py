"""Per-family cache of the phenotype-prioritised small-variant ranking.

The prioritised default view (Phenotype-priority preset + Mendeliome panel) costs ~10s
to compute, dominated by per-gene phenotype scoring against Monarch. This caches the
ranked order keyed by an ``inputs_hash`` — a digest of the query filters plus the mutable
inputs that change the ranking (affected HPO terms, pedigree/affected status, gene-panel
version, Monarch release, scoring-algorithm version). Any change flips the hash, so a
stale ranking is never served. See docs / the small-variant page.

This module owns only the hash + Postgres cache rows; the (de)serialisation of variant
records is done by the caller (clickhouse_family_variants) which holds those helpers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Bump when the scoring/ranking logic changes so old cached rankings are ignored.
_ALGORITHM_VERSION = "1"
# Keep only the few most-recent distinct query signatures per family.
_MAX_CACHE_ROWS_PER_FAMILY = 6


def canonical_filters(filters: Any) -> dict[str, Any]:
    """The ranking-relevant filter fields (pagination removed) — used for the hash and
    to replay the query during background warming."""
    data = asdict(filters) if is_dataclass(filters) else dict(filters)
    # Pagination doesn't change the ranking — the whole order is cached.
    data.pop("page", None)
    data.pop("page_size", None)
    return data


async def _pedigree_signature(session: AsyncSession, context: Any) -> Any:
    # The pedigree structure hash already captures roles, parentage and affected
    # status, and is bumped on every pedigree/phenotype edit — reuse it when present.
    structure_hash = (
        await session.execute(
            text(
                """
                SELECT structure_hash
                FROM family_structure_versions
                WHERE family_id = CAST(:family_uuid AS uuid)
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"family_uuid": context.family_uuid},
        )
    ).scalar()
    if structure_hash:
        return {"structure_hash": structure_hash}
    # Fallback: derive from the loaded context.
    samples = sorted(
        (
            {
                "id": row.get("sample_id"),
                "role": row.get("role"),
                "affected": row.get("affected"),
                "clinical_status": row.get("clinical_status"),
            }
            for row in (getattr(context, "sample_rows", None) or [])
        ),
        key=lambda entry: str(entry["id"]),
    )
    return {
        "affected": sorted(getattr(context, "affected_sample_names", None) or []),
        "samples": samples,
        "relationships": sorted(
            (json.dumps(row, sort_keys=True, default=str) for row in (context.relationship_rows or [])),
        ),
    }


async def _panel_version(session: AsyncSession, panel_id: str | None) -> str | None:
    if not panel_id:
        return None
    row = (
        await session.execute(
            text("SELECT version, external_version FROM gene_panels WHERE id = CAST(:id AS uuid)"),
            {"id": panel_id},
        )
    ).mappings().first()
    if not row:
        return None
    return f"{row['version']}:{row['external_version'] or ''}"


async def _monarch_release(session: AsyncSession) -> str | None:
    release = (
        await session.execute(text("SELECT max(release_version) FROM monarch_gene_disease"))
    ).scalar()
    return str(release) if release else None


async def compute_inputs_hash(
    session: AsyncSession,
    *,
    context: Any,
    filters: Any,
    patient_terms: Any,
    review_variant_ids: Any = None,
    excluded_review_variant_ids: Any = None,
    include_review_filter_active: bool = False,
) -> str:
    # Review-tag filters are resolved to variant-id sets outside the filter object, so
    # they must be folded into the hash or two otherwise-identical queries would collide.
    review_signature = {
        "active": bool(include_review_filter_active),
        "include": sorted({str(v) for v in (review_variant_ids or [])}),
        "exclude": sorted({str(v) for v in (excluded_review_variant_ids or [])}),
    }
    payload = {
        "algorithm": _ALGORITHM_VERSION,
        "assembly": getattr(context, "assembly_name", None),
        "filters": canonical_filters(filters),
        "review": review_signature,
        "hpo": sorted({str(term) for term in (patient_terms or [])}),
        "pedigree": await _pedigree_signature(session, context),
        "panel_version": await _panel_version(session, getattr(filters, "panel_id", None)),
        "monarch_release": await _monarch_release(session),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def get_cached_ranking(
    session: AsyncSession, *, family_uuid: str, inputs_hash: str
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT total, total_is_estimated, ranking_truncated, ranking,
                       provenance, computed_at
                FROM family_variant_ranking_cache
                WHERE family_id = CAST(:family_uuid AS uuid) AND inputs_hash = :inputs_hash
                """
            ),
            {"family_uuid": family_uuid, "inputs_hash": inputs_hash},
        )
    ).mappings().first()
    return dict(row) if row else None


async def store_ranking(
    session: AsyncSession,
    *,
    family_uuid: str,
    inputs_hash: str,
    total: int,
    total_is_estimated: bool,
    ranking_truncated: bool,
    ranking: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO family_variant_ranking_cache
                (family_id, inputs_hash, total, total_is_estimated, ranking_truncated,
                 ranking, provenance, computed_at)
            VALUES
                (CAST(:family_uuid AS uuid), :inputs_hash, :total, :estimated, :truncated,
                 CAST(:ranking AS jsonb), CAST(:provenance AS jsonb), now())
            ON CONFLICT (family_id, inputs_hash) DO UPDATE SET
                total = EXCLUDED.total,
                total_is_estimated = EXCLUDED.total_is_estimated,
                ranking_truncated = EXCLUDED.ranking_truncated,
                ranking = EXCLUDED.ranking,
                provenance = EXCLUDED.provenance,
                computed_at = now()
            """
        ),
        {
            "family_uuid": family_uuid,
            "inputs_hash": inputs_hash,
            "total": total,
            "estimated": total_is_estimated,
            "truncated": ranking_truncated,
            "ranking": json.dumps(ranking),
            "provenance": json.dumps(provenance or {}),
        },
    )
    # Keep the cache bounded — drop all but the most recent signatures per family.
    await session.execute(
        text(
            """
            DELETE FROM family_variant_ranking_cache
            WHERE family_id = CAST(:family_uuid AS uuid)
              AND id NOT IN (
                  SELECT id FROM family_variant_ranking_cache
                  WHERE family_id = CAST(:family_uuid AS uuid)
                  ORDER BY computed_at DESC
                  LIMIT :keep
              )
            """
        ),
        {"family_uuid": family_uuid, "keep": _MAX_CACHE_ROWS_PER_FAMILY},
    )
    await session.commit()


async def clear_family_ranking_cache(session: AsyncSession, family_uuid: str) -> None:
    await session.execute(
        text(
            "DELETE FROM family_variant_ranking_cache WHERE family_id = CAST(:family_uuid AS uuid)"
        ),
        {"family_uuid": family_uuid},
    )
    await session.commit()
