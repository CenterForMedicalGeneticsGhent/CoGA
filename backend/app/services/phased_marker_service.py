"""Per-marker parent-of-origin for GLIMPSE2-imputed variants.

For each child in a trio, computes which parental homolog (0/1) was inherited at
each informative marker, binned across the requested region and oriented to match
the stored haplotype blocks. This reveals recombination/haplotype switches at far
finer resolution than the smoothed blocks (which need ~50 markers / 500 kb to
switch), while keeping the payload bounded regardless of imputed-variant density.

The Mendelian classifier and the affected-child orientation are reused verbatim
from the haplotype block builder so the homolog indices line up with the stored
blocks (and therefore the Haplotype track's colours + disease overlay).
"""
from __future__ import annotations

import math

from ..schemas import PhasedMarker, PhasedMarkerResponse, PhasedMarkerSample
from .clickhouse_family_variants import fetch_imputed_phased_genotypes
from .family_metadata_context import FamilyMetadataContext
from .variant_upload_service import (
    _parent_sample_names,
    _phased_haplotype_alleles,
    _transmitted_parent_haplotype,
)

# Fetch ceiling — covers a whole (largest) chromosome of family-scoped imputed
# sites with headroom (~275k on chr2 here); truncation only affects the tail of
# an unusually large family's full-chromosome view.
PHASED_FETCH_LIMIT = 500_000
# Output bins per child — the track is grouped into at most this many points,
# which both bounds the payload/render and (by giving each bin many markers in a
# dense window) denoises single-marker GLIMPSE2 phasing errors. When markers are
# sparse (zoomed in) each bin is a single marker, so resolution is preserved.
PHASED_MAX_BINS = 200


def compute_phased_marker_bins(
    rows: list[tuple[int, list[str], list[str]]],
    *,
    father: str,
    mother: str,
    children: list[str],
    affected: set[str],
    start: int,
    end: int,
    max_bins: int = PHASED_MAX_BINS,
) -> dict[str, list[PhasedMarker]]:
    """Per child, return the majority (oriented) parental homolog over groups of
    K consecutive informative markers, where K scales with density so each bin
    holds enough markers for a robust majority. Bounded to <= max_bins per child.

    Index-binning (rather than fixed genomic bins) keeps a constant number of
    markers per bin regardless of how the imputed sites cluster, so the majority
    reliably suppresses isolated phasing-switch errors while a real recombination
    — a run of the other homolog — still flips the colour."""
    raw: dict[str, list[tuple[int, int | None, int | None]]] = {child: [] for child in children}
    father_counts = [0, 0]
    mother_counts = [0, 0]

    for pos, sample_ids, gts in rows:
        gt = dict(zip(sample_ids, gts))
        father_alleles = _phased_haplotype_alleles(gt.get(father))
        mother_alleles = _phased_haplotype_alleles(gt.get(mother))
        if father_alleles is None or mother_alleles is None:
            continue
        for child in children:
            child_alleles = _phased_haplotype_alleles(gt.get(child))
            if child_alleles is None:
                continue
            paternal_raw = _transmitted_parent_haplotype(father_alleles, mother_alleles, child_alleles)
            maternal_raw = _transmitted_parent_haplotype(mother_alleles, father_alleles, child_alleles)
            if paternal_raw is None and maternal_raw is None:
                continue
            # `_transmitted_parent_haplotype` returns the homolog index as a string.
            paternal = int(paternal_raw) if paternal_raw is not None else None
            maternal = int(maternal_raw) if maternal_raw is not None else None
            raw[child].append((pos, paternal, maternal))
            if child in affected:
                if paternal is not None:
                    father_counts[paternal] += 1
                if maternal is not None:
                    mother_counts[maternal] += 1

    father_flip = father_counts[0] > father_counts[1]
    mother_flip = mother_counts[0] > mother_counts[1]

    def majority(values: list[int], flip: bool) -> int | None:
        if not values:
            return None
        ones = sum(values)
        value = 1 if ones * 2 > len(values) else 0
        return (1 - value) if flip else value

    result: dict[str, list[PhasedMarker]] = {}
    for child in children:
        markers = raw[child]
        result[child] = []
        if not markers:
            continue
        group_size = max(1, math.ceil(len(markers) / max_bins))
        for offset in range(0, len(markers), group_size):
            group = markers[offset : offset + group_size]
            paternal = majority([p for _, p, _ in group if p is not None], father_flip)
            maternal = majority([m for _, _, m in group if m is not None], mother_flip)
            if paternal is None and maternal is None:
                continue
            result[child].append(
                PhasedMarker(pos=group[len(group) // 2][0], paternal=paternal, maternal=maternal)
            )
    return result


async def get_family_phased_markers_response(
    context: FamilyMetadataContext,
    *,
    chr: str,
    start: int | None,
    end: int | None,
) -> PhasedMarkerResponse:
    father, mother = _parent_sample_names(context)
    if (
        father is None
        or mother is None
        or not context.assembly_name
        or start is None
        or end is None
        or end <= start
    ):
        return PhasedMarkerResponse(chr=chr, start=start, end=end, samples=[])

    children = [name for name in context.sample_name_to_uuid if name not in {father, mother}]
    if not children:
        return PhasedMarkerResponse(chr=chr, start=start, end=end, samples=[])

    rows = await fetch_imputed_phased_genotypes(
        context, chrom=chr, start=int(start), end=int(end), limit=PHASED_FETCH_LIMIT
    )
    markers_by_child = compute_phased_marker_bins(
        rows,
        father=father,
        mother=mother,
        children=children,
        affected=set(context.affected_sample_names),
        start=int(start),
        end=int(end),
    )
    return PhasedMarkerResponse(
        chr=chr,
        start=start,
        end=end,
        samples=[
            PhasedMarkerSample(sample=child, markers=markers_by_child.get(child, []))
            for child in children
        ],
    )
