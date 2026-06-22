"""Wire the monogenic NIPT analysis core to family data (Phase 5).

Resolves the NIPT trio for a family, loads the joined father + cfDNA calls from
ClickHouse, turns them into ``NiptSiteObservation`` rows, and runs the pure
analysis core. The site-building helpers are pure (and unit-tested); only
``run_family_nipt_analysis`` performs I/O.

See docs/monogenic-nipt.md and docs/monogenic-nipt-classification.md.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .clickhouse_family_variants import (
    SmallVariantCall,
    SmallVariantRecord,
    _fetch_small_variant_rows,
)
from .family_metadata_context import FamilyMetadataContext, build_family_metadata_context
from .family_variant_filters import SmallVariantQueryFilters
from .metadata_service import CurrentUser, get_family_record
from .nipt import resolve_nipt_trio
from .nipt_analysis import (
    NiptAnalysisResult,
    NiptQualityThresholds,
    NiptSiteObservation,
    run_nipt_analysis,
)

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


async def _load_family_records(context: FamilyMetadataContext) -> list[SmallVariantRecord]:
    # No filters: the summary spans the whole family cohort (FF estimation needs
    # every category-7 site and the category counts are cohort-wide).
    filters = SmallVariantQueryFilters(page=1, page_size=100)
    return await _fetch_small_variant_rows(context, filters, limit=None)


async def run_family_nipt_analysis(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None = None,
    qc: NiptQualityThresholds | None = None,
    external_ff: float | None = None,
) -> NiptAnalysisResult:
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
    records = await _load_family_records(context)
    sites = build_nipt_observations(
        records,
        father_sample_id=trio.father_sample_id,
        cfdna_sample_id=trio.cfdna_sample_id,
    )
    return run_nipt_analysis(sites, qc or NiptQualityThresholds(), external_ff=external_ff)
