"""Tests for the APCAD downsample budget allocation (_apcad_band_targets).

APCAD is downsampled server-side to ~budget points across two BAF bands, keeping
the highest-quality markers in each. The allocation must keep the heterozygous
(phasing) signal while leaving the homozygous bands visible — including the case
where het is rare (its full set must survive) and where het is plentiful (the
homozygous band must still get a share).
"""
from app.services.clickhouse_interval_tracks import _apcad_band_targets


def test_rare_het_is_kept_in_full():
    het_target, homo_target = _apcad_band_targets(het_count=283, homo_count=35_000, budget=9108)
    assert het_target == 283  # every het marker survives
    assert homo_target == 9108 - 283  # the rest goes to homozygous


def test_plentiful_het_still_leaves_room_for_homozygous():
    het_target, homo_target = _apcad_band_targets(het_count=800_000, homo_count=700_000, budget=9000)
    assert homo_target == 9000 * 2 // 5  # homozygous reserve (40%)
    assert het_target == 9000 - homo_target
    assert het_target + homo_target <= 9000


def test_total_stays_within_budget():
    het_target, homo_target = _apcad_band_targets(het_count=500_000, homo_count=500_000, budget=6000)
    assert het_target + homo_target <= 6000


def test_small_track_keeps_everything():
    het_target, homo_target = _apcad_band_targets(het_count=100, homo_count=50, budget=9000)
    assert het_target == 100 and homo_target == 50


def test_empty_band_is_excluded():
    het_target, homo_target = _apcad_band_targets(het_count=0, homo_count=10_000, budget=5000)
    assert het_target == 0  # no het -> excluded
    assert homo_target == 5000
