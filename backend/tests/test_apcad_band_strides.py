"""Tests for the APCAD downsample budget allocation (_apcad_band_strides).

APCAD is downsampled server-side to ~budget points across two BAF bands. The
allocation must keep the heterozygous (phasing) signal while leaving the
homozygous bands visible — including the case where het is rare (its full set must
survive) and the case where het is plentiful (homozygous must still get a share).
"""
from app.services.clickhouse_interval_tracks import _apcad_band_strides


def _kept(count: int, stride: int) -> int:
    """Approximate rows kept by a cityHash modulo stride (0 stride => band excluded)."""
    if stride == 0:
        return 0
    return -(-count // stride)  # ceil(count / stride), the best case for uniform hashing


def test_rare_het_is_kept_in_full():
    # Homozygous-heavy sample: every het marker (the autozygosity-break signal) survives.
    het_stride, homo_stride = _apcad_band_strides(het_count=283, homo_count=35_000, budget=9108)
    assert het_stride == 1  # keep all het
    assert homo_stride >= 1
    # Homozygous band is still represented and thinned, not dropped.
    assert _kept(35_000, homo_stride) <= 9108


def test_plentiful_het_still_leaves_room_for_homozygous():
    # Het-heavy sample: het is thinned, but the homozygous band keeps a visible share.
    het_stride, homo_stride = _apcad_band_strides(het_count=800_000, homo_count=700_000, budget=9000)
    assert het_stride > 1 and homo_stride > 1
    homo_kept = _kept(700_000, homo_stride)
    assert homo_kept > 0
    # Homozygous reserve is up to 40% of the budget.
    assert homo_kept <= 9000 * 2 // 5 + 2


def test_total_kept_is_within_budget():
    het_stride, homo_stride = _apcad_band_strides(het_count=500_000, homo_count=500_000, budget=6000)
    total = _kept(500_000, het_stride) + _kept(500_000, homo_stride)
    assert total <= 6000 + 2  # ceil rounding slack


def test_small_track_keeps_everything():
    het_stride, homo_stride = _apcad_band_strides(het_count=100, homo_count=50, budget=9000)
    assert het_stride == 1 and homo_stride == 1  # nothing thinned


def test_empty_band_is_excluded():
    het_stride, homo_stride = _apcad_band_strides(het_count=0, homo_count=10_000, budget=5000)
    assert het_stride == 0  # no het rows -> band excluded
    assert homo_stride >= 1
