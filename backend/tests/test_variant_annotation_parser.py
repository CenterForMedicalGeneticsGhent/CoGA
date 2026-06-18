"""Tests for VCF annotation parsing helpers."""

from backend.app.services.variant_annotation_parser import (
    _parse_float,
    _parse_spliceai_pred,
    _spliceai_delta,
)


def test_parse_float_handles_scientific_notation() -> None:
    assert _parse_float("1.23e-5") == 1.23e-5
    assert _parse_float("6.84E-7") == 6.84e-7
    assert _parse_float("0.001") == 0.001
    assert _parse_float(".") is None


def test_spliceai_delta_rejects_out_of_range() -> None:
    # Delta scores are probabilities in [0, 1]; a leaked DP position (e.g. 22) is dropped.
    assert _spliceai_delta(0.42) == 0.42
    assert _spliceai_delta(0.0) == 0.0
    assert _spliceai_delta(1.0) == 1.0
    assert _spliceai_delta(22.0) is None
    assert _spliceai_delta(-1.0) is None
    assert _spliceai_delta(None) is None


def test_parse_spliceai_pred_drops_position_leak() -> None:
    # Standard format ALLELE|SYMBOL|DS_AG|DS_AL|DS_DG|DS_DL|DP_AG|... — delta scores only.
    parsed = _parse_spliceai_pred("A|GENE|0.01|0.00|0.93|0.00|-5|12|-8|22")
    assert parsed == {"spliceai_ds_ag": 0.01, "spliceai_ds_al": 0.0,
                      "spliceai_ds_dg": 0.93, "spliceai_ds_dl": 0.0}

    # An offset format where a DP position lands in a DS slot: the >1 value is dropped.
    offset = _parse_spliceai_pred("A|0.00|0.00|0.00|22|35|-8|22|0|0")
    assert "spliceai_ds_dl" not in offset
    assert all(0.0 <= v <= 1.0 for v in offset.values())
