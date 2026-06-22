"""Router tests for the admin Monarch disease/phenotype search endpoint."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.core.postgres import get_postgres_session
from backend.app.main import app
from backend.app.routers import admin as admin_router
from backend.app.services.metadata_service import CurrentUser


class _FakeSession:
    async def rollback(self) -> None:  # pragma: no cover - defensive only
        return None


@pytest.fixture()
def monarch_admin_client(monkeypatch: pytest.MonkeyPatch):
    original_overrides = dict(app.dependency_overrides)
    app.state.skip_startup_tasks = True

    admin_user = CurrentUser(
        id="admin1",
        username="admin@example.com",
        email="admin@example.com",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )

    async def override_get_postgres_session():
        yield _FakeSession()

    async def override_get_current_admin_user():
        return admin_user

    app.dependency_overrides[get_postgres_session] = override_get_postgres_session
    app.dependency_overrides[admin_router.get_current_admin_user] = (
        override_get_current_admin_user
    )

    with TestClient(app) as client:
        yield client, monkeypatch

    app.dependency_overrides = original_overrides


def test_monarch_search_returns_diseases_with_links(monarch_admin_client) -> None:
    client, monkeypatch = monarch_admin_client

    captured: dict[str, object] = {}

    async def fake_search(session, *, query, limit):
        captured["query"] = query
        captured["limit"] = limit
        return {
            "query": query,
            "total": 1,
            "diseases": [
                {
                    "mondo_id": "MONDO:0007739",
                    "disease_label": "Huntington disease",
                    "match_type": "disease",
                    "gene_count": 1,
                    "genes": [
                        {
                            "gene_symbol": "HTT",
                            "hgnc_id": "HGNC:4851",
                            "predicate": "causes",
                            "causal": True,
                        }
                    ],
                    "phenotype_count": 2,
                    "matched_phenotype_count": 0,
                    "phenotypes": [
                        {
                            "hpo_id": "HP:0002072",
                            "phenotype_label": "Chorea",
                            "matched": False,
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(admin_router, "search_monarch_associations", fake_search)

    response = client.get("/api/admin/monarch/search?q=huntington&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert captured == {"query": "huntington", "limit": 10}
    assert body["total"] == 1
    disease = body["diseases"][0]
    assert disease["mondo_id"] == "MONDO:0007739"
    assert disease["match_type"] == "disease"
    assert disease["genes"][0]["gene_symbol"] == "HTT"
    assert disease["genes"][0]["causal"] is True
    assert disease["phenotypes"][0]["hpo_id"] == "HP:0002072"


def test_monarch_search_rejects_out_of_range_limit(monarch_admin_client) -> None:
    client, _ = monarch_admin_client

    response = client.get("/api/admin/monarch/search?q=seizure&limit=500")

    assert response.status_code == 422
