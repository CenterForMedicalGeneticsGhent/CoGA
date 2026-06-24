from __future__ import annotations

import asyncio

from backend.app.services import admin_service


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, *args, **kwargs):
        return _FakeResult(self._rows)


def _status_dict(name: str) -> dict:
    return {
        "assembly_name": name,
        "health": "ready",
        "expected_table_count": 12,
        "existing_table_count": 12,
        "missing_tables": [],
        "pending_mutations": 0,
        "total_rows": 0,
        "total_bytes_on_disk": 0,
        "small_variant_rows": 0,
        "structural_variant_rows": 0,
        "tables": [],
    }


def _patch(monkeypatch, ch_keys):
    async def _ch():
        return set(ch_keys)

    async def _status(name):
        return _status_dict(name)

    monkeypatch.setattr(admin_service, "list_clickhouse_variant_assemblies", _ch)
    monkeypatch.setattr(admin_service, "get_clickhouse_variant_storage_status", _status)


def test_list_normalizes_assembly_names_for_clickhouse(monkeypatch) -> None:
    # "T2T CHM13v2.0" (a space) is normalized to its dataset key and listed,
    # not skipped and not a 500.
    _patch(monkeypatch, ch_keys=set())
    session = _FakeSession([("GRCh38",), ("T2T CHM13v2.0",)])
    result = asyncio.run(admin_service.list_clickhouse_variant_status(session))
    assert sorted(a.assembly_name for a in result.assemblies) == ["GRCh38", "T2T_CHM13v2.0"]


def test_list_dedups_pg_name_against_clickhouse_key(monkeypatch) -> None:
    # The Postgres name and the ClickHouse-derived key both reduce to the same
    # dataset key, so the assembly appears once.
    _patch(monkeypatch, ch_keys={"T2T_CHM13v2.0"})
    session = _FakeSession([("T2T CHM13v2.0",)])
    result = asyncio.run(admin_service.list_clickhouse_variant_status(session))
    assert [a.assembly_name for a in result.assemblies] == ["T2T_CHM13v2.0"]
