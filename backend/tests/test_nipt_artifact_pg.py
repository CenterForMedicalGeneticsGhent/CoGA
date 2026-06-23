from __future__ import annotations

import pytest

from backend.app.services import clickhouse_family_variants, nipt_artifact_pg
from backend.app.services.nipt_artifact_pg import (
    auto_seed_nipt_artifacts,
    bulk_upsert_nipt_artifacts,
    load_nipt_artifact_ids,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list = []

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_load_nipt_artifact_ids_returns_variant_id_set() -> None:
    session = _FakeSession([("1-100-A-G",), ("2-200-C-T",)])
    ids = await load_nipt_artifact_ids(
        session,  # type: ignore[arg-type]
        assembly_id="assembly-uuid",
        assay_key="nipt_cfdna",
    )
    assert ids == {"1-100-A-G", "2-200-C-T"}
    assert session.executed  # the query ran


@pytest.mark.asyncio
async def test_load_nipt_artifact_ids_short_circuits_without_assembly() -> None:
    session = _FakeSession([("1-100-A-G",)])
    ids = await load_nipt_artifact_ids(
        session,  # type: ignore[arg-type]
        assembly_id=None,
        assay_key="nipt_cfdna",
    )
    assert ids == set()
    assert session.executed == []


@pytest.mark.asyncio
async def test_fetch_recurrent_small_variant_ids_parses_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute(query, params):
        assert "HAVING carriers >=" in query
        assert params["min_samples"] == 5
        return [("1-100-A-G", 12), ("2-200-C-T", 7)]

    monkeypatch.setattr(clickhouse_family_variants, "_execute_clickhouse", fake_execute)
    result = await clickhouse_family_variants.fetch_recurrent_small_variant_ids(
        "GRCh38", min_carrier_samples=5
    )
    assert result == [("1-100-A-G", 12), ("2-200-C-T", 7)]


@pytest.mark.asyncio
async def test_fetch_recurrent_small_variant_ids_guards() -> None:
    assert await clickhouse_family_variants.fetch_recurrent_small_variant_ids(
        "", min_carrier_samples=5
    ) == []


class _AutoSeedResult:
    def __init__(self, first_row):
        self._first = first_row

    def first(self):
        return self._first


class _AutoSeedSession:
    def __init__(self, assembly_name):
        self._assembly_name = assembly_name
        self.bulk_rows = None
        self.commits = 0

    async def execute(self, statement, params=None):
        if "FROM assemblies" in str(statement):
            return _AutoSeedResult((self._assembly_name,) if self._assembly_name else None)
        self.bulk_rows = params
        return _AutoSeedResult(None)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_auto_seed_nipt_artifacts_upserts_recurrent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_recurrent(assembly_name, *, min_carrier_samples, **_kwargs):
        assert assembly_name == "GRCh38"
        assert min_carrier_samples == 5
        return [("1-100-A-G", 12), ("2-200-C-T", 7)]

    monkeypatch.setattr(nipt_artifact_pg, "fetch_recurrent_small_variant_ids", fake_recurrent)
    session = _AutoSeedSession("GRCh38")

    result = await auto_seed_nipt_artifacts(
        session,  # type: ignore[arg-type]
        assembly_id="assembly-uuid",
        assay_key="nipt_cfdna",
        min_carrier_samples=5,
    )

    assert result == {"seeded": 2, "min_carrier_samples": 5}
    assert session.bulk_rows is not None and len(session.bulk_rows) == 2
    assert session.bulk_rows[0]["source"] == "auto"


@pytest.mark.asyncio
async def test_auto_seed_nipt_artifacts_missing_assembly_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_recurrent(*_args, **_kwargs):
        return []

    monkeypatch.setattr(nipt_artifact_pg, "fetch_recurrent_small_variant_ids", fake_recurrent)
    session = _AutoSeedSession(None)

    with pytest.raises(Exception) as excinfo:
        await auto_seed_nipt_artifacts(
            session,  # type: ignore[arg-type]
            assembly_id="missing",
            assay_key="nipt_cfdna",
            min_carrier_samples=5,
        )
    assert "Assembly not found" in str(excinfo.value)


@pytest.mark.asyncio
async def test_bulk_upsert_nipt_artifacts_empty_is_noop() -> None:
    session = _AutoSeedSession("GRCh38")
    seeded = await bulk_upsert_nipt_artifacts(
        session,  # type: ignore[arg-type]
        assembly_id="assembly-uuid",
        assay_key="nipt_cfdna",
        items=[],
    )
    assert seeded == 0
    assert session.bulk_rows is None
