"""Liveness and readiness probes (unauthenticated, no PHI).

``/api/health`` is a pure liveness check used by the container healthcheck, the
CI smoke test and the frontend proxy. It returns 200 as soon as the application
has finished starting up — exactly the signal that was missing when the backend
crash-looped on startup and the only symptom was "Unable to reach API".

``/api/health/ready`` additionally confirms Postgres and ClickHouse are
reachable, returning 503 when a datastore is down so an orchestrator can hold
traffic until the backend is truly ready.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..core.clickhouse import execute_clickhouse
from ..core.postgres import get_postgres_sessionmaker

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: 200 once the app has started. Touches no dependencies."""
    return {"status": "ok"}


async def _postgres_ok() -> bool:
    try:
        session_factory = get_postgres_sessionmaker()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — any failure means "not ready", never raise
        return False


async def _clickhouse_ok() -> bool:
    try:
        await execute_clickhouse("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 — any failure means "not ready", never raise
        return False


@router.get("/health/ready")
async def ready(response: Response) -> dict[str, Any]:
    """Readiness: 200 only when both Postgres and ClickHouse are reachable."""
    postgres_ok = await _postgres_ok()
    clickhouse_ok = await _clickhouse_ok()
    if not (postgres_ok and clickhouse_ok):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if postgres_ok and clickhouse_ok else "degraded",
        "postgres": "ok" if postgres_ok else "down",
        "clickhouse": "ok" if clickhouse_ok else "down",
    }
