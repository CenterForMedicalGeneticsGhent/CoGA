"""Loader + pedigree resolution for sample-integrity QC.

Fetches a bounded, genome-spread sample of GLIMPSE2-imputed genotypes (the same
source the haplotype track uses), parses them into the pure ``sample_integrity_qc``
representation, resolves the pedigree's assertions, and runs the QC. A sample
swap is genome-wide, so a few autosomes plus chrX are ample signal.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .clickhouse_family_variants import fetch_imputed_phased_genotypes
from .family_metadata_context import FamilyMetadataContext, build_family_metadata_context
from .haplotype_lineage_service import build_pedigree
from .metadata_service import CurrentUser
from .sample_integrity_qc import (
    Genotype,
    PedigreeSpec,
    SampleIntegrityReport,
    evaluate_sample_integrity,
)
from .variant_upload_service import _phased_haplotype_alleles

# A handful of autosomes spread across the genome (robust to one being absent)
# plus chrX for sex. Capped per chromosome so the QC stays cheap.
QC_AUTOSOMES: tuple[str, ...] = ("1", "2", "3")
QC_SITES_PER_CHROM = 30_000
QC_X_CHROM = "X"
QC_X_SITES = 20_000
_WHOLE_CHROM_END = 300_000_000  # larger than any human chromosome


def _parse_genotype(gt: str | None) -> Genotype | None:
    alleles = _phased_haplotype_alleles(gt)
    if alleles is None:
        return None
    a, b = alleles
    if not (a.isdigit() and b.isdigit()):
        return None
    return (int(a), int(b))


async def _load_chromosome(
    context: FamilyMetadataContext, chrom: str, limit: int, samples: list[str]
) -> dict[str, list[Genotype | None]]:
    rows = await fetch_imputed_phased_genotypes(
        context, chrom=chrom, start=0, end=_WHOLE_CHROM_END, limit=limit
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
    spec = _build_pedigree_spec(context)
    samples = sorted(context.sample_name_to_uuid)
    if not context.assembly_name or not samples:
        return evaluate_sample_integrity({}, {}, spec)

    autosomal: dict[str, list[Genotype | None]] = {sample: [] for sample in samples}
    for chrom in QC_AUTOSOMES:
        part = await _load_chromosome(context, chrom, QC_SITES_PER_CHROM, samples)
        for sample in samples:
            autosomal[sample].extend(part[sample])

    x_genotypes = await _load_chromosome(context, QC_X_CHROM, QC_X_SITES, samples)
    return evaluate_sample_integrity(autosomal, x_genotypes, spec)
