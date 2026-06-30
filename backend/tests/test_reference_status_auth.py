from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.core.postgres import get_postgres_session
from backend.app.dependencies import get_current_user
from backend.app.main import app
from backend.app.routers import assemblies as assemblies_router
from backend.app.services.metadata_service import CurrentUser


class _FakeSession:
    async def rollback(self) -> None:
        return None


@pytest.fixture()
def reference_status_client(monkeypatch: pytest.MonkeyPatch):
    original_overrides = dict(app.dependency_overrides)
    app.state.skip_startup_tasks = True

    async def override_get_postgres_session():
        yield _FakeSession()

    app.dependency_overrides[get_postgres_session] = override_get_postgres_session

    with TestClient(app) as client:
        yield client, monkeypatch

    app.dependency_overrides = original_overrides


def test_reference_status_requires_authentication(reference_status_client) -> None:
    client, _monkeypatch = reference_status_client

    # The response embeds import provenance (source + performed-by operator email),
    # so an unauthenticated request must be rejected before any data is returned.
    response = client.get("/api/assemblies/reference-status")

    assert response.status_code == 401


def test_reference_status_returns_data_for_authenticated_user(reference_status_client) -> None:
    client, monkeypatch = reference_status_client

    user = CurrentUser(
        id="u1",
        username="viewer@example.com",
        email="viewer@example.com",
        role="viewer",
        created_at=datetime.now(timezone.utc),
    )

    async def override_get_current_user():
        return user

    async def fake_list_reference_statuses(session):
        return []

    app.dependency_overrides[get_current_user] = override_get_current_user
    monkeypatch.setattr(
        assemblies_router, "list_reference_statuses", fake_list_reference_statuses
    )

    # A plain (non-admin) signed-in user may still read the reference-data page.
    response = client.get("/api/assemblies/reference-status")

    assert response.status_code == 200
    assert response.json() == []
