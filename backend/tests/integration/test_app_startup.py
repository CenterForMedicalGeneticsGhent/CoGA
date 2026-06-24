"""End-to-end startup smoke test against real Postgres + ClickHouse.

This boots the application through its real lifespan — Postgres schema init
(including the dollar-quoted append-only audit trigger), the admin-user seed and
the ClickHouse schema init — which is the exact path that crash-looped on startup
and made the API unreachable. Heavy reference/HPO/gene bootstrap is disabled via
env so the boot needs no large data files.

Skipped unless RUN_INTEGRATION=1 (see conftest.py); the CI ``smoke`` job sets it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_app_boots_against_real_datastores_and_serves() -> None:
    from backend.app.main import app

    # TestClient's context manager runs startup (and shutdown) — a schema-apply
    # failure here would raise and fail the test, exactly as it crash-looped live.
    with TestClient(app) as client:
        live = client.get("/api/health")
        assert live.status_code == 200
        assert live.json() == {"status": "ok"}

        # Routing + auth are wired against the running app.
        assert client.get("/api/projects/").status_code == 401

        # Both datastores came up and their schemas applied.
        ready = client.get("/api/health/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ok", "postgres": "ok", "clickhouse": "ok"}
