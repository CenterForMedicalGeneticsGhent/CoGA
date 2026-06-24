"""Loader, application detection and pedigree resolution for sample-integrity QC.

CoGA runs several applications with different input modalities, so a single
generic QC is wrong. This layer resolves the application (long-read WGS family /
shallow-WGS PGT / monogenic NIPT / carrier couple (BEGECS) / single targeted),
picks the matching genotype callset (clair3 SNVs, GLIMPSE2 imputed, …), runs only
the checks that make sense for it, and — for NIPT — derives paternity from the
cfDNA classification instead of genotype relatedness. The QC maths is in the pure
``sample_integrity_qc`` module.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .clickhouse_family_variants import (
    fetch_family_variant_sources,
    fetch_imputed_phased_genotypes,
)
from .family_metadata_context import FamilyMetadataContext, build_family_metadata_context
from .haplotype_lineage_service import build_pedigree
from .metadata_service import CurrentUser, get_family_record
from .nipt import resolve_nipt_trio
from .sample_integrity_qc import (
    FetalSexCheck,
    Genotype,
    PaternityCheck,
    PedigreeSpec,
    SampleIntegrityReport,
    evaluate_fetal_sex,
    evaluate_paternity,
    evaluate_sample_integrity,
    profile_for,
    resolve_application,
)

QC_AUTOSOMES: tuple[str, ...] = ("1", "2", "3")
QC_SITES_PER_CHROM = 30_000
QC_X_CHROM = "X"
QC_X_SITES = 20_000
_WHOLE_CHROM_END = 300_000_000

# Genotype callsets preferred for QC, best first: real SNV calls before imputed.
_SOURCE_PREFERENCE = ("clair3", "glimpse2")


def _parse_genotype(gt: str | None) -> Genotype | None:
    """Parse a phased (``0|1``) or unphased (``0/1``) diploid GT; None if missing."""
    if not gt:
        return None
    sep = "|" if "|" in gt else "/" if "/" in gt else None
    if sep is None:
        return None
    a, b = gt.split(sep, 1)
    if not (a.isdigit() and b.isdigit()):
        return None
    return (int(a), int(b))


def _choose_genotype_source(available: list[str]) -> str | None:
    """Pick the QC genotype source from the family's callsets (clair3 > glimpse2)."""
    lowered = [s.lower() for s in available]
    for preferred in _SOURCE_PREFERENCE:
        for raw, low in zip(available, lowered):
            if preferred in low:
                return raw
    return available[0] if available else None


async def _load_chromosome(
    context: FamilyMetadataContext,
    chrom: str,
    limit: int,
    samples: list[str],
    source: str,
) -> dict[str, list[Genotype | None]]:
    rows = await fetch_imputed_phased_genotypes(
        context, chrom=chrom, start=0, end=_WHOLE_CHROM_END, limit=limit, source=source
    )
    arrays: dict[str, list[Genotype | None]] = {sample: [] for sample in samples}
    for _pos, _ref, _alt, sample_ids, gts in rows:
        gt_by_sample = dict(zip(sample_ids, gts))
        for sample in samples:
            arrays[sample].append(_parse_genotype(gt_by_sample.get(sample)))
    return arrays


def _build_pedigree_spec(context: FamilyMetadataContext) -> PedigreeSpec:
    recorded_sex = {
        str(row["sample_id"]): str(row.get("sex") or "")
        for row in context.sample_rows
        if row.get("sample_id")
    }
    pedigree = build_pedigree(context.sample_rows, context.relationship_rows)
    return PedigreeSpec(recorded_sex=recorded_sex, parents_of=pedigree.parents_of)


async def _nipt_checks(
    session: AsyncSession, *, family, family_id: str, user: CurrentUser, project_id: str | None
) -> tuple[PaternityCheck | None, FetalSexCheck | None]:
    """NIPT cfDNA integrity: paternity (cat 7/8) and fetal sex (paternal X)."""
    trio = resolve_nipt_trio(family)
    if trio is None:
        return None, None
    # Imported lazily: nipt_service pulls in the heavy analysis stack.
    from .nipt_service import run_family_nipt_analysis

    result = await run_family_nipt_analysis(
        session, family_id=family_id, user=user, project_id=project_id
    )
    paternity = evaluate_paternity(trio.father_sample_id, result.category_counts)
    fs = result.fetal_sex
    fetal_sex = evaluate_fetal_sex(
        fs.inferred, fs.x_transmitted, fs.x_not_transmitted, fs.informative_sites
    )
    return paternity, fetal_sex


async def get_family_sample_integrity_qc(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None = None,
) -> SampleIntegrityReport:
    context = await build_family_metadata_context(
        session, family_identifier=family_id, user=user, project_id=project_id
    )
    family = await get_family_record(session, family_id, user)
    analysis_type = str((getattr(family, "metadata", None) or {}).get("analysis_type") or "")

    spec = _build_pedigree_spec(context)
    pedigree = build_pedigree(context.sample_rows, context.relationship_rows)
    samples = sorted(context.sample_name_to_uuid)

    application = resolve_application(
        analysis_type=analysis_type,
        roles=pedigree.roles,
        parents_of=pedigree.parents_of,
        sample_count=len(samples),
    )
    profile = profile_for(application)

    paternity_check: PaternityCheck | None = None
    fetal_sex_check: FetalSexCheck | None = None
    if profile.run_paternity:
        paternity_check, fetal_sex_check = await _nipt_checks(
            session, family=family, family_id=family_id, user=user, project_id=project_id
        )

    autosomal: dict[str, list[Genotype | None]] = {sample: [] for sample in samples}
    x_genotypes: dict[str, list[Genotype | None]] = {sample: [] for sample in samples}
    genotype_source: str | None = None
    needs_genotypes = profile.run_sex or profile.run_relatedness or profile.run_mendelian
    if needs_genotypes and context.assembly_name and samples:
        genotype_source = _choose_genotype_source(await fetch_family_variant_sources(context))
        if genotype_source:
            for chrom in QC_AUTOSOMES:
                part = await _load_chromosome(context, chrom, QC_SITES_PER_CHROM, samples, genotype_source)
                for sample in samples:
                    autosomal[sample].extend(part[sample])
            x_genotypes = await _load_chromosome(
                context, QC_X_CHROM, QC_X_SITES, samples, genotype_source
            )

    return evaluate_sample_integrity(
        autosomal,
        x_genotypes,
        spec,
        profile=profile,
        genotype_source=genotype_source,
        paternity_check=paternity_check,
        fetal_sex_check=fetal_sex_check,
    )
