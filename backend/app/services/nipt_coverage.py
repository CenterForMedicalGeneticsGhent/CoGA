"""On-target coverage summary for monogenic NIPT (Phase 4, pure core).

The lab uploads a coverage BED (the existing interval-track coverage path); the
"target" is the existing gene panel / family ROI. This module intersects the
cfDNA sample's coverage intervals with the target regions and computes a
length-weighted median coverage per region and overall.

Length-weighted median: each coverage interval contributes its value weighted by
the number of bases it covers within the target, so the result is the median
per-base depth across the target (not a plain median of interval values). Pure
Python, no I/O -- the loader and target resolution live in nipt_service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator


@dataclass(slots=True)
class CoverageInterval:
    chrom: str
    start: int
    end: int
    value: float


@dataclass(slots=True)
class TargetRegion:
    label: str
    chrom: str
    start: int
    end: int


@dataclass(slots=True)
class RegionCoverage:
    label: str
    chrom: str
    start: int
    end: int
    median_coverage: float | None
    covered_bases: int
    target_bases: int


@dataclass(slots=True)
class NiptCoverageSummary:
    overall_median_on_target: float | None
    target_region_count: int
    per_region: list[RegionCoverage] = field(default_factory=list)


def _overlap_length(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def weighted_median(weighted_values: Iterable[tuple[float, int]]) -> float | None:
    """Median of ``value``s weighted by integer ``weight`` (base count)."""
    pairs = [(float(value), int(weight)) for value, weight in weighted_values if weight and weight > 0]
    if not pairs:
        return None
    pairs.sort(key=lambda pair: pair[0])
    total = sum(weight for _, weight in pairs)
    half = total / 2.0
    cumulative = 0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= half:
            return value
    return pairs[-1][0]


def _clip_overlaps(
    region: TargetRegion, coverage: Iterable[CoverageInterval]
) -> Iterator[tuple[float, int]]:
    for interval in coverage:
        if interval.chrom != region.chrom:
            continue
        length = _overlap_length(interval.start, interval.end, region.start, region.end)
        if length > 0:
            yield interval.value, length


def summarize_region(
    region: TargetRegion, coverage: list[CoverageInterval]
) -> RegionCoverage:
    pairs = list(_clip_overlaps(region, coverage))
    covered = sum(weight for _, weight in pairs)
    return RegionCoverage(
        label=region.label,
        chrom=region.chrom,
        start=region.start,
        end=region.end,
        median_coverage=weighted_median(pairs),
        covered_bases=covered,
        target_bases=max(0, region.end - region.start),
    )


def summarize_on_target_coverage(
    target_regions: list[TargetRegion], coverage: list[CoverageInterval]
) -> NiptCoverageSummary:
    per_region = [summarize_region(region, coverage) for region in target_regions]
    overall_pairs: list[tuple[float, int]] = []
    for region in target_regions:
        overall_pairs.extend(_clip_overlaps(region, coverage))
    return NiptCoverageSummary(
        overall_median_on_target=weighted_median(overall_pairs),
        target_region_count=len(target_regions),
        per_region=per_region,
    )
