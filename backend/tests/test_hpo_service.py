from pathlib import Path

import pytest

from backend.app.services.family_package_import import validate_family_package
from backend.app.services import hpo_service
from backend.app.services.hpo_service import (
    compute_hpo_closure,
    ensure_hpo_ontology_on_startup,
    get_hpo_admin_summary,
    list_hpo_admin_terms,
    parse_hpo_obo_text,
    parse_hpo_ontology_release_metadata_text,
    parse_hpo_tsv_text,
    parse_manifest_inline_hpo,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class _FakeMappings:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)

    def scalar_one_or_none(self):
        if not self._rows:
            return None
        return next(iter(self._rows[0].values()))

    def scalar_one(self):
        return next(iter(self._rows[0].values()))


class _FakeSession:
    def __init__(self, results: list[_FakeResult]):
        self._results = list(results)

    async def execute(self, *args, **kwargs):
        del args, kwargs
        return self._results.pop(0)


def test_parse_hpo_obo_terms_synonyms_and_closure() -> None:
    ontology = parse_hpo_obo_text((FIXTURE_DIR / "hpo-mini.obo").read_text(encoding="utf-8"))

    assert ontology.terms["HP:0001250"].label == "Seizure"
    assert ontology.terms["HP:0001250"].synonyms == ["Epileptic seizure"]
    assert ontology.edges[0].child_id == "HP:0001250"

    closure = set(compute_hpo_closure(ontology.terms, ontology.edges))
    assert ("HP:0001250", "HP:0001250", 0) in closure
    assert ("HP:0001250", "HP:0000118", 1) in closure
    assert ("HP:0004322", "HP:0000118", 1) in closure


def test_parse_hpo_obo_release_metadata() -> None:
    metadata = parse_hpo_ontology_release_metadata_text(
        "\n".join(
            [
                "format-version: 1.2",
                "data-version: hp/releases/2026-02-16",
                'property_value: owl:versionInfo "2026-02-16" xsd:string',
                "",
                "[Term]",
                "id: HP:0000001",
            ]
        )
    )

    assert metadata.release_version == "hp/releases/2026-02-16"
    assert metadata.release_date.isoformat() == "2026-02-16"


@pytest.mark.asyncio
async def test_hpo_admin_summary_reports_not_loaded_when_schema_missing() -> None:
    session = _FakeSession([_FakeResult([{"hpo_term": False}])])

    summary = await get_hpo_admin_summary(session)

    assert summary["total_terms"] == 0
    assert summary["ontology_loaded"] is False


@pytest.mark.asyncio
async def test_hpo_admin_terms_normalizes_json_values() -> None:
    session = _FakeSession(
        [
            _FakeResult([{"hpo_term": True, "hpo_synonym": True, "hpo_edge": True}]),
            _FakeResult(
                [
                    {
                        "hpo_id": "HP:0001250",
                        "label": "Seizure",
                        "definition": "A seizure phenotype.",
                        "is_obsolete": False,
                        "replaced_by": None,
                        "release_version": "test",
                        "release_date": None,
                        "synonyms": '["Epileptic seizure"]',
                        "parents": '[{"hpo_id":"HP:0000118","label":"Phenotypic abnormality","relation":"is_a"}]',
                        "children": "[]",
                        "parent_count": 1,
                        "child_count": 0,
                        "match_rank": 0,
                    }
                ]
            ),
        ]
    )

    terms = await list_hpo_admin_terms(session, query="seizure", limit=100)

    assert terms[0]["synonyms"] == ["Epileptic seizure"]
    assert terms[0]["parents"] == [
        {
            "hpo_id": "HP:0000118",
            "label": "Phenotypic abnormality",
            "relation": "is_a",
        }
    ]
    assert "match_rank" not in terms[0]


@pytest.mark.asyncio
async def test_search_hpo_terms_returns_default_order_when_query_blank() -> None:
    captured: dict[str, object] = {}

    class _CapturingSession:
        async def execute(self, sql, params=None):
            captured["sql"] = str(sql)
            captured["params"] = dict(params or {})
            return _FakeResult(
                [
                    {
                        "hpo_id": "HP:0000001",
                        "label": "Abnormality",
                        "definition": None,
                        "is_obsolete": False,
                    }
                ]
            )

    result = await hpo_service.search_hpo_terms(_CapturingSession(), query="", limit=10)

    assert result == [
        {
            "hpo_id": "HP:0000001",
            "label": "Abnormality",
            "definition": None,
            "is_obsolete": False,
        }
    ]
    assert "CASE" not in captured["sql"]
    assert "ORDER BY t.is_obsolete, t.label" in captured["sql"]
    assert captured["params"]["limit"] == 10


@pytest.mark.asyncio
async def test_hpo_admin_terms_accepts_null_query_parameter() -> None:
    captured: dict[str, object] = {}

    class _CapturingSession:
        def __init__(self):
            self.call_count = 0

        async def execute(self, sql, params=None):
            self.call_count += 1
            if self.call_count == 1:
                return _FakeResult([{"hpo_term": True, "hpo_synonym": True, "hpo_edge": True}])

            captured["sql"] = str(sql)
            captured["params"] = dict(params or {})
            return _FakeResult(
                [
                    {
                        "hpo_id": "HP:0000001",
                        "label": "Abnormality",
                        "definition": None,
                        "is_obsolete": False,
                    }
                ]
            )

    result = await list_hpo_admin_terms(_CapturingSession(), query=None, limit=10)

    assert result[0]["hpo_id"] == "HP:0000001"
    assert result[0]["label"] == "Abnormality"
    assert result[0]["definition"] is None
    assert result[0]["is_obsolete"] is False
    assert "lower(t.hpo_id) = lower(:query)" in captured["sql"]
    assert "LIMIT :limit" in captured["sql"]


@pytest.mark.asyncio
async def test_hpo_startup_bootstrap_imports_empty_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ontology_path = tmp_path / "hpo.obo"
    ontology_path.write_text(
        "\n".join(
            [
                "format-version: 1.2",
                "data-version: hp/releases/2026-02-16",
                "",
                "[Term]",
                "id: HP:0000001",
                "name: All",
            ]
        ),
        encoding="utf-8",
    )
    session = _FakeSession(
        [
            _FakeResult([{"hpo_term": True, "hpo_synonym": True, "hpo_edge": True, "hpo_closure": True}]),
            _FakeResult([{"count": 0}]),
        ]
    )
    captured = {}

    async def fake_import(*args, **kwargs):
        captured.update(kwargs)
        return {"terms": 1, "synonyms": 0, "edges": 0, "closure_rows": 1}

    monkeypatch.setattr(hpo_service, "import_hpo_ontology", fake_import)

    result = await ensure_hpo_ontology_on_startup(
        session,
        ontology_path=ontology_path,
        download_if_missing=False,
    )

    assert result is not None
    assert result["release_version"] == "hp/releases/2026-02-16"
    assert result["release_date"].isoformat() == "2026-02-16"
    assert captured["path"] == ontology_path
    assert captured["release_version"] == "hp/releases/2026-02-16"
    assert captured["release_date"].isoformat() == "2026-02-16"


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
