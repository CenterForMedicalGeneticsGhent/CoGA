from __future__ import annotations

import pytest

from backend.app.services.clickhouse_family_variants import _fetch_panel_constraints


class _MappingResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class _PanelConstraintSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement, params: dict[str, object]):
        sql = str(statement)
        self.statements.append(sql)
        if "FROM gene_panel_genes" in sql:
            return _MappingResult([{"gene_symbol": "GENE1"}])
        if "FROM gene_panel_regions" in sql:
            return _MappingResult([{"gene": "GENE1", "chr": "1", "start": 10, "end": 20}])
        if "FROM genes" in sql:
            return _MappingResult([{"chr": "2", "start": 100, "end": 200}])
        return _MappingResult([])


@pytest.mark.asyncio
async def test_panel_constraints_include_family_assembly_gene_regions() -> None:
    session = _PanelConstraintSession()

    constraints = await _fetch_panel_constraints(
        session,
        "d67e635c-7d98-4495-8b3c-153f5007561b",
        assembly_id="5ddde908-e97d-4f60-95cb-3a6f9f8173d3",
    )

    assert constraints.genes == ("GENE1",)
    assert [(region.chr, region.start, region.end) for region in constraints.regions] == [
        ("1", 10, 20),
        ("2", 100, 200),
    ]
    assert any("FROM genes" in statement for statement in session.statements)


@pytest.mark.asyncio
async def test_panel_constraints_skip_dynamic_regions_without_assembly() -> None:
    session = _PanelConstraintSession()

    constraints = await _fetch_panel_constraints(
        session,
        "d67e635c-7d98-4495-8b3c-153f5007561b",
    )

    assert [(region.chr, region.start, region.end) for region in constraints.regions] == [
        ("1", 10, 20),
    ]
    assert not any("FROM genes" in statement for statement in session.statements)
