from pathlib import Path

from backend.app.services.family_package_import import validate_family_package
from backend.app.services.hpo_service import (
    compute_hpo_closure,
    parse_hpo_obo_text,
    parse_hpo_tsv_text,
    parse_manifest_inline_hpo,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_hpo_obo_terms_synonyms_and_closure() -> None:
    ontology = parse_hpo_obo_text((FIXTURE_DIR / "hpo-mini.obo").read_text(encoding="utf-8"))

    assert ontology.terms["HP:0001250"].label == "Seizure"
    assert ontology.terms["HP:0001250"].synonyms == ["Epileptic seizure"]
    assert ontology.edges[0].child_id == "HP:0001250"

    closure = set(compute_hpo_closure(ontology.terms, ontology.edges))
    assert ("HP:0001250", "HP:0001250", 0) in closure
    assert ("HP:0001250", "HP:0000118", 1) in closure
    assert ("HP:0004322", "HP:0000118", 1) in closure


def test_parse_hpo_tsv_reports_row_level_errors() -> None:
    text_value = "\n".join(
        [
            "family_id\tindividual_id\thpo_id\tlabel\tstatus\tonset\tevidence\tsource\tnote",
            "FAM1\tPROBAND\tHP:0001250\tSeizure\tpresent\t\t\tmanual\t",
            "FAM2\tPROBAND\tHP:0001250\tSeizure\tpresent\t\t\tmanual\t",
            "FAM1\tSIB\tbad\tBad\tpresent\t\t\tmanual\t",
            "FAM1\tSIB\tHP:0004322\tShort stature\tmaybe\t\t\tmanual\t",
        ]
    )

    rows, issues = parse_hpo_tsv_text(text_value, expected_family_id="FAM1")

    assert [row.hpo_id for row in rows] == ["HP:0001250"]
    assert [issue.code for issue in issues] == [
        "phenotype_family_mismatch",
        "phenotype_hpo_invalid",
        "phenotype_status_invalid",
    ]
    assert issues[0].line_no == 3


def test_parse_manifest_inline_hpo_present_and_absent_terms() -> None:
    rows, issues = parse_manifest_inline_hpo(
        {
            "II-3": {
                "hpo": {
                    "present": ["HP:0001250"],
                    "absent": [{"id": "HP:0004322", "label": "Short stature"}],
                }
            }
        },
        family_id="FAM1",
    )

    assert issues == []
    assert [(row.individual_id, row.hpo_id, row.status) for row in rows] == [
        ("II-3", "HP:0001250", "present"),
        ("II-3", "HP:0004322", "absent"),
    ]


def test_family_package_validation_accepts_hpo_phenotype_manifest(tmp_path: Path) -> None:
    package = tmp_path / "FAMHPO"
    package.mkdir()
    (package / "family.ped").write_text(
        "\n".join(
            [
                "FAMHPO FATHER 0 0 1 1",
                "FAMHPO MOTHER 0 0 2 1",
                "FAMHPO PROBAND FATHER MOTHER 2 2",
            ]
        ),
        encoding="utf-8",
    )
    (package / "phenotypes.tsv").write_text(
        (FIXTURE_DIR / "phenotypes.tsv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (package / "manifest.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "family_id: FAMHPO",
                "ped: family.ped",
                "phenotypes:",
                "  file: phenotypes.tsv",
                "  format: hpo_tsv",
                "individuals:",
                "  PROBAND:",
                "    hpo:",
                "      present:",
                "        - HP:0004322",
            ]
        ),
        encoding="utf-8",
    )

    validation = validate_family_package(package)
    phenotype_summary = next(
        summary for summary in validation.datasets if summary.dataset_type == "phenotypes"
    )

    assert validation.valid
    assert phenotype_summary.status == "valid"
    assert phenotype_summary.files == ["phenotypes.tsv"]
    assert phenotype_summary.samples == ["MOTHER", "PROBAND"]
    assert phenotype_summary.summary["rows"] == 3
