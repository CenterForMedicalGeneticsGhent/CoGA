"""Wire the monogenic NIPT analysis core to family data (Phase 5).

Resolves the NIPT trio for a family, loads the joined father + cfDNA calls from
ClickHouse, turns them into ``NiptSiteObservation`` rows, and runs the pure
analysis core. The site-building helpers are pure (and unit-tested); only
``run_family_nipt_analysis`` performs I/O.

See docs/monogenic-nipt.md and docs/monogenic-nipt-classification.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .clickhouse_family_variants import (
    PanelFilterConstraints,
    SmallVariantCall,
    SmallVariantRecord,
    _fetch_panel_constraints,
    _fetch_small_variant_rows,
)
from .family_metadata_context import FamilyMetadataContext, build_family_metadata_context
from .family_variant_filters import SmallVariantQueryFilters
from .metadata_service import CurrentUser, get_family_record
from .nipt import NiptTrio, nipt_assay_key, resolve_nipt_trio
from .nipt_artifact_pg import load_nipt_artifact_ids
from .nipt_analysis import (
    FetalFractionEstimate,
    NiptAnalysisResult,
    NiptClassification,
    NiptQualityThresholds,
    NiptSiteObservation,
    classify_site,
    estimate_fetal_fraction,
    run_nipt_analysis,
)

# Bounds the in-memory classification for the variant list. Clinical use always
# narrows by gene/panel/region, so this is a safety cap, not a normal limit.
_NIPT_VARIANT_FETCH_LIMIT = 5000

# NIPT inheritance presets that map to a set of categories. recessive_at_risk
# needs cross-variant gene pairing and is deferred to the clinical-filter phase.
_INHERITANCE_CATEGORIES: dict[str, frozenset[int]] = {
    "de_novo": frozenset({1}),
    "paternal_dominant": frozenset({7}),
    "maternal_dominant": frozenset({3, 4}),
}

_AUTOSOMES = {str(index) for index in range(1, 23)}


def _is_autosomal(chrom: str) -> bool:
    return chrom.lower().removeprefix("chr") in _AUTOSOMES


def _gt_alleles(gt: str | None) -> list[str]:
    if not gt:
        return []
    return [token for token in gt.replace("|", "/").split("/") if token not in ("", ".")]


def derive_father_state(call: SmallVariantCall | None) -> str:
    """Map a germline genotype to hom_ref / het / hom_alt / missing."""
    alleles = _gt_alleles(call.gt) if call is not None else []
    if not alleles:
        return "missing"
    alt_count = sum(1 for allele in alleles if allele != "0")
    if alt_count == 0:
        return "hom_ref"
    if len(alleles) >= 2 and alt_count >= len(alleles):
        return "hom_alt"
    return "het"


def _cfdna_alt_reads(call: SmallVariantCall) -> int | None:
    if call.ad and len(call.ad) > 1:
        return call.ad[1]
    return None


def _cfdna_vaf(call: SmallVariantCall, alt_reads: int | None) -> float | None:
    if call.af:
        return call.af[0]
    if alt_reads is not None and call.dp:
        return alt_reads / call.dp
    return None


def build_nipt_observations(
    records: list[SmallVariantRecord],
    *,
    father_sample_id: str,
    cfdna_sample_id: str,
) -> list[NiptSiteObservation]:
    """Turn family variant records into per-site NIPT observations.

    Each record is expected to carry per-sample calls; the cfDNA sample provides
    the signal we classify and the father sample provides the genotype that
    prunes candidate categories. Sites without a cfDNA call are skipped.
    """
    sites: list[NiptSiteObservation] = []
    for record in records:
        calls = {call.sample: call for call in record.calls}
        cf_call = calls.get(cfdna_sample_id)
        if cf_call is None:
            continue
        father_call = calls.get(father_sample_id)
        alt_reads = _cfdna_alt_reads(cf_call)
        if alt_reads is not None:
            present = alt_reads > 0
        else:
            present = any(allele != "0" for allele in _gt_alleles(cf_call.gt))
        sites.append(
            NiptSiteObservation(
                variant_id=record.variant_id,
                chrom=record.chr,
                pos=record.start,
                is_autosomal=_is_autosomal(record.chr),
                cf_present=present,
                cf_dp=cf_call.dp,
                cf_alt_reads=alt_reads,
                cf_vaf=_cfdna_vaf(cf_call, alt_reads),
                cf_qual=record.qual,
                father_state=derive_father_state(father_call),
                father_dp=father_call.dp if father_call is not None else None,
                father_qual=None,
            )
        )
    return sites


@dataclass(slots=True)
class NiptClassifiedVariant:
    """A family variant record paired with its NIPT classification."""

    record: SmallVariantRecord
    classification: NiptClassification


@dataclass(slots=True)
class NiptVariantsResult:
    fetal_fraction: FetalFractionEstimate
    total: int
    variants: list[NiptClassifiedVariant]


async def _load_family_records(context: FamilyMetadataContext) -> list[SmallVariantRecord]:
    # No filters: the summary/FF estimation spans the whole family cohort (FF
    # needs every category-7 site and the category counts are cohort-wide).
    filters = SmallVariantQueryFilters(page=1, page_size=100)
    return await _fetch_small_variant_rows(context, filters, limit=None)


async def _resolve_trio_and_context(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None,
) -> tuple[NiptTrio, FamilyMetadataContext, str]:
    family = await get_family_record(session, family_id, user)
    trio = resolve_nipt_trio(family)
    if trio is None:
        raise HTTPException(
            status_code=400,
            detail="Family is not configured for monogenic NIPT analysis",
        )
    context = await build_family_metadata_context(
        session,
        family_identifier=family_id,
        user=user,
        project_id=project_id,
    )
    return trio, context, nipt_assay_key(family, trio)


async def _load_artifact_lookup(
    session: AsyncSession, context: FamilyMetadataContext, assay_key: str
):
    artifact_ids = await load_nipt_artifact_ids(
        session, assembly_id=context.assembly_id, assay_key=assay_key
    )
    return artifact_ids.__contains__


def _family_sites(
    records: list[SmallVariantRecord], trio: NiptTrio
) -> list[NiptSiteObservation]:
    return build_nipt_observations(
        records,
        father_sample_id=trio.father_sample_id,
        cfdna_sample_id=trio.cfdna_sample_id,
    )


async def run_family_nipt_analysis(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None = None,
    qc: NiptQualityThresholds | None = None,
    external_ff: float | None = None,
) -> NiptAnalysisResult:
    trio, context, assay_key = await _resolve_trio_and_context(
        session, family_id=family_id, user=user, project_id=project_id
    )
    artifact_lookup = await _load_artifact_lookup(session, context, assay_key)
    records = await _load_family_records(context)
    sites = _family_sites(records, trio)
    return run_nipt_analysis(
        sites,
        qc or NiptQualityThresholds(),
        artifact_lookup=artifact_lookup,
        external_ff=external_ff,
    )


def _build_nipt_query_filters(query_filters: dict) -> SmallVariantQueryFilters:
    """Build a SmallVariantQueryFilters for the NIPT-relevant filter subset."""
    return SmallVariantQueryFilters(
        page=1,
        page_size=100,
        chromosome=query_filters.get("chr"),
        start=query_filters.get("start"),
        end=query_filters.get("end"),
        intervals=query_filters.get("intervals"),
        gene=query_filters.get("gene"),
        exclude_gene=query_filters.get("exclude_gene"),
        impact=query_filters.get("impact") or [],
        effect=query_filters.get("effect") or [],
        max_gnomad_af=query_filters.get("max_gnomad_af"),
        max_gnomad_popmax_af=query_filters.get("max_gnomad_popmax_af"),
        min_cadd=query_filters.get("min_cadd"),
        min_revel=query_filters.get("min_revel"),
        min_spliceai=query_filters.get("min_spliceai"),
        canonical_only=bool(query_filters.get("canonical_only", False)),
        mane_only=bool(query_filters.get("mane_only", False)),
        lof_only=bool(query_filters.get("lof_only", False)),
        panel_id=query_filters.get("panel_id"),
    )


async def get_family_nipt_variants(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None = None,
    query_filters: dict | None = None,
    categories: list[int] | None = None,
    min_confidence: float | None = None,
    inheritance: str | None = None,
    page: int = 1,
    page_size: int = 100,
    qc: NiptQualityThresholds | None = None,
    external_ff: float | None = None,
) -> NiptVariantsResult:
    qc = qc or NiptQualityThresholds()

    wanted = set(categories or [])
    if inheritance:
        preset = _INHERITANCE_CATEGORIES.get(inheritance)
        if preset is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported NIPT inheritance preset: {inheritance}",
            )
        wanted = (wanted & set(preset)) if wanted else set(preset)

    trio, context, assay_key = await _resolve_trio_and_context(
        session, family_id=family_id, user=user, project_id=project_id
    )
    artifact_ids = await load_nipt_artifact_ids(
        session, assembly_id=context.assembly_id, assay_key=assay_key
    )

    # Fetal fraction is estimated cohort-wide (the FF/2 category-7 sites are
    # rarely inside the clinical filter), then the filtered subset is classified
    # against that FF.
    cohort_sites = _family_sites(await _load_family_records(context), trio)
    ff_estimate = estimate_fetal_fraction(cohort_sites, qc, external_ff=external_ff)

    filters = _build_nipt_query_filters(query_filters or {})
    panel_constraints = PanelFilterConstraints()
    if filters.panel_id:
        panel_constraints = await _fetch_panel_constraints(
            session, filters.panel_id, assembly_id=context.assembly_id
        )
        if not panel_constraints.genes and not panel_constraints.regions:
            return NiptVariantsResult(fetal_fraction=ff_estimate, total=0, variants=[])

    records = await _fetch_small_variant_rows(
        context,
        filters,
        panel_constraints=panel_constraints,
        limit=_NIPT_VARIANT_FETCH_LIMIT,
    )
    observations = {
        observation.variant_id: observation for observation in _family_sites(records, trio)
    }

    classified: list[NiptClassifiedVariant] = []
    for record in records:
        if record.variant_id in artifact_ids:
            continue
        observation = observations.get(record.variant_id)
        if observation is None:
            continue
        classification = classify_site(observation, ff_estimate, qc)
        if wanted and classification.category not in wanted:
            continue
        if min_confidence is not None and (
            classification.category is None or classification.confidence < min_confidence
        ):
            continue
        classified.append(NiptClassifiedVariant(record=record, classification=classification))

    total = len(classified)
    offset = max(0, (page - 1) * page_size)
    page_items = classified[offset : offset + page_size]
    return NiptVariantsResult(fetal_fraction=ff_estimate, total=total, variants=page_items)
