"""Per-marker phasing for GLIMPSE2-imputed variants.

For every family member, returns the value drawn on each haplotype lane at each
informative imputed site — one raw call per site, no binning/smoothing/voting:

- For a child: which parental homolog (0/1) was inherited on each side
  (paternal -> hap1, maternal -> hap2), oriented to match the stored haplotype
  blocks.
- For a parent: the alleles on their own two phased homologs (the raw per-site
  version of their haplotype blocks).

This is deliberate: the phased-marker overlay is the *diagnostic* layer. Its
purpose is to expose where the imputed phasing is noisy or uncertain about the
haplotypes (isolated switches, jitter at recombination boundaries). The "cleaned"
view is the Haplotype block track; collapsing the raw calls here would hide
exactly the signal the overlay exists to show.

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


def _allele_int(allele: str) -> int | None:
    return int(allele) if allele.isdigit() else None


def compute_phased_markers(
    rows: list[tuple[int, list[str], list[str]]],
    *,
    father: str,
    mother: str,
    children: list[str],
    affected: set[str],
) -> dict[str, list[PhasedMarker]]:
    """Per member, return the raw per-site haplotype-lane values.

    Children get the oriented parental homolog inherited on each side (hap1 =
    paternal, hap2 = maternal); parents get the alleles on their own two phased
    homologs. One PhasedMarker per imputed site — no binning or majority-voting,
    so isolated single-marker switches are preserved (the overlay surfaces phasing
    noise/uncertainty rather than hiding it). The only transform is the affected-
    child orientation flip, which lines the child homolog indices up with the
    stored haplotype blocks."""
    members = [father, mother, *children]
    child_set = set(children)
    father_counts = [0, 0]
    mother_counts = [0, 0]

    # First pass: per site, the (hap1, hap2) lane value for each member present.
    staged: list[tuple[int, dict[str, tuple[int | None, int | None]]]] = []
    for pos, sample_ids, gts in rows:
        gt = dict(zip(sample_ids, gts))
        father_alleles = _phased_haplotype_alleles(gt.get(father))
        mother_alleles = _phased_haplotype_alleles(gt.get(mother))
        if father_alleles is None or mother_alleles is None:
            continue

        lane_values: dict[str, tuple[int | None, int | None]] = {
            # Parents: the alleles on their own homologs (raw, not oriented).
            father: (_allele_int(father_alleles[0]), _allele_int(father_alleles[1])),
            mother: (_allele_int(mother_alleles[0]), _allele_int(mother_alleles[1])),
        }
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
            lane_values[child] = (paternal, maternal)
            if child in affected:
                if paternal is not None:
                    father_counts[paternal] += 1
                if maternal is not None:
                    mother_counts[maternal] += 1
        staged.append((pos, lane_values))

    father_flip = father_counts[0] > father_counts[1]
    mother_flip = mother_counts[0] > mother_counts[1]

    def orient(value: int | None, flip: bool) -> int | None:
        if value is None:
            return None
        return (1 - value) if flip else value

    result: dict[str, list[PhasedMarker]] = {member: [] for member in members}
    for pos, lane_values in staged:
        for member, (hap1, hap2) in lane_values.items():
            if member in child_set:
                hap1 = orient(hap1, father_flip)
                hap2 = orient(hap2, mother_flip)
            result[member].append(PhasedMarker(pos=pos, hap1=hap1, hap2=hap2))
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
    markers_by_member = compute_phased_markers(
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
            PhasedMarkerSample(sample=member, markers=markers_by_member.get(member, []))
            for member in [father, mother, *children]
        ],
    )
