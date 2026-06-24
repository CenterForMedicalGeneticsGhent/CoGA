from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_liveness_and_routing_without_datastores() -> None:
    """The app mounts health + the API routers without touching Postgres/ClickHouse.

    Boots with startup tasks skipped, so this needs no datastores and runs in the
    normal backend job. It catches import / router-wiring / middleware crashes —
    the kind that previously only surfaced at runtime as "Unable to reach API".
    """
    app.state.skip_startup_tasks = True
    try:
        with TestClient(app) as client:
            live = client.get("/api/health")
            assert live.status_code == 200
            assert live.json() == {"status": "ok"}

            # Routing, auth and middleware are wired: an unauthenticated data route
            # is rejected with 401 — not a 404 (missing) or 500 (broken wiring).
            assert client.get("/api/projects/").status_code == 401
    finally:
        app.state.skip_startup_tasks = False
