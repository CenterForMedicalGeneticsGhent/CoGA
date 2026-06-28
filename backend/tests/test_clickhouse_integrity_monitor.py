"""P2-6: the scheduled ClickHouse integrity monitor sweeps, escalates, and caches."""

from __future__ import annotations

import asyncio
import logging

import pytest

from backend.app.core.config import settings
from backend.app.services import clickhouse_integrity_monitor as mon


@pytest.fixture(autouse=True)
def _reset():
    mon._last_results.clear()
    yield
    mon._last_results.clear()


def _patch(monkeypatch, assemblies, results):
    async def fake_list():
        return assemblies

    async def fake_check(name):
        value = results[name]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(mon, "list_clickhouse_variant_assemblies", fake_list)
    monkeypatch.setattr(mon, "check_clickhouse_variant_integrity", fake_check)


def test_sweep_caches_and_escalates_by_status(monkeypatch, caplog):
    _patch(
        monkeypatch,
        ["GRCh38", "GRCh37"],
        {
            "GRCh38": {"status": "ok", "notes": []},
            "GRCh37": {"status": "corrupt", "notes": ["bad part"]},
        },
    )
    with caplog.at_level(logging.INFO, logger=mon.logger.name):
        out = asyncio.run(mon.run_integrity_sweep())
    assert out["GRCh37"]["status"] == "corrupt"
    assert mon.last_integrity_results()["GRCh37"]["status"] == "corrupt"
    # corrupt -> ERROR; ok -> INFO
    assert any(r.levelno == logging.ERROR and "GRCh37" in r.getMessage() for r in caplog.records)
    assert any(r.levelno == logging.INFO and "GRCh38" in r.getMessage() for r in caplog.records)


def test_sweep_warns_on_degraded(monkeypatch, caplog):
    _patch(monkeypatch, ["GRCh38"], {"GRCh38": {"status": "degraded", "notes": ["detached"]}})
    with caplog.at_level(logging.WARNING, logger=mon.logger.name):
        asyncio.run(mon.run_integrity_sweep())
    assert any(r.levelno == logging.WARNING and "degraded" in r.getMessage() for r in caplog.records)


def test_sweep_survives_check_and_list_exceptions(monkeypatch):
    _patch(monkeypatch, ["GRCh38"], {"GRCh38": RuntimeError("boom")})
    assert asyncio.run(mon.run_integrity_sweep()) == {}  # check raised -> nothing cached, no raise

    async def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(mon, "list_clickhouse_variant_assemblies", boom)
    assert asyncio.run(mon.run_integrity_sweep()) == {}  # list raised -> no raise


def test_start_is_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "clickhouse_integrity_monitor_enabled", False)

    async def _go():
        await mon.start_clickhouse_integrity_monitor()
        assert mon._worker_task is None
        await mon.stop_clickhouse_integrity_monitor()

    asyncio.run(_go())


def test_worker_sweeps_then_stops_cleanly(monkeypatch):
    monkeypatch.setattr(settings, "clickhouse_integrity_monitor_enabled", True)
    monkeypatch.setattr(settings, "clickhouse_integrity_startup_delay_seconds", 0)
    monkeypatch.setattr(settings, "clickhouse_integrity_interval_seconds", 60)
    sweeps = {"n": 0}

    async def fake_sweep():
        sweeps["n"] += 1
        return {}

    monkeypatch.setattr(mon, "run_integrity_sweep", fake_sweep)

    async def _go():
        await mon.start_clickhouse_integrity_monitor()
        await asyncio.sleep(0.1)  # let the initial (0-delay) sweep run
        await mon.stop_clickhouse_integrity_monitor()
        assert mon._worker_task is None

    asyncio.run(_go())
    assert sweeps["n"] >= 1
