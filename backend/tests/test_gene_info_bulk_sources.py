"""Tests for gene-reference bulk-source parsing helpers."""

from backend.app.services.gene_info_bulk_sources import (
    _leading_float,
    parse_dbnsfp_gene_rows,
)


def test_leading_float_preserves_scientific_notation() -> None:
    # dbNSFP stores constraint metrics in scientific notation; dropping the exponent
    # silently corrupts them (regression: gnomAD_pLI 9.2157e-29 became 9.2157).
    assert _leading_float("9.2157e-29") == 9.2157e-29
    assert _leading_float("8.8500e-01") == 0.885
    assert _leading_float("-1.80471748387839") == -1.80471748387839
    assert _leading_float("1.5E3") == 1500.0
    assert _leading_float("") is None


def test_dbnsfp_constraint_metrics_parsed_in_range(tmp_path) -> None:
    # Minimal dbNSFP gene file with scientific-notation constraint columns.
    header = ["Gene_name", "gnomAD_pLI", "gnomAD_pRec", "gnomAD_pNull", "gnomAD_LOEUF"]
    row = ["BRCA1", "9.2157e-29", "2.4418e-01", "7.5582e-01", "8.8500e-01"]
    path = tmp_path / "dbnsfp_gene.tsv"
    path.write_text("\t".join(header) + "\n" + "\t".join(row) + "\n")

    records = parse_dbnsfp_gene_rows(path)
    brca1 = records["BRCA1"]
    metrics = brca1["extra"]["constraint_metrics"]
    # pLI is a probability in [0, 1]; the exponent must be preserved (≈ 0, not 9.2).
    assert 0.0 <= metrics["gnomad_pli"] <= 1.0
    assert metrics["gnomad_pli"] < 1e-20
    assert abs(metrics["gnomad_loeuf"] - 0.885) < 1e-9
    assert abs(metrics["gnomad_pnull"] - 0.75582) < 1e-9
