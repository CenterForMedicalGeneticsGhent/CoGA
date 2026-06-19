import json

import pytest
from fastapi import HTTPException

from backend.app.schemas import AcmgClassificationPayload, AcmgCriterionSelection
from backend.app.services import acmg_points
from backend.app.services.small_variant_review_pg import (
    _acmg_json_or_none,
    _deserialize_acmg,
    _normalize_acmg_payload,
)


def crit(code: str, strength: str, accepted: bool = True) -> AcmgCriterionSelection:
    return AcmgCriterionSelection(code=code, strength=strength, accepted=accepted)


def test_point_bands_match_clingen_thresholds() -> None:
    cases = [
        ([("PVS1", "very_strong"), ("PM2", "moderate")], 10, "acmg_class_5"),
        ([("PVS1", "very_strong"), ("PM2", "supporting")], 9, "acmg_class_4"),
        ([("PM2", "supporting")], 1, "acmg_class_3"),
        ([("BP4", "supporting"), ("BP7", "supporting")], -2, "acmg_class_2"),
        ([("BS1", "strong"), ("BS2", "strong")], -8, "acmg_class_1"),
    ]
    for selections, expected_points, expected_class in cases:
        criteria = [{"code": c, "strength": s, "accepted": True} for c, s in selections]
        points, class_key, _ = acmg_points.compute_classification(criteria)
        assert points == expected_points
        assert class_key == expected_class


def test_vus_sub_tier_bands() -> None:
    # Cold 0–1, Warm 2–3, Hot 4–5; None outside the VUS band.
    assert acmg_points.vus_tier_for_points(0, "acmg_class_3") == "cold"
    assert acmg_points.vus_tier_for_points(1, "acmg_class_3") == "cold"
    assert acmg_points.vus_tier_for_points(2, "acmg_class_3") == "warm"
    assert acmg_points.vus_tier_for_points(3, "acmg_class_3") == "warm"
    assert acmg_points.vus_tier_for_points(4, "acmg_class_3") == "hot"
    assert acmg_points.vus_tier_for_points(5, "acmg_class_3") == "hot"
    assert acmg_points.vus_tier_for_points(9, "acmg_class_4") is None
    assert acmg_points.vus_tier_for_points(-2, "acmg_class_2") is None


def test_normalize_stores_vus_tier_only_for_vus() -> None:
    # PM2 supporting (1 pt) → VUS cold.
    vus_blob, _, vus_class = _normalize_acmg_payload(
        AcmgClassificationPayload(criteria=[crit("PM2", "supporting")])
    )
    assert vus_class == "acmg_class_3"
    assert vus_blob["vus_tier"] == "cold"

    # PS1 strong (4 pts) → VUS hot.
    hot_blob, _, _ = _normalize_acmg_payload(
        AcmgClassificationPayload(criteria=[crit("PS1", "strong")])
    )
    assert hot_blob["vus_tier"] == "hot"

    # Likely Pathogenic → no tier.
    lp_blob, _, lp_class = _normalize_acmg_payload(
        AcmgClassificationPayload(criteria=[crit("PVS1", "very_strong"), crit("PM2", "supporting")])
    )
    assert lp_class == "acmg_class_4"
    assert lp_blob["vus_tier"] is None


def test_ba1_forces_benign_regardless_of_points() -> None:
    points, class_key, label = acmg_points.compute_classification(
        [
            {"code": "BA1", "strength": "stand_alone", "accepted": True},
            {"code": "PVS1", "strength": "very_strong", "accepted": True},
        ]
    )
    assert class_key == "acmg_class_1"
    assert label == "Benign - class 1"


def test_unaccepted_criteria_do_not_score() -> None:
    points, class_key, _ = acmg_points.compute_classification(
        [{"code": "PVS1", "strength": "very_strong", "accepted": False}]
    )
    assert points == 0
    assert class_key == "acmg_class_3"


def test_normalize_recomputes_and_ignores_client_total() -> None:
    payload = AcmgClassificationPayload(
        criteria=[crit("PVS1", "very_strong"), crit("PM2", "supporting")],
        point_total=999,  # bogus client value must be ignored
        classification="Benign - class 1",
    )
    blob, total, class_key = _normalize_acmg_payload(payload)
    assert total == 9
    assert class_key == "acmg_class_4"
    assert blob["point_total"] == 9
    assert blob["classification"] == "Likely Pathogenic - class 4"
    assert {c["code"] for c in blob["criteria"]} == {"PVS1", "PM2"}


def test_normalize_empty_criteria_clears() -> None:
    assert _normalize_acmg_payload(AcmgClassificationPayload(criteria=[])) == (None, None, None)
    assert _normalize_acmg_payload(None) == (None, None, None)


def test_normalize_rejects_unknown_code() -> None:
    with pytest.raises(HTTPException) as exc:
        _normalize_acmg_payload(AcmgClassificationPayload(criteria=[crit("PX9", "supporting")]))
    assert exc.value.status_code == 400


def test_normalize_rejects_invalid_strength() -> None:
    with pytest.raises(HTTPException) as exc:
        _normalize_acmg_payload(AcmgClassificationPayload(criteria=[crit("PM2", "ultra")]))
    assert exc.value.status_code == 400


def test_blob_round_trips_through_storage_helpers() -> None:
    payload = AcmgClassificationPayload(criteria=[crit("PVS1", "very_strong")])
    blob, _, _ = _normalize_acmg_payload(payload)

    stored = _acmg_json_or_none(blob)
    assert isinstance(stored, str)

    restored = _deserialize_acmg(json.loads(stored))
    assert restored is not None
    assert restored.point_total == 8
    assert restored.criteria[0].code == "PVS1"
    assert restored.criteria[0].accepted is True


def test_acmg_json_or_none_returns_none_for_empty() -> None:
    assert _acmg_json_or_none(None) is None
    assert _deserialize_acmg(None) is None
