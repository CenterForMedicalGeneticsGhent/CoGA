"""Integrity-check SQL validated against a real ClickHouse server.

The unit tests mock `_execute`; this confirms the system-table / CHECK TABLE /
detached-parts SQL actually parses and runs on ClickHouse and returns a
well-formed report. It is state-agnostic: the CI ClickHouse is empty (``missing``)
while a populated server may report ``ok``/``degraded`` — both are valid here.

Skipped unless RUN_INTEGRATION=1 (see conftest.py); the CI ``smoke`` job sets it.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.integration


def test_integrity_check_runs_against_real_clickhouse() -> None:
    from backend.app.core.clickhouse import close_clickhouse_client
    from backend.app.services.clickhouse_variant_storage import (
        check_clickhouse_variant_integrity,
    )

    async def _run():
        try:
            return await check_clickhouse_variant_integrity("GRCh38")
        finally:
            # Close within this loop so no client leaks to another test's loop.
            await close_clickhouse_client()

    report = asyncio.run(_run())
    # The SQL ran cleanly and produced a well-formed report (status valid, blocks
    # present) — independent of whether this server has variant data.
    assert report["status"] in {"ok", "degraded", "corrupt", "missing"}
    assert isinstance(report["table_checks"], list)
    assert isinstance(report["detached_broken_parts"], list)
    assert "checked" in report["gene_index_consistency"]
