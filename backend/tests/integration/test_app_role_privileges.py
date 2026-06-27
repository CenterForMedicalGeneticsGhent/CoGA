"""P1-3: the restricted runtime role `coga_app` cannot bypass the append-only controls.

Verifying evidence for the privilege separation that closes P1-4's owner-bypass gap. As
`coga_app` (assumed via ``SET LOCAL ROLE`` — auto-resets at transaction end, so no pooled
connection keeps the role) the test asserts:
- it MAY ``INSERT`` + ``SELECT`` the append-only tables (the app's real access), and
- it MAY still delete a user whose ``ON DELETE SET NULL`` cascade nulls an audit FK (so
  account/family deletion keeps working without UPDATE on the append-only table), but
- it may NOT ``UPDATE`` / ``DELETE`` those tables nor ``DISABLE`` their triggers — i.e. it
  cannot rewrite/remove audit rows, signed reports or the hash-chain columns, and cannot
  re-chain an interior edit.

Skipped unless ``RUN_INTEGRATION=1`` (see conftest.py); the CI ``smoke`` job sets it. The
test connects as the migration owner/superuser, which can ``SET ROLE`` to the NOLOGIN
``coga_app`` to exercise exactly its privilege set.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration

_APPEND_ONLY = ("audit_log_events", "clinical_audit_events", "report_signouts")

# A syntactically-valid UPDATE per table (a real column); the privilege check fires before
# the row scan, so a no-op SET still surfaces "permission denied" for coga_app.
_UPDATE_SQL = {
    "audit_log_events": "UPDATE audit_log_events SET status_code = 200",
    "clinical_audit_events": "UPDATE clinical_audit_events SET summary = summary",
    "report_signouts": "UPDATE report_signouts SET signed_out_by = signed_out_by",
}


async def _denied(sm, sql: str, expect: str) -> None:
    """A statement coga_app must NOT be allowed to run; pin the exact refusal reason
    (``permission denied`` from the REVOKE vs ``must be owner`` from DISABLE TRIGGER) so a
    dropped REVOKE can't be masked by the ownership check still failing."""
    with pytest.raises(DBAPIError) as exc_info:
        async with sm() as session:
            await session.execute(text("SET LOCAL ROLE coga_app"))
            await session.execute(text(sql))
            await session.commit()
    assert expect in str(exc_info.value).lower(), str(exc_info.value)


def test_coga_app_role_is_locked_out_of_append_only_mutations() -> None:
    from backend.app.core.postgres import (
        close_postgres_engine,
        get_postgres_sessionmaker,
        init_postgres_schema,
    )

    async def _run() -> None:
        try:
            await init_postgres_schema()
            sm = get_postgres_sessionmaker()

            # Positive: coga_app may INSERT then read its own durable write back.
            marker = f"p1-3-grant-{uuid4()}"
            async with sm() as s:
                await s.execute(text("SET LOCAL ROLE coga_app"))
                await s.execute(
                    text(
                        "INSERT INTO clinical_audit_events (actor, action, summary) "
                        "VALUES ('p1-3', 'test', :m)"
                    ),
                    {"m": marker},
                )
                await s.commit()
            async with sm() as s:
                await s.execute(text("SET LOCAL ROLE coga_app"))
                found = (
                    await s.execute(
                        text("SELECT 1 FROM clinical_audit_events WHERE summary = :m"),
                        {"m": marker},
                    )
                ).first()
                assert found is not None  # coga_app's committed INSERT is readable by coga_app

            # Negative: no UPDATE / DELETE (REVOKE → "permission denied") and no DISABLE
            # TRIGGER (non-owner → "must be owner") on any append-only table.
            for table in _APPEND_ONLY:
                await _denied(sm, _UPDATE_SQL[table], "permission denied")
                await _denied(sm, f"DELETE FROM {table}", "permission denied")
                await _denied(sm, f"ALTER TABLE {table} DISABLE TRIGGER USER", "must be owner")

            # The ON DELETE SET NULL carve-out still works for coga_app on ALL THREE
            # append-only tables: deleting a user nulls each table's user FK without
            # coga_app holding UPDATE on them, so account/family deletion keeps functioning.
            label = f"p1-3-{uuid4()}"
            async with sm() as s:  # set up as the owner: one row per append-only table
                fam = (
                    await s.execute(
                        text("INSERT INTO families (family_id) VALUES (:f) RETURNING id::text"),
                        {"f": label},
                    )
                ).scalar_one()
                uid = (
                    await s.execute(
                        text(
                            "INSERT INTO users (username, hashed_password, role, email) "
                            "VALUES (:u, 'x', 'viewer', :e) RETURNING id::text"
                        ),
                        {"u": f"p1-3-{uuid4()}", "e": f"p1-3-{uuid4()}@x.org"},
                    )
                ).scalar_one()
                await s.execute(
                    text(
                        "INSERT INTO clinical_audit_events (family_id, actor_id, actor, "
                        "action, summary) VALUES (CAST(:f AS uuid), CAST(:u AS uuid), "
                        "'x', 'test', 'cascade')"
                    ),
                    {"f": fam, "u": uid},
                )
                await s.execute(
                    text(
                        "INSERT INTO audit_log_events (method, path, status_code, user_id) "
                        "VALUES ('GET', :p, 200, CAST(:u AS uuid))"
                    ),
                    {"p": f"/p1-3-cascade-{label}", "u": uid},
                )
                await s.execute(
                    text(
                        "INSERT INTO report_signouts (family_id, family_identifier, version, "
                        "signed_out_by, signed_out_by_id, content_hash, snapshot) VALUES "
                        "(CAST(:f AS uuid), :fl, 1, 'x', CAST(:u AS uuid), 'deadbeef', '{}'::jsonb)"
                    ),
                    {"f": fam, "fl": label, "u": uid},
                )
                await s.commit()
            async with sm() as s:  # as coga_app: the delete + 3-way cascade must succeed
                await s.execute(text("SET LOCAL ROLE coga_app"))
                await s.execute(
                    text("DELETE FROM users WHERE id = CAST(:u AS uuid)"), {"u": uid}
                )
                await s.commit()
            async with sm() as s:  # every audit row survived, with its user FK nulled
                cae = (
                    await s.execute(
                        text("SELECT actor_id FROM clinical_audit_events WHERE family_id = CAST(:f AS uuid)"),
                        {"f": fam},
                    )
                ).first()
                ale = (
                    await s.execute(
                        text("SELECT user_id FROM audit_log_events WHERE path = :p"),
                        {"p": f"/p1-3-cascade-{label}"},
                    )
                ).first()
                rso = (
                    await s.execute(
                        text("SELECT signed_out_by_id FROM report_signouts WHERE family_identifier = :fl"),
                        {"fl": label},
                    )
                ).first()
                assert cae is not None and cae[0] is None, cae
                assert ale is not None and ale[0] is None, ale
                assert rso is not None and rso[0] is None, rso
        finally:
            await close_postgres_engine()

    asyncio.run(_run())
