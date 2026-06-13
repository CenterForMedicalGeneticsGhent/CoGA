"""Per-marker parent-of-origin for GLIMPSE2-imputed variants.

For each child in a trio, computes which parental homolog (0/1) was inherited at
each informative marker, oriented to match the stored haplotype blocks. Every
informative imputed site is returned as its own raw call — no binning, smoothing,
or majority-voting.

This is deliberate: the phased-marker track is the *diagnostic* layer. Its purpose
is to expose where the imputed phasing is noisy or uncertain about the haplotypes
(isolated switches, jitter at recombination boundaries). The "cleaned" view is the
Haplotype block track; collapsing the raw calls here would hide exactly the signal
this track exists to show.

The Mendelian classifier and the affected-child orientation are reused verbatim
from the haplotype block builder so the homolog indices line up with the stored
blocks (and therefore the Haplotype track's colours + disease overlay).
"""
from __future__ import annotations

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
# an unusually large family's full-chromosome view. This bounds the ClickHouse
# query only; the markers it returns are emitted raw, one point per site.
PHASED_FETCH_LIMIT = 500_000


def compute_phased_markers(
    rows: list[tuple[int, list[str], list[str]]],
    *,
    father: str,
    mother: str,
    children: list[str],
    affected: set[str],
) -> dict[str, list[PhasedMarker]]:
    """Per child, return the oriented parental homolog (0/1) inherited at every
    informative marker — one PhasedMarker per imputed site, raw.

    No binning or majority-voting: isolated single-marker switches are preserved
    so the track surfaces phasing noise/uncertainty rather than hiding it. The
    only transform applied is the affected-child orientation flip, which lines the
    homolog indices up with the stored haplotype blocks (so this track's colours +
    disease overlay match the Haplotype block track)."""
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

    def orient(value: int | None, flip: bool) -> int | None:
        if value is None:
            return None
        return (1 - value) if flip else value

    result: dict[str, list[PhasedMarker]] = {}
    for child in children:
        result[child] = [
            PhasedMarker(
                pos=pos,
                paternal=orient(paternal, father_flip),
                maternal=orient(maternal, mother_flip),
            )
            for pos, paternal, maternal in raw[child]
        ]
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
    markers_by_child = compute_phased_markers(
        rows,
        father=father,
        mother=mother,
        children=children,
        affected=set(context.affected_sample_names),
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
