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

from .monarch_phenotype_score import reset_information_content_cache

logger = logging.getLogger(__name__)

# Monthly releases; "latest" always redirects to the newest dated release.
MONARCH_KG_BASE_URL = "https://data.monarchinitiative.org/monarch-kg/latest"
MONARCH_METADATA_URL = f"{MONARCH_KG_BASE_URL}/metadata.yaml"
_GENE_TSV_BASE = f"{MONARCH_KG_BASE_URL}/tsv/gene_associations"
_DISEASE_TSV_BASE = f"{MONARCH_KG_BASE_URL}/tsv/disease_associations"

# Pre-split denormalized association files. The causal file is taxon-filtered to
# human (9606); the noncausal file is cross-species but gene -> disease rows are
# HGNC-subject and we filter to those.
MONARCH_GENE_DISEASE_FILES = (
    (f"{_GENE_TSV_BASE}/gene_disease.9606.tsv.gz", True),
    (f"{_GENE_TSV_BASE}/gene_disease.noncausal.tsv.gz", False),
)

# Disease -> phenotype (HPO). Cross-species file; filtered to MONDO -> HP rows.
MONARCH_DISEASE_PHENOTYPE_FILE = f"{_DISEASE_TSV_BASE}/disease_phenotype.all.tsv.gz"

_HGNC_PREFIX = "HGNC:"
_MONDO_PREFIX = "MONDO:"
_HPO_PREFIX = "HP:"

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
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip().strip("'\"") or None
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
    commit: bool = True,
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
    if commit:
        await session.commit()
    return len(rows)


async def refresh_monarch_gene_disease(
    session: AsyncSession,
    *,
    release_version: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Download, parse, and replace the Monarch gene -> disease table.

    Returns a summary dict suitable for an admin response.
    """
    started_at = datetime.now(timezone.utc)
    if release_version is None:
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
        commit=commit,
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


@dataclass(slots=True)
class _DiseasePhenotype:
    mondo_id: str
    disease_label: str
    hpo_id: str
    phenotype_label: str
    sources: set[str] = field(default_factory=set)
    # True only while *every* assertion of the pair is negated; a single present
    # assertion flips it to False (present wins over excluded).
    negated: bool = True


def parse_disease_phenotype_tsv(
    text_value: str,
    *,
    phenotypes: dict[tuple[str, str], _DiseasePhenotype],
) -> None:
    """Fold the rows of the denormalized disease_phenotype TSV into ``phenotypes``.

    Keyed by ``(mondo_id, hpo_id)``; sources accumulate and a pair is only kept as
    ``negated`` when no source asserts it as present.
    """
    reader = csv.DictReader(io.StringIO(text_value), delimiter="\t")
    for row in reader:
        subject = (row.get("subject") or "").strip()
        obj = (row.get("object") or "").strip()
        if not subject.startswith(_MONDO_PREFIX) or not obj.startswith(_HPO_PREFIX):
            continue
        negated = (row.get("negated") or "").strip().lower() == "true"
        key = (subject, obj)
        record = phenotypes.get(key)
        if record is None:
            record = _DiseasePhenotype(
                mondo_id=subject,
                disease_label=(row.get("subject_label") or "").strip(),
                hpo_id=obj,
                phenotype_label=(row.get("object_label") or "").strip(),
            )
            phenotypes[key] = record
        record.negated = record.negated and negated
        source = _strip_prefix(row.get("primary_knowledge_source") or "")
        if source:
            record.sources.add(source)
        if not record.disease_label:
            record.disease_label = (row.get("subject_label") or "").strip()
        if not record.phenotype_label:
            record.phenotype_label = (row.get("object_label") or "").strip()


async def _replace_disease_phenotype_rows(
    session: AsyncSession,
    *,
    phenotypes: Iterable[_DiseasePhenotype],
    release_version: str | None,
    now: datetime,
    commit: bool = True,
) -> int:
    rows = [
        {
            "mondo_id": record.mondo_id,
            "disease_label": record.disease_label or None,
            "hpo_id": record.hpo_id,
            "phenotype_label": record.phenotype_label or None,
            "negated": record.negated,
            "sources": json.dumps(sorted(record.sources)),
            "release_version": release_version,
            "updated_at": now,
        }
        for record in phenotypes
    ]

    await session.execute(text("DELETE FROM monarch_disease_phenotype"))
    if rows:
        # Chunked to keep the executemany parameter set bounded (~265k rows).
        chunk = 5000
        insert = text(
            """
            INSERT INTO monarch_disease_phenotype (
                mondo_id,
                disease_label,
                hpo_id,
                phenotype_label,
                negated,
                sources,
                release_version,
                updated_at
            )
            VALUES (
                :mondo_id,
                :disease_label,
                :hpo_id,
                :phenotype_label,
                :negated,
                CAST(:sources AS jsonb),
                :release_version,
                :updated_at
            )
            """
        )
        for start in range(0, len(rows), chunk):
            await session.execute(insert, rows[start : start + chunk])
    if commit:
        await session.commit()
    return len(rows)


async def refresh_monarch_disease_phenotype(
    session: AsyncSession,
    *,
    release_version: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Download, parse, and replace the Monarch disease -> phenotype table."""
    started_at = datetime.now(timezone.utc)
    if release_version is None:
        release_version = await _fetch_release_version()

    phenotypes: dict[tuple[str, str], _DiseasePhenotype] = {}
    text_value = await _download_gzip_tsv(MONARCH_DISEASE_PHENOTYPE_FILE)
    parse_disease_phenotype_tsv(text_value, phenotypes=phenotypes)

    records = list(phenotypes.values())
    written = await _replace_disease_phenotype_rows(
        session,
        phenotypes=records,
        release_version=release_version,
        now=started_at,
        commit=commit,
    )

    completed_at = datetime.now(timezone.utc)
    summary = {
        "release_version": release_version,
        "disease_phenotype_pairs": written,
        "phenotype_diseases": len({record.mondo_id for record in records}),
        "phenotypes": len({record.hpo_id for record in records}),
        "excluded_phenotype_pairs": sum(1 for record in records if record.negated),
        "completed_at": completed_at,
        "duration_seconds": (completed_at - started_at).total_seconds(),
    }
    logger.info(
        "Monarch disease-phenotype refresh complete: %s pairs across %s diseases (release %s)",
        summary["disease_phenotype_pairs"],
        summary["phenotype_diseases"],
        release_version,
    )
    return summary


async def refresh_monarch(session: AsyncSession) -> dict[str, Any]:
    """Refresh all Monarch tables (gene -> disease and disease -> phenotype).

    Fetches the release version once and shares it across both refreshes so the
    tables stay consistent. Returns a merged summary.
    """
    started_at = datetime.now(timezone.utc)
    release_version = await _fetch_release_version()

    # Stage both table swaps in one transaction so a failure can't leave the tables on
    # mismatched releases (gene_disease new, disease_phenotype old/empty).
    gene_disease = await refresh_monarch_gene_disease(
        session, release_version=release_version, commit=False
    )
    disease_phenotype = await refresh_monarch_disease_phenotype(
        session, release_version=release_version, commit=False
    )
    await session.commit()
    # The information-content map is derived from disease_phenotype; drop the cache so
    # the next scoring request recomputes it against the new release.
    reset_information_content_cache()

    completed_at = datetime.now(timezone.utc)
    summary = {
        **gene_disease,
        **disease_phenotype,
        "files_loaded": gene_disease.get("files_loaded", 0) + 1,
        "completed_at": completed_at,
        "duration_seconds": (completed_at - started_at).total_seconds(),
    }
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


async def family_observed_phenotype_closure(
    session: AsyncSession, *, family_uuid: str
) -> set[str]:
    """Return the set of HPO ids that count as observed for a family.

    This is the family's *present* annotations plus all their ancestors, so a
    disease's general expected phenotype matches when the patient has that term or
    any more specific descendant of it.
    """
    present_result = await session.execute(
        text(
            """
            SELECT DISTINCT hpo_id
            FROM individual_hpo
            WHERE family_id = CAST(:family_uuid AS uuid)
              AND status = 'present'
            """
        ),
        {"family_uuid": family_uuid},
    )
    present = {row["hpo_id"] for row in present_result.mappings().all()}
    if not present:
        return set()

    closure_result = await session.execute(
        text(
            """
            SELECT DISTINCT ancestor_id
            FROM hpo_closure
            WHERE hpo_id = ANY(:present)
            """
        ),
        {"present": list(present)},
    )
    observed = {row["ancestor_id"] for row in closure_result.mappings().all()}
    observed.update(present)  # ensure exact terms count even without self-closure rows
    return observed


async def summarize_disease_phenotypes(
    session: AsyncSession,
    *,
    mondo_ids: Iterable[str],
    observed_closure: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Per-disease expected-phenotype summary for the given MONDO ids.

    Returns ``{mondo_id: {"phenotype_count": int, "matched": [{"hpo_id", "label"}]}}``.
    ``matched`` lists the disease's expected phenotypes the patient exhibits (only
    populated when ``observed_closure`` is provided), sorted by label.
    """
    ids = list({mondo_id for mondo_id in mondo_ids if mondo_id})
    summary: dict[str, dict[str, Any]] = {
        mondo_id: {"phenotype_count": 0, "matched": []} for mondo_id in ids
    }
    if not ids:
        return summary

    result = await session.execute(
        text(
            """
            SELECT mondo_id, hpo_id, phenotype_label
            FROM monarch_disease_phenotype
            WHERE mondo_id = ANY(:ids)
              AND negated = FALSE
            """
        ),
        {"ids": ids},
    )
    for row in result.mappings().all():
        entry = summary[row["mondo_id"]]
        entry["phenotype_count"] += 1
        if observed_closure and row["hpo_id"] in observed_closure:
            entry["matched"].append(
                {"hpo_id": row["hpo_id"], "label": row["phenotype_label"]}
            )
    for entry in summary.values():
        entry["matched"].sort(key=lambda item: (item["label"] or item["hpo_id"]).lower())
    return summary
