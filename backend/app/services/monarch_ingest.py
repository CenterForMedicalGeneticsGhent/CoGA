"""Ingest Monarch Initiative gene -> disease associations.

Downloads the Monarch Knowledge Graph denormalized association TSVs (human causal
and the cross-species noncausal file), filters to human gene -> disease edges,
aggregates them into one record per (gene, disease), and replaces the contents of
the `monarch_gene_disease` table.

Reference data only; keyed by HGNC and joined onto the gene profile by symbol at
read time. See docs/monarch-integration.md.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Monthly releases; "latest" always redirects to the newest dated release.
MONARCH_KG_BASE_URL = "https://data.monarchinitiative.org/monarch-kg/latest"
MONARCH_METADATA_URL = f"{MONARCH_KG_BASE_URL}/metadata.yaml"
_TSV_BASE = f"{MONARCH_KG_BASE_URL}/tsv/gene_associations"

# Pre-split denormalized association files. The causal file is taxon-filtered to
# human (9606); the noncausal file is cross-species but gene -> disease rows are
# HGNC-subject and we filter to those.
MONARCH_GENE_DISEASE_FILES = (
    (f"{_TSV_BASE}/gene_disease.9606.tsv.gz", True),
    (f"{_TSV_BASE}/gene_disease.noncausal.tsv.gz", False),
)

_HGNC_PREFIX = "HGNC:"
_MONDO_PREFIX = "MONDO:"

# Predicate priority, strongest relationship first. Used to pick the representative
# predicate when a (gene, disease) pair is asserted by several edges.
_PREDICATE_PRIORITY = (
    "causes",
    "gene_associated_with_condition",
    "contributes_to",
    "associated_with_increased_likelihood_of",
)
# `causal` mirrors Monarch's own causal/noncausal split: only `biolink:causes`
# (the human causal file) is strong direct causation. `gene_associated_with_condition`
# and `contributes_to` come from the noncausal file and are broader associations.
_CAUSAL_PREDICATES = frozenset({"causes"})


def _strip_prefix(value: str, sep: str = ":") -> str:
    """Drop a CURIE-style namespace prefix, e.g. ``biolink:causes`` -> ``causes``."""
    text_value = (value or "").strip()
    _, _, tail = text_value.rpartition(sep)
    return tail or text_value


def _predicate_rank(predicate: str) -> int:
    try:
        return _PREDICATE_PRIORITY.index(predicate)
    except ValueError:
        return len(_PREDICATE_PRIORITY)


@dataclass(slots=True)
class _Association:
    hgnc_id: str
    gene_symbol: str
    mondo_id: str
    disease_label: str
    predicates: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)

    @property
    def predicate(self) -> str:
        return min(self.predicates, key=_predicate_rank)

    @property
    def causal(self) -> bool:
        return bool(self.predicates & _CAUSAL_PREDICATES)


async def _download_gzip_tsv(url: str) -> str:
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    raw = response.content
    if url.endswith(".gz"):
        raw = gzip.decompress(raw)
    return raw.decode("utf-8")


async def _fetch_release_version() -> str | None:
    """Read the release id (e.g. ``2026-06-08``) from the KG metadata file."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(MONARCH_METADATA_URL)
            response.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        logger.warning("Could not fetch Monarch release metadata: %s", exc)
        return None
    for line in response.text.splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip("'\"") or None
    return None


def parse_gene_disease_tsv(
    text_value: str,
    *,
    associations: dict[tuple[str, str], _Association],
) -> None:
    """Fold the rows of one denormalized gene_disease TSV into ``associations``.

    Keyed by ``(hgnc_id, mondo_id)``; predicates and sources accumulate so a pair
    asserted by several sources/predicates collapses to a single record.
    """
    reader = csv.DictReader(io.StringIO(text_value), delimiter="\t")
    for row in reader:
        subject = (row.get("subject") or "").strip()
        obj = (row.get("object") or "").strip()
        if not subject.startswith(_HGNC_PREFIX) or not obj.startswith(_MONDO_PREFIX):
            continue
        if (row.get("negated") or "").strip().lower() == "true":
            continue
        predicate = _strip_prefix(row.get("predicate") or "")
        if not predicate:
            continue
        key = (subject, obj)
        record = associations.get(key)
        if record is None:
            record = _Association(
                hgnc_id=subject,
                gene_symbol=(row.get("subject_label") or "").strip(),
                mondo_id=obj,
                disease_label=(row.get("object_label") or "").strip(),
            )
            associations[key] = record
        record.predicates.add(predicate)
        source = _strip_prefix(row.get("primary_knowledge_source") or "")
        if source:
            record.sources.add(source)
        if not record.gene_symbol:
            record.gene_symbol = (row.get("subject_label") or "").strip()
        if not record.disease_label:
            record.disease_label = (row.get("object_label") or "").strip()


async def _replace_gene_disease_rows(
    session: AsyncSession,
    *,
    associations: Iterable[_Association],
    release_version: str | None,
    now: datetime,
) -> int:
    rows = [
        {
            "hgnc_id": assoc.hgnc_id,
            "gene_symbol": assoc.gene_symbol or assoc.hgnc_id,
            "mondo_id": assoc.mondo_id,
            "disease_label": assoc.disease_label or None,
            "predicate": assoc.predicate,
            "predicates": json.dumps(sorted(assoc.predicates)),
            "sources": json.dumps(sorted(assoc.sources)),
            "causal": assoc.causal,
            "release_version": release_version,
            "updated_at": now,
        }
        for assoc in associations
        if assoc.gene_symbol or assoc.hgnc_id
    ]

    await session.execute(text("DELETE FROM monarch_gene_disease"))
    if rows:
        await session.execute(
            text(
                """
                INSERT INTO monarch_gene_disease (
                    hgnc_id,
                    gene_symbol,
                    mondo_id,
                    disease_label,
                    predicate,
                    predicates,
                    sources,
                    causal,
                    release_version,
                    updated_at
                )
                VALUES (
                    :hgnc_id,
                    :gene_symbol,
                    :mondo_id,
                    :disease_label,
                    :predicate,
                    CAST(:predicates AS jsonb),
                    CAST(:sources AS jsonb),
                    :causal,
                    :release_version,
                    :updated_at
                )
                """
            ),
            rows,
        )
    await session.commit()
    return len(rows)


async def refresh_monarch_gene_disease(session: AsyncSession) -> dict[str, Any]:
    """Download, parse, and replace the Monarch gene -> disease table.

    Returns a summary dict suitable for an admin response.
    """
    started_at = datetime.now(timezone.utc)
    release_version = await _fetch_release_version()

    associations: dict[tuple[str, str], _Association] = {}
    files_loaded = 0
    for url, _causal in MONARCH_GENE_DISEASE_FILES:
        text_value = await _download_gzip_tsv(url)
        parse_gene_disease_tsv(text_value, associations=associations)
        files_loaded += 1

    records = list(associations.values())
    written = await _replace_gene_disease_rows(
        session,
        associations=records,
        release_version=release_version,
        now=started_at,
    )

    completed_at = datetime.now(timezone.utc)
    summary = {
        "release_version": release_version,
        "files_loaded": files_loaded,
        "gene_disease_pairs": written,
        "genes": len({assoc.hgnc_id for assoc in records}),
        "diseases": len({assoc.mondo_id for assoc in records}),
        "causal_pairs": sum(1 for assoc in records if assoc.causal),
        "completed_at": completed_at,
        "duration_seconds": (completed_at - started_at).total_seconds(),
    }
    logger.info(
        "Monarch gene-disease refresh complete: %s pairs across %s genes (release %s)",
        summary["gene_disease_pairs"],
        summary["genes"],
        release_version,
    )
    return summary


async def list_monarch_gene_disease(
    session: AsyncSession, *, symbol: str
) -> list[dict[str, Any]]:
    """Return Monarch disease associations for a gene symbol (case-insensitive)."""
    result = await session.execute(
        text(
            """
            SELECT
                hgnc_id,
                gene_symbol,
                mondo_id,
                disease_label,
                predicate,
                predicates,
                sources,
                causal,
                release_version
            FROM monarch_gene_disease
            WHERE upper(gene_symbol) = upper(:symbol)
            ORDER BY causal DESC, lower(coalesce(disease_label, mondo_id))
            """
        ),
        {"symbol": symbol},
    )
    return [dict(row) for row in result.mappings().all()]
