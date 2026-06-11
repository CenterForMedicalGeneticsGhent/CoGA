"""Global Small Variant Explorer endpoints.

A variant-centric, cross-project aggregation view over small variants. See
``app/services/variant_explorer_service.py`` for the aggregation strategy.
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.postgres import get_postgres_session
from ..dependencies import get_current_user
from ..schemas import (
    GlobalVariantPageOut,
    SmallVariantTagDefinitionOut,
    VariantCarriersOut,
    VariantExplorerAssemblyOut,
)
from ..services.metadata_service import CurrentUser, _is_admin_user
from ..services.small_variant_review_pg import list_small_variant_tag_definitions
from ..services.variant_explorer_service import (
    GlobalVariantFilters,
    get_variant_carriers,
    list_explorer_assemblies,
    list_explorer_samples,
    search_global_small_variants,
    _accessible_project_rows,
)

router = APIRouter(prefix="/variant-explorer", tags=["variant-explorer"])

_GENOTYPE_MODES = {"het", "hom", "het_hom"}


def _parse_sample_genotype_filters(values: List[str]) -> list[tuple[str, str]]:
    """Parse ``sampleId:mode`` query values into (sample, mode) pairs."""

    parsed: list[tuple[str, str]] = []
    for entry in values:
        text_value = str(entry or "").strip()
        if not text_value:
            continue
        sample, _, mode = text_value.partition(":")
        sample = sample.strip()
        mode = mode.strip().lower() or "het_hom"
        if not sample:
            continue
        if mode not in _GENOTYPE_MODES:
            mode = "het_hom"
        parsed.append((sample, mode))
    return parsed


@router.get("/assemblies", response_model=List[VariantExplorerAssemblyOut])
async def list_assemblies(
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[VariantExplorerAssemblyOut]:
    return await list_explorer_assemblies(session, user)


@router.get("/samples", response_model=List[str])
async def list_samples(
    assembly_id: str | None = None,
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[str]:
    return await list_explorer_samples(session, user, assembly_id=assembly_id)


@router.get("/small-variant-tags", response_model=List[SmallVariantTagDefinitionOut])
async def list_explorer_tag_definitions(
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[SmallVariantTagDefinitionOut]:
    if _is_admin_user(user):
        return await list_small_variant_tag_definitions(
            session, family_uuid="", project_ids=[], include_all_project_tags=True
        )
    rows = await _accessible_project_rows(session, user)
    project_ids = sorted({row["project_id"] for row in rows})
    return await list_small_variant_tag_definitions(
        session, family_uuid="", project_ids=project_ids
    )


@router.get("/small-variants", response_model=GlobalVariantPageOut)
async def list_global_small_variants(
    assembly_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = "total_samples",
    order: str = "desc",
    chr: str | None = None,
    start: int | None = None,
    end: int | None = None,
    type: str | None = None,
    gene: str | None = None,
    impact: List[str] = Query(default_factory=list),
    effect: List[str] = Query(default_factory=list),
    clinvar: List[str] = Query(default_factory=list),
    exclude_clinvar: List[str] = Query(default_factory=list, alias="exclude_clinvar"),
    rsid: str | None = None,
    hgvsc: str | None = None,
    hgvsp: str | None = None,
    canonical_only: bool = False,
    mane_only: bool = False,
    lof_only: bool = False,
    max_gnomad_af: float | None = None,
    max_gnomad_exomes_af: float | None = None,
    max_gnomad_genomes_af: float | None = None,
    max_gnomad_popmax_af: float | None = None,
    max_topmed_af: float | None = None,
    max_gnomad_ac: int | None = None,
    max_gnomad_hom_count: int | None = None,
    max_gnomad_hemi_count: int | None = None,
    min_cadd: float | None = None,
    min_revel: float | None = None,
    min_spliceai: float | None = None,
    sift: str | None = None,
    polyphen: str | None = None,
    classification: List[str] = Query(default_factory=list),
    review_tag: List[str] = Query(default_factory=list, alias="review_tag"),
    include_imputed: bool = False,
    sample_gt: List[str] = Query(default_factory=list, alias="sample_gt"),
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> GlobalVariantPageOut:
    filters = GlobalVariantFilters(
        chromosome=chr,
        start=start,
        end=end,
        variant_type=type,
        gene=gene,
        impacts=impact,
        effects=effect,
        clinvar=clinvar,
        exclude_clinvar=exclude_clinvar,
        rsid=rsid,
        hgvsc=hgvsc,
        hgvsp=hgvsp,
        canonical_only=canonical_only,
        mane_only=mane_only,
        lof_only=lof_only,
        max_gnomad_af=max_gnomad_af,
        max_gnomad_exomes_af=max_gnomad_exomes_af,
        max_gnomad_genomes_af=max_gnomad_genomes_af,
        max_gnomad_popmax_af=max_gnomad_popmax_af,
        max_topmed_af=max_topmed_af,
        max_gnomad_ac=max_gnomad_ac,
        max_gnomad_hom_count=max_gnomad_hom_count,
        max_gnomad_hemi_count=max_gnomad_hemi_count,
        min_cadd=min_cadd,
        min_revel=min_revel,
        min_spliceai=min_spliceai,
        sift=sift,
        polyphen=polyphen,
        classifications=classification,
        review_tags=review_tag,
        include_imputed=include_imputed,
        sample_genotype_filters=_parse_sample_genotype_filters(sample_gt),
    )
    return await search_global_small_variants(
        session,
        user=user,
        filters=filters,
        assembly_id=assembly_id,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )


@router.get("/small-variants/{variant_key}/carriers", response_model=VariantCarriersOut)
async def list_variant_carriers(
    variant_key: int,
    assembly_id: str | None = None,
    genotype: str | None = None,
    include_imputed: bool = False,
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> VariantCarriersOut:
    return await get_variant_carriers(
        session,
        user=user,
        variant_key=variant_key,
        assembly_id=assembly_id,
        genotype=genotype,
        include_imputed=include_imputed,
    )
