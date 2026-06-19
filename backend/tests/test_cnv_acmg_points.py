"""Tests for the ClinGen 2019 CNV classification point system."""

from backend.app.services import cnv_acmg_points as p


def test_class_thresholds() -> None:
    assert p.class_key_for_points(0.99) == "cnv_class_5"
    assert p.class_key_for_points(0.90) == "cnv_class_4"
    assert p.class_key_for_points(0.89) == "cnv_class_3"
    assert p.class_key_for_points(0.0) == "cnv_class_3"
    assert p.class_key_for_points(-0.89) == "cnv_class_3"
    assert p.class_key_for_points(-0.90) == "cnv_class_2"
    assert p.class_key_for_points(-0.98) == "cnv_class_2"
    assert p.class_key_for_points(-0.99) == "cnv_class_1"


def test_loss_complete_hi_overlap_is_pathogenic() -> None:
    total, key, label = p.compute_classification(
        "loss", [{"code": "2A", "points": 1.0, "accepted": True}]
    )
    assert total == 1.0
    assert key == "cnv_class_5"
    assert "Pathogenic" in label


def test_loss_benign_region_is_benign() -> None:
    total, key, _ = p.compute_classification(
        "loss", [{"code": "2F", "points": -1.0, "accepted": True}]
    )
    assert total == -1.0
    assert key == "cnv_class_1"


def test_unaccepted_criteria_do_not_score() -> None:
    total, key, _ = p.compute_classification(
        "loss",
        [
            {"code": "2A", "points": 1.0, "accepted": False},
            {"code": "3B", "points": 0.45, "accepted": True},
        ],
    )
    assert total == 0.45
    assert key == "cnv_class_3"


def test_points_are_clamped_to_allowed_range() -> None:
    # 2H allows at most 0.15; a client over-value must not inflate the score.
    assert p.clamp_points("loss", "2H", 5.0) == 0.15
    total, _key, _ = p.compute_classification(
        "loss", [{"code": "2H", "points": 5.0, "accepted": True}]
    )
    assert total == 0.15


def test_gain_and_loss_have_distinct_catalogs() -> None:
    # 2I (gene disruption) only exists in the gain catalog.
    assert p.is_valid_code("gain", "2I")
    assert not p.is_valid_code("loss", "2I")
    # 2C means different things but is valid in both.
    assert p.is_valid_code("gain", "2C")


def test_gain_complete_ts_overlap_is_pathogenic() -> None:
    total, key, _ = p.compute_classification(
        "gain", [{"code": "2A", "points": 1.0, "accepted": True}]
    )
    assert total == 1.0
    assert key == "cnv_class_5"


def test_summed_evidence_reaches_likely_pathogenic() -> None:
    total, key, _ = p.compute_classification(
        "loss",
        [
            {"code": "2C-1", "points": 0.90, "accepted": True},
            {"code": "5A", "points": 0.15, "accepted": True},
        ],
    )
    assert total == 1.05
    assert key == "cnv_class_5"
