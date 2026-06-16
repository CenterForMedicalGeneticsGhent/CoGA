"""Unit tests for the pure BED helpers in app.services.bed_service.

`_downsample_apcad_records` bounds the genome-wide APCAD payload (otherwise
~2.7 MB/sample, which stalled the genome-overview page) by uniformly thinning the
raw points to a cap. Crucially it preserves the *real* BAF values rather than
averaging each window to a single dot — averaging flattened the homozygous bands
to a sparse dotted line, so many APCAD values were no longer visible.
"""
from app.services.bed_service import _downsample_apcad_records


def _row(start: int, value: float, origin: str = "paternal") -> dict:
    return {"chr": "1", "start": start, "end": start + 1, "value": value, "origin": origin}


def test_returns_all_points_with_real_values_when_under_limit():
    rows = [_row(0, 0.01), _row(10, 0.99), _row(20, 0.48)]

    out = _downsample_apcad_records(rows, limit=100)

    # Real values, in order — no per-window averaging.
    assert [rec["value"] for rec in out] == [0.01, 0.99, 0.48]
    assert out[0] == {"chr": "1", "start": 0, "end": 1, "value": 0.01, "origin": "paternal"}


def test_thins_to_at_most_limit_preserving_real_input_values():
    rows = [_row(i, 0.99 if i % 2 else 0.01) for i in range(100)]

    out = _downsample_apcad_records(rows, limit=10)

    assert len(out) <= 10
    # Every emitted value is one of the real inputs (a subset), never an average.
    assert all(rec["value"] in (0.01, 0.99) for rec in out)
    # Uniform stride starts at the first point.
    assert out[0]["start"] == 0


def test_homozygous_extremes_are_not_collapsed_to_a_band_mean():
    # Many homozygous-high points across a region keep their real spread (~0.97–0.99)
    # instead of averaging to one dot pinned at 1.0.
    rows = [_row(i * 10, 0.97 + (i % 3) * 0.01) for i in range(60)]

    out = _downsample_apcad_records(rows, limit=1000)

    assert len(out) == 60
    assert {round(rec["value"], 2) for rec in out} == {0.97, 0.98, 0.99}


def test_heterozygous_points_are_kept_when_homozygous_bands_are_thinned():
    # Dense homozygous bands plus a few rare heterozygous points (the autozygosity-
    # break signal). A tight budget thins the homozygous bands but keeps every het
    # point.
    rows = [_row(i, 0.99 if i % 2 else 0.01) for i in range(1000)]
    het_starts = [101, 303, 505, 707, 909]
    rows += [_row(start, 0.5) for start in het_starts]

    out = _downsample_apcad_records(rows, limit=50)

    assert len(out) <= 50
    kept_het = [rec for rec in out if 0.05 <= rec["value"] <= 0.95]
    assert sorted(rec["start"] for rec in kept_het) == het_starts


def test_keeps_origins_distinct():
    rows = [_row(0, 0.99, "paternal"), _row(0, 0.99, "maternal")]

    out = _downsample_apcad_records(rows, limit=100)

    assert {rec["origin"] for rec in out} == {"paternal", "maternal"}


def test_zero_limit_is_treated_as_unbounded():
    rows = [_row(i, 0.5) for i in range(5)]

    out = _downsample_apcad_records(rows, limit=0)

    assert len(out) == 5
