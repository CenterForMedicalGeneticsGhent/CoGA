from __future__ import annotations

import asyncio

from backend.app.services import admin_service
from backend.app.services.clickhouse_variant_storage import is_valid_clickhouse_identifier


def test_is_valid_clickhouse_identifier() -> None:
    assert is_valid_clickhouse_identifier("GRCh38")
    assert is_valid_clickhouse_identifier("T2T_CHM13v2.0")
    assert not is_valid_clickhouse_identifier("T2T CHM13v2.0")  # space
    assert not is_valid_clickhouse_identifier("")


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


def test_list_skips_assembly_names_invalid_for_clickhouse(monkeypatch) -> None:
    # An assembly named with a space ("T2T CHM13v2.0") cannot back ClickHouse
    # tables; it must be skipped, not 500 the whole listing.
    session = _FakeSession([("GRCh38",), ("T2T CHM13v2.0",)])

    async def _no_ch_assemblies():
        return set()

    async def _status(name):
        assert is_valid_clickhouse_identifier(name)  # never called for the bad name
        return _status_dict(name)

    monkeypatch.setattr(admin_service, "list_clickhouse_variant_assemblies", _no_ch_assemblies)
    monkeypatch.setattr(admin_service, "get_clickhouse_variant_storage_status", _status)

    result = asyncio.run(admin_service.list_clickhouse_variant_status(session))
    assert [a.assembly_name for a in result.assemblies] == ["GRCh38"]
