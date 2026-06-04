from __future__ import annotations

import pytest

from backend.app.services.clickhouse_family_variants import SmallVariantCall, SmallVariantRecord
from backend.app.services import clickhouse_variant_storage


@pytest.mark.asyncio
async def test_list_clickhouse_variant_assemblies_dedupes_table_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        assert "FROM system.tables" in query
        return [
            ("GRCh38/SNV_INDEL/entries",),
            ("GRCh38/SV/entries",),
            ("GRCh37/SNV_INDEL/entries",),
        ]

    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)

    assemblies = await clickhouse_variant_storage.list_clickhouse_variant_assemblies()

    assert assemblies == ["GRCh37", "GRCh38"]


@pytest.mark.asyncio
async def test_get_clickhouse_variant_storage_status_reports_missing_tables_and_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        if "FROM system.tables" in query:
            return [
                ("GRCh38/SNV_INDEL/entries", "CollapsingMergeTree"),
                ("GRCh38/SNV_INDEL/variants/details", "ReplacingMergeTree"),
                ("GRCh38/SV/entries", "CollapsingMergeTree"),
            ]
        if "FROM system.parts" in query:
            return [
                ("GRCh38/SNV_INDEL/entries", 5000, 250_000),
                ("GRCh38/SNV_INDEL/variants/details", 5000, 175_000),
                ("GRCh38/SV/entries", 1200, 64_000),
            ]
        if "FROM system.mutations" in query:
            return [("GRCh38/SV/entries", 2)]
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)

    status = await clickhouse_variant_storage.get_clickhouse_variant_storage_status("GRCh38")

    assert status["assembly_name"] == "GRCh38"
    assert status["health"] == "missing"
    assert status["expected_table_count"] == 14
    assert status["existing_table_count"] == 3
    assert status["small_variant_rows"] == 5000
    assert status["structural_variant_rows"] == 1200
    assert status["pending_mutations"] == 2
    assert "GRCh38/SNV_INDEL/variants/annotation_index" in status["missing_tables"]
    assert "GRCh38/SNV_INDEL/family_variant_summary" in status["missing_tables"]
    assert any(
        table["name"] == "GRCh38/SV/entries" and table["pending_mutations"] == 2
        for table in status["tables"]
    )


@pytest.mark.asyncio
async def test_count_family_small_variants_by_sample_counts_non_reference_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_ensure(assembly_name: str) -> None:
        assert assembly_name == "GRCh38"

    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        captured["query"] = query
        captured["params"] = params
        return [("embryo-1", 7)]

    monkeypatch.setattr(
        clickhouse_variant_storage,
        "ensure_clickhouse_variant_tables",
        fake_ensure,
    )
    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)

    counts = await clickhouse_variant_storage.count_family_small_variants_by_sample(
        "GRCh38",
        "family-1",
        sample_ids=["embryo-1"],
        project_ids=["project-1"],
    )

    assert counts == {"embryo-1": 7}
    assert "ARRAY JOIN `calls.sampleId` AS sample_id, `calls.gt` AS gt" in str(captured["query"])
    assert captured["params"] == {
        "family_guid": "family-1",
        "sample_ids": ("embryo-1",),
        "project_ids": ("project-1",),
    }


@pytest.mark.asyncio
async def test_optimize_clickhouse_variant_tables_skips_materialized_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed_queries: list[str] = []

    async def fake_ensure(assembly_name: str) -> None:
        assert assembly_name == "GRCh38"

    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        executed_queries.append(query)
        return []

    async def fake_status(assembly_name: str) -> dict[str, object]:
        return {"assembly_name": assembly_name, "health": "ready", "tables": []}

    monkeypatch.setattr(
        clickhouse_variant_storage,
        "ensure_clickhouse_variant_tables",
        fake_ensure,
    )
    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)
    monkeypatch.setattr(
        clickhouse_variant_storage,
        "get_clickhouse_variant_storage_status",
        fake_status,
    )

    status = await clickhouse_variant_storage.optimize_clickhouse_variant_tables(
        "GRCh38",
        final=True,
    )

    assert status["assembly_name"] == "GRCh38"
    assert len(executed_queries) == 12
    assert all("OPTIMIZE TABLE" in query for query in executed_queries)
    assert all("FINAL" in query for query in executed_queries)
    assert not any("_mv" in query for query in executed_queries)


@pytest.mark.asyncio
async def test_insert_small_variant_records_uses_compact_annotations_and_gene_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, list[tuple[object, ...]] | None]] = []

    async def fake_ensure(assembly_name: str) -> None:
        assert assembly_name == "GRCh38"

    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        executed.append((query, data))
        return []

    monkeypatch.setattr(
        clickhouse_variant_storage,
        "ensure_clickhouse_variant_tables",
        fake_ensure,
    )
    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)

    record = SmallVariantRecord(
        variant_key=None,
        variant_id="1-100-A-G",
        chr="1",
        start=100,
        end=100,
        ref="A",
        alt="G",
        source="glimpse2",
        rsid=None,
        filters=[],
        gene_symbols=["APC"],
        annotations=[{"gene": "APC", "gene_id": "ENSG00000134982", "impact": "HIGH"}],
        calls=[SmallVariantCall(sample="sample-1", gt="0/1", gq=None, dp=None, af=[], ad=[], ps=None)],
    )

    await clickhouse_variant_storage.insert_small_variant_records(
        "GRCh38",
        "family-1",
        ["project-1", "project-2"],
        [record],
    )

    annotation_query, annotation_data = next(
        (query, data)
        for query, data in executed
        if "INSERT INTO coga.`GRCh38/SNV_INDEL/variants/annotations`" in query
    )
    entry_data = next(
        data
        for query, data in executed
        if "INSERT INTO coga.`GRCh38/SNV_INDEL/entries`" in query
    )
    gene_index_data = next(
        data
        for query, data in executed
        if "INSERT INTO coga.`GRCh38/SNV_INDEL/variants/gene_index`" in query
    )

    assert "annotation_json" not in annotation_query
    assert annotation_data is not None
    assert len(annotation_data) == 1
    assert entry_data is not None
    assert len(entry_data) == 2
    assert gene_index_data is not None
    assert {row[4] for row in gene_index_data} == {"apc", "ensg00000134982"}


@pytest.mark.asyncio
async def test_rebuild_small_variant_gene_index_is_explicit_batched_maintenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed_queries: list[str] = []

    async def fake_ensure(assembly_name: str) -> None:
        assert assembly_name == "GRCh38"

    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        executed_queries.append(query)
        return []

    async def fake_status(assembly_name: str) -> dict[str, object]:
        return {"assembly_name": assembly_name, "health": "ready"}

    monkeypatch.setattr(
        clickhouse_variant_storage,
        "ensure_clickhouse_variant_tables",
        fake_ensure,
    )
    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)
    monkeypatch.setattr(
        clickhouse_variant_storage,
        "get_clickhouse_variant_storage_status",
        fake_status,
    )

    status = await clickhouse_variant_storage.rebuild_small_variant_gene_index("GRCh38")

    assert status["assembly_name"] == "GRCh38"
    assert executed_queries[0] == "TRUNCATE TABLE coga.`GRCh38/SNV_INDEL/variants/gene_index`"
    assert "INSERT INTO coga.`GRCh38/SNV_INDEL/variants/gene_index`" in executed_queries[1]
    assert "SELECT DISTINCT" in executed_queries[1]
    assert "arrayConcat(gene_symbols, gene_ids)" in executed_queries[1]


@pytest.mark.asyncio
async def test_refresh_family_small_variant_summaries_rebuilds_family_and_sample_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, dict[str, object] | None]] = []

    async def fake_ensure(assembly_name: str) -> None:
        assert assembly_name == "GRCh38"

    async def fake_execute(
        query: str,
        params: dict[str, object] | None = None,
        data=None,
    ):
        executed.append((query, params))
        return []

    monkeypatch.setattr(
        clickhouse_variant_storage,
        "ensure_clickhouse_variant_tables",
        fake_ensure,
    )
    monkeypatch.setattr(clickhouse_variant_storage, "_execute", fake_execute)

    await clickhouse_variant_storage.refresh_family_small_variant_summaries(
        "GRCh38",
        "family-1",
    )

    assert len(executed) == 4
    assert "family_variant_summary" in executed[0][0]
    assert "DELETE WHERE family_guid = %(family_guid)s" in executed[0][0]
    assert "family_sample_variant_summary" in executed[1][0]
    assert "countDistinctIf(key, length(ref) = 1 AND length(alt) = 1)" in executed[2][0]
    assert "countDistinctIf(key, gt NOT IN ('', '.', './.', '.|.', '0/0', '0|0'))" in executed[3][0]
    assert "countDistinctIf(key, gt IN ('0/1', '1/0', '0|1', '1|0'))" in executed[3][0]
    assert all(params == {"family_guid": "family-1"} for _query, params in executed)
