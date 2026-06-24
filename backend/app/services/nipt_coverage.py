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

# Defaults for the "was this gene adequately interrogated?" QC flag. A region is
# flagged when its median on-target depth is below ``DEFAULT_MIN_DEPTH`` or when
# part of it has no coverage at all (covered fraction below
# ``DEFAULT_MIN_COVERED_FRACTION``). The covered-fraction check is what catches
# silent gaps: a length-weighted median only sees *covered* bases, so a gene with
# a large uncovered stretch can still report a healthy median.
DEFAULT_MIN_DEPTH = 20.0
DEFAULT_MIN_COVERED_FRACTION = 0.90


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
class LowCoverageRegion:
    """A target region (panel gene) that failed the coverage QC check."""

    label: str
    chrom: str
    median_coverage: float | None
    covered_fraction: float
    reason: str  # "no_coverage" | "low_depth" | "partial_coverage"


@dataclass(slots=True)
class NiptCoverageSummary:
    overall_median_on_target: float | None
    target_region_count: int
    per_region: list[RegionCoverage] = field(default_factory=list)
    min_depth: float = DEFAULT_MIN_DEPTH
    min_covered_fraction: float = DEFAULT_MIN_COVERED_FRACTION
    low_coverage_regions: list[LowCoverageRegion] = field(default_factory=list)


def covered_fraction(region: RegionCoverage) -> float:
    """Fraction of the target region's bases that have any coverage (0..1)."""
    if region.target_bases <= 0:
        return 1.0
    return min(1.0, region.covered_bases / region.target_bases)


def _low_coverage_reason(
    region: RegionCoverage, *, min_depth: float, min_covered_fraction: float
) -> str | None:
    """Most severe coverage-QC failure for ``region``, or None if it passes.

    Order matters: a gene with no coverage at all is the worst case, then one
    that is uniformly too shallow, then one that is shallow only because part of
    it is uncovered (a silent gap the median alone would hide).
    """
    if region.covered_bases <= 0:
        return "no_coverage"
    if region.median_coverage is None or region.median_coverage < min_depth:
        return "low_depth"
    if covered_fraction(region) < min_covered_fraction:
        return "partial_coverage"
    return None


def evaluate_low_coverage(
    per_region: list[RegionCoverage],
    *,
    min_depth: float = DEFAULT_MIN_DEPTH,
    min_covered_fraction: float = DEFAULT_MIN_COVERED_FRACTION,
) -> list[LowCoverageRegion]:
    """Compact list of regions failing the depth / completeness QC thresholds."""
    flagged: list[LowCoverageRegion] = []
    for region in per_region:
        reason = _low_coverage_reason(
            region, min_depth=min_depth, min_covered_fraction=min_covered_fraction
        )
        if reason is None:
            continue
        flagged.append(
            LowCoverageRegion(
                label=region.label,
                chrom=region.chrom,
                median_coverage=region.median_coverage,
                covered_fraction=covered_fraction(region),
                reason=reason,
            )
        )
    return flagged


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
    target_regions: list[TargetRegion],
    coverage: list[CoverageInterval],
    *,
    min_depth: float = DEFAULT_MIN_DEPTH,
    min_covered_fraction: float = DEFAULT_MIN_COVERED_FRACTION,
) -> NiptCoverageSummary:
    per_region = [summarize_region(region, coverage) for region in target_regions]
    overall_pairs: list[tuple[float, int]] = []
    for region in target_regions:
        overall_pairs.extend(_clip_overlaps(region, coverage))
    return NiptCoverageSummary(
        overall_median_on_target=weighted_median(overall_pairs),
        target_region_count=len(target_regions),
        per_region=per_region,
        min_depth=min_depth,
        min_covered_fraction=min_covered_fraction,
        low_coverage_regions=evaluate_low_coverage(
            per_region, min_depth=min_depth, min_covered_fraction=min_covered_fraction
        ),
    )
