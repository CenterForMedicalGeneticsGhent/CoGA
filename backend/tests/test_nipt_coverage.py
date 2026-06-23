from __future__ import annotations

from backend.app.services.nipt_coverage import (
    CoverageInterval,
    TargetRegion,
    summarize_on_target_coverage,
    summarize_region,
    weighted_median,
)


def test_weighted_median_basic() -> None:
    assert weighted_median([(10.0, 1)]) == 10.0
    assert weighted_median([(10.0, 20), (40.0, 80)]) == 40.0
    assert weighted_median([]) is None


def test_summarize_region_weighted_median_and_covered_bases() -> None:
    region = TargetRegion(label="GENEA", chrom="1", start=100, end=200)
    coverage = [
        CoverageInterval("1", 100, 180, 40.0),
        CoverageInterval("1", 180, 200, 10.0),
    ]
    rc = summarize_region(region, coverage)
    assert rc.median_coverage == 40.0  # 80 bases at 40x outweigh 20 bases at 10x
    assert rc.covered_bases == 100
    assert rc.target_bases == 100


def test_summarize_region_clips_to_region_and_ignores_other_chromosomes() -> None:
    region = TargetRegion(label="GENEA", chrom="1", start=100, end=200)
    coverage = [
        CoverageInterval("1", 50, 120, 99.0),  # clipped to [100, 120) = 20 bases
        CoverageInterval("2", 100, 200, 5.0),  # different chromosome, ignored
    ]
    rc = summarize_region(region, coverage)
    assert rc.covered_bases == 20
    assert rc.median_coverage == 99.0


def test_summarize_on_target_overall_and_region_count() -> None:
    regions = [
        TargetRegion("A", "1", 100, 200),
        TargetRegion("B", "2", 0, 100),
    ]
    coverage = [
        CoverageInterval("1", 100, 200, 30.0),
        CoverageInterval("2", 0, 100, 30.0),
    ]
    summary = summarize_on_target_coverage(regions, coverage)
    assert summary.target_region_count == 2
    assert summary.overall_median_on_target == 30.0
    assert all(region.median_coverage == 30.0 for region in summary.per_region)


def test_summarize_on_target_without_coverage() -> None:
    regions = [TargetRegion("A", "1", 100, 200)]
    summary = summarize_on_target_coverage(regions, [])
    assert summary.overall_median_on_target is None
    assert summary.per_region[0].median_coverage is None
    assert summary.per_region[0].covered_bases == 0
