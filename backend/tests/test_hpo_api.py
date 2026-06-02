from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.core.postgres import get_postgres_session
from backend.app.main import app
from backend.app.routers import families as families_router
from backend.app.routers import hpo as hpo_router
from backend.app.services.metadata_service import CurrentUser


@dataclass
class _FakeFamilyContext:
    family_uuid: str = "11111111-1111-1111-1111-111111111111"
    family_id: str = "FAM1"


@pytest.fixture()
def hpo_api_client(monkeypatch: pytest.MonkeyPatch):
    original_overrides = dict(app.dependency_overrides)
    app.state.skip_startup_tasks = True

    user = CurrentUser(
        id="user1",
        username="viewer@example.com",
        email="viewer@example.com",
        role="viewer",
        created_at=datetime.now(timezone.utc),
    )

    async def override_get_postgres_session():
        yield object()

    async def override_get_current_user():
        return user

    async def override_get_current_admin_user():
        return user.model_copy(update={"role": "admin"})

    app.dependency_overrides[get_postgres_session] = override_get_postgres_session
    app.dependency_overrides[hpo_router.get_current_user] = override_get_current_user
    app.dependency_overrides[hpo_router.get_current_admin_user] = override_get_current_admin_user
    app.dependency_overrides[families_router.get_current_user] = override_get_current_user

    with TestClient(app) as client:
        yield client, monkeypatch

    app.dependency_overrides = original_overrides


def test_hpo_search_and_detail_endpoints(hpo_api_client) -> None:
    client, monkeypatch = hpo_api_client

    async def fake_search(*args, **kwargs):
        return [
            {
                "hpo_id": "HP:0001250",
                "label": "Seizure",
                "definition": "A seizure phenotype.",
                "is_obsolete": False,
            }
        ]

    async def fake_details(*args, **kwargs):
        return {
            "hpo_id": "HP:0001250",
            "label": "Seizure",
            "definition": "A seizure phenotype.",
            "is_obsolete": False,
            "replaced_by": None,
            "release_version": "test",
            "release_date": None,
            "synonyms": ["Epileptic seizure"],
            "parents": [],
            "children": [],
        }

    monkeypatch.setattr(hpo_router, "search_hpo_terms", fake_search)
    monkeypatch.setattr(hpo_router, "get_hpo_term_details", fake_details)

    search_response = client.get("/hpo/search?q=seizure")
    detail_response = client.get("/hpo/HP:0001250")

    assert search_response.status_code == 200
    assert search_response.json()[0]["hpo_id"] == "HP:0001250"
    assert detail_response.status_code == 200
    assert detail_response.json()["synonyms"] == ["Epileptic seizure"]


def test_family_hpo_annotation_endpoints(hpo_api_client) -> None:
    client, monkeypatch = hpo_api_client
    now = datetime.now(timezone.utc)
    annotation = {
        "id": "22222222-2222-2222-2222-222222222222",
        "sample_id": "PROBAND",
        "hpo_id": "HP:0001250",
        "label": "Seizure",
        "status": "present",
        "onset": None,
        "evidence": None,
        "source": "manual",
        "note": None,
        "created_at": now,
        "updated_at": now,
    }

    async def fake_context(*args, **kwargs):
        return _FakeFamilyContext()

    async def fake_list(*args, **kwargs):
        return [annotation]

    async def fake_create(*args, **kwargs):
        return annotation

    async def fake_query(*args, **kwargs):
        return {
            "hpo_id": "HP:0001250",
            "include_descendants": True,
            "sample_ids": ["PROBAND"],
            "annotations": [annotation],
        }

    monkeypatch.setattr(families_router, "build_family_metadata_context", fake_context)
    monkeypatch.setattr(families_router, "list_family_hpo_annotations", fake_list)
    monkeypatch.setattr(families_router, "create_individual_hpo_annotation", fake_create)
    monkeypatch.setattr(families_router, "query_family_hpo_annotations", fake_query)

    list_response = client.get("/families/FAM1/hpo")
    create_response = client.post(
        "/families/FAM1/members/PROBAND/hpo",
        json={"hpo_id": "HP:0001250", "status": "present"},
    )
    query_response = client.get("/families/FAM1/hpo/query?hpo_id=HP:0001250")

    assert list_response.status_code == 200
    assert list_response.json()[0]["sample_id"] == "PROBAND"
    assert create_response.status_code == 200
    assert create_response.json()["hpo_id"] == "HP:0001250"
    assert query_response.status_code == 200
    assert query_response.json()["sample_ids"] == ["PROBAND"]
