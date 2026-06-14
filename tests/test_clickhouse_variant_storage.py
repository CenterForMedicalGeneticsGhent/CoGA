import pytest

from backend.app.services import clickhouse_variant_storage as cvs


@pytest.mark.asyncio
async def test_count_family_small_variants_by_family_builds_scoped_group_by(monkeypatch) -> None:
    captured: dict = {}

    async def fake_ensure(assembly_name):
        return None

    async def fake_execute(query, params=None, data=None):
        captured["query"] = query
        captured["params"] = params
        return [("fam-1", 15), ("fam-2", 7)]

    monkeypatch.setattr(cvs, "ensure_clickhouse_variant_tables", fake_ensure)
    monkeypatch.setattr(cvs, "_execute", fake_execute)

    out = await cvs.count_family_small_variants_by_family(
        "GRCh38",
        family_project_pairs=[("fam-1", "p1"), ("fam-2", "p2")],
        families_without_project=["fam-3"],
    )

    assert out == {"fam-1": 15, "fam-2": 7}
    query = captured["query"]
    # Exact per-family project scope via tuple-IN, plus an unscoped OR term.
    assert "(family_guid, project_guid) IN %(family_project_pairs)s" in query
    assert "family_guid IN %(families_without_project)s" in query
    assert "GROUP BY family_guid" in query
    # Counts via the exact nested count(), not approximate count(DISTINCT).
    assert "GROUP BY family_guid, key" in query
    # tuple-of-tuples so clickhouse-connect renders ClickHouse tuple-IN syntax.
    assert captured["params"]["family_project_pairs"] == (("fam-1", "p1"), ("fam-2", "p2"))
    assert captured["params"]["families_without_project"] == ("fam-3",)


@pytest.mark.asyncio
async def test_count_family_by_family_skips_query_when_no_scope(monkeypatch) -> None:
    calls = {"execute": 0}

    async def fake_ensure(assembly_name):
        return None

    async def fake_execute(query, params=None, data=None):
        calls["execute"] += 1
        return []

    monkeypatch.setattr(cvs, "ensure_clickhouse_variant_tables", fake_ensure)
    monkeypatch.setattr(cvs, "_execute", fake_execute)

    out = await cvs.count_family_structural_variants_by_family(
        "GRCh38", family_project_pairs=[], families_without_project=[]
    )
    assert out == {}
    assert calls["execute"] == 0
