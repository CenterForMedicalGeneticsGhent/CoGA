from __future__ import annotations

from backend.app.services.nipt_coverage import (
    DEFAULT_MIN_COVERED_FRACTION,
    DEFAULT_MIN_DEPTH,
    CoverageInterval,
    TargetRegion,
    evaluate_low_coverage,
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


def test_low_coverage_flags_deep_genes_pass_and_shallow_genes_fail() -> None:
    regions = [
        TargetRegion("DEEP", "1", 0, 100),
        TargetRegion("SHALLOW", "2", 0, 100),
    ]
    coverage = [
        CoverageInterval("1", 0, 100, 100.0),  # well covered
        CoverageInterval("2", 0, 100, 8.0),  # uniformly shallow
    ]
    summary = summarize_on_target_coverage(regions, coverage, min_depth=20.0)
    flagged = {region.label: region for region in summary.low_coverage_regions}
    assert set(flagged) == {"SHALLOW"}
    assert flagged["SHALLOW"].reason == "low_depth"
    assert flagged["SHALLOW"].covered_fraction == 1.0
    assert summary.min_depth == 20.0
    assert summary.min_covered_fraction == DEFAULT_MIN_COVERED_FRACTION


def test_low_coverage_flags_gene_with_no_coverage() -> None:
    regions = [TargetRegion("ABSENT", "1", 0, 100)]
    summary = summarize_on_target_coverage(regions, [])
    assert [region.reason for region in summary.low_coverage_regions] == ["no_coverage"]
    assert summary.low_coverage_regions[0].median_coverage is None
    assert summary.low_coverage_regions[0].covered_fraction == 0.0


def test_low_coverage_catches_silent_gap_a_high_median_would_hide() -> None:
    # Half the gene is deep, half has no coverage at all. A length-weighted
    # median over only the covered bases still reports 100x, but the gene was
    # not adequately interrogated -- the covered-fraction check must catch it.
    region = TargetRegion("GAPPY", "1", 0, 100)
    coverage = [CoverageInterval("1", 0, 40, 100.0)]
    rc = summarize_region(region, coverage)
    assert rc.median_coverage == 100.0  # median alone looks healthy
    flagged = evaluate_low_coverage([rc], min_depth=20.0, min_covered_fraction=0.90)
    assert len(flagged) == 1
    assert flagged[0].reason == "partial_coverage"
    assert flagged[0].covered_fraction == 0.4


def test_low_coverage_threshold_is_respected() -> None:
    regions = [TargetRegion("GENE", "1", 0, 100)]
    coverage = [CoverageInterval("1", 0, 100, 30.0)]
    # 30x passes the default floor but fails a stricter 50x threshold.
    assert not summarize_on_target_coverage(regions, coverage).low_coverage_regions
    strict = summarize_on_target_coverage(regions, coverage, min_depth=50.0)
    assert [region.reason for region in strict.low_coverage_regions] == ["low_depth"]
    assert DEFAULT_MIN_DEPTH == 20.0
