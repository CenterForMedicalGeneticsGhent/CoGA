"""Unit tests for the pure BED windowing helpers in app.services.bed_service.

These focus on `_windowed_apcad_rows`, which previously emitted every homozygous
(extreme-BAF) SNP individually — leaving the genome-wide APCAD payload unbounded
(~2.7 MB/sample) and stalling the genome-overview page. The fix bins the extremes
per window/origin/band like the mid-range, so the payload is bounded while the
homozygous bands that carry the ROH signal survive.
"""
from app.services.bed_service import _windowed_apcad_rows


def _row(start: int, value: float, origin: str = "paternal") -> dict:
    return {"chr": "1", "start": start, "end": start + 1, "value": value, "origin": origin}


def test_homozygous_extremes_are_binned_not_emitted_per_snp():
    # A whole window of homozygous SNPs (the genome-wide common case) used to be
    # emitted one record per SNP; now it collapses to one dot per band.
    rows = [_row(start=i * 10, value=0.99) for i in range(100)]
    rows += [_row(start=i * 10 + 5, value=0.01) for i in range(100)]  # 200 rows total

    out = _windowed_apcad_rows(rows, window=1000, limit=10000)

    # 200 homozygous SNPs in one window/origin -> exactly two band dots.
    assert len(out) == 2
    values = sorted(round(rec["value"], 3) for rec in out)
    assert values == [0.01, 0.99]
    assert all(rec["start"] == 0 and rec["end"] == 1000 for rec in out)


def test_bands_are_averaged_and_roh_window_keeps_homozygous_bands():
    rows = [
        # Window [0,1000): run of homozygosity — only the two extreme bands.
        _row(start=10, value=0.01),
        _row(start=20, value=0.03),
        _row(start=30, value=0.98),
        _row(start=40, value=0.99),
        # Window [1000,2000): heterozygous — adds the mid band.
        _row(start=1010, value=0.02),
        _row(start=1020, value=0.48),
        _row(start=1030, value=0.52),
        _row(start=1040, value=0.97),
    ]

    out = _windowed_apcad_rows(rows, window=1000, limit=10000)

    by_window: dict[int, list[float]] = {}
    for rec in out:
        by_window.setdefault(rec["start"], []).append(round(rec["value"], 3))

    # ROH window: two bands (low/high), no mid -> the empty mid band is the signal.
    assert sorted(by_window[0]) == [0.02, 0.985]
    # Heterozygous window: three bands, each the mean of its members.
    assert sorted(by_window[1000]) == [0.02, 0.5, 0.97]


def test_origins_are_kept_separate():
    rows = [
        _row(start=10, value=0.99, origin="paternal"),
        _row(start=20, value=0.99, origin="maternal"),
    ]

    out = _windowed_apcad_rows(rows, window=1000, limit=10000)

    assert {rec["origin"] for rec in out} == {"paternal", "maternal"}
    assert len(out) == 2


def test_limit_bounds_the_output():
    rows = [_row(start=i * 1000, value=0.5) for i in range(50)]  # 50 distinct windows

    out = _windowed_apcad_rows(rows, window=1000, limit=10)

    assert len(out) == 10
    # Truncation keeps the earliest windows (sorted by start).
    assert out[0]["start"] == 0
    assert all(out[i]["start"] <= out[i + 1]["start"] for i in range(len(out) - 1))
