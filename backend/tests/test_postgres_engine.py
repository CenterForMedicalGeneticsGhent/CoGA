from __future__ import annotations

import pytest

from backend.app.core import postgres as pg


@pytest.fixture
def captured_engine(monkeypatch):
    """Capture create_async_engine args and reset module state around the test."""
    captured: dict = {}

    def fake_create_async_engine(url, **kwargs):
        captured["url"] = str(url)
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(pg, "_engine", None)
    monkeypatch.setattr(pg, "_sessionmaker", None)
    monkeypatch.setattr(pg, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(pg, "async_sessionmaker", lambda *a, **k: object())
    return captured


def test_engine_uses_cloud_sql_connector_when_enabled(monkeypatch, captured_engine):
    monkeypatch.setattr(pg.settings, "postgres_use_cloud_sql_connector", True)
    monkeypatch.setattr(pg.settings, "postgres_instance_connection_name", "proj:eu-west1:coga")

    pg.get_postgres_engine()

    assert captured_engine["url"].startswith("postgresql+asyncpg")
    assert captured_engine.get("async_creator") is pg._cloud_sql_connect
    # The connector supplies TLS; no direct DSN connect_args (sslmode) in this mode.
    assert "connect_args" not in captured_engine


def test_engine_uses_dsn_when_connector_disabled(monkeypatch, captured_engine):
    monkeypatch.setattr(pg.settings, "postgres_use_cloud_sql_connector", False)

    pg.get_postgres_engine()

    assert "async_creator" not in captured_engine
    assert "connect_args" in captured_engine
