"""Login must not leak account existence through response timing.

The no-such-account branch used to return before calling ``verify_password``,
so only real accounts paid the bcrypt cost — a measurable enumeration oracle.
The handler now runs a throwaway verify against a constant hash on that branch.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.postgres import get_postgres_session
from backend.app.main import app
from backend.app.routers import auth as auth_router


class _FakeSession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.fixture()
def login_client(monkeypatch: pytest.MonkeyPatch):
    original_overrides = dict(app.dependency_overrides)
    app.state.skip_startup_tasks = True

    async def override_get_postgres_session():
        yield _FakeSession()

    app.dependency_overrides[get_postgres_session] = override_get_postgres_session
    with TestClient(app) as client:
        yield client, monkeypatch
    app.dependency_overrides = original_overrides


def _login_payload() -> dict:
    return {"email": "ghost@example.com", "password": "whatever-password"}


def test_login_runs_dummy_verify_when_account_missing(login_client) -> None:
    client, monkeypatch = login_client
    calls = {"verify": 0}

    async def no_throttle(session, *, email, remote_ip, now=None):
        return None

    async def no_such_user(session, email):
        return None

    async def record(session, *, email, remote_ip, now=None):
        return None

    def counting_verify(password, hashed):
        calls["verify"] += 1
        return False

    monkeypatch.setattr(auth_router, "get_login_throttle_state", no_throttle)
    monkeypatch.setattr(auth_router, "get_auth_user_mapping_by_email", no_such_user)
    monkeypatch.setattr(auth_router, "record_failed_login", record)
    monkeypatch.setattr(auth_router, "verify_password", counting_verify)

    response = client.post("/api/auth/login", json=_login_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"
    # The dummy verify runs even though the account doesn't exist, so the response
    # time doesn't distinguish "no such account" from "wrong password".
    assert calls["verify"] == 1


def test_dummy_login_hash_is_a_valid_bcrypt_hash() -> None:
    from backend.app.dependencies import verify_password

    # The equalizer hash must actually be verifiable (a malformed constant would
    # make the dummy verify cheap/raise and defeat the point).
    assert auth_router._DUMMY_LOGIN_PASSWORD_HASH.startswith("$2")
    assert verify_password("coga-login-timing-equalizer", auth_router._DUMMY_LOGIN_PASSWORD_HASH)
    assert not verify_password("wrong", auth_router._DUMMY_LOGIN_PASSWORD_HASH)
