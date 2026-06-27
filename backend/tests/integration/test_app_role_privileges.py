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


async def _denied(sm, sql: str) -> None:
    """A statement coga_app must NOT be allowed to run (permission / ownership error)."""
    with pytest.raises(DBAPIError) as exc_info:
        async with sm() as session:
            await session.execute(text("SET LOCAL ROLE coga_app"))
            await session.execute(text(sql))
            await session.commit()
    message = str(exc_info.value).lower()
    assert "permission denied" in message or "must be owner" in message, message


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

            # Positive: coga_app may INSERT + SELECT an append-only table (no commit — the
            # INSERT executing without a permission error is the assertion).
            async with sm() as s:
                await s.execute(text("SET LOCAL ROLE coga_app"))
                await s.execute(
                    text(
                        "INSERT INTO clinical_audit_events (actor, action, summary) "
                        "VALUES ('p1-3', 'test', 'grant-check')"
                    )
                )
                await s.execute(text("SELECT 1 FROM clinical_audit_events LIMIT 1"))

            # Negative: no UPDATE / DELETE / DISABLE TRIGGER on any append-only table.
            for table in _APPEND_ONLY:
                await _denied(sm, _UPDATE_SQL[table])
                await _denied(sm, f"DELETE FROM {table}")
                await _denied(sm, f"ALTER TABLE {table} DISABLE TRIGGER USER")

            # The ON DELETE SET NULL carve-out still works for coga_app: deleting a user
            # nulls the audit FK without coga_app holding UPDATE on the append-only table,
            # so account/family deletion keeps functioning under the restricted role.
            label = f"p1-3-{uuid4()}"
            async with sm() as s:  # set up as the owner
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
                await s.commit()
            async with sm() as s:  # as coga_app: the delete + cascade must succeed
                await s.execute(text("SET LOCAL ROLE coga_app"))
                await s.execute(
                    text("DELETE FROM users WHERE id = CAST(:u AS uuid)"), {"u": uid}
                )
                await s.commit()
            async with sm() as s:  # the audit row survived, with actor_id nulled
                row = (
                    await s.execute(
                        text(
                            "SELECT actor_id FROM clinical_audit_events "
                            "WHERE family_id = CAST(:f AS uuid)"
                        ),
                        {"f": fam},
                    )
                ).first()
                assert row is not None and row[0] is None, row
        finally:
            await close_postgres_engine()

    asyncio.run(_run())
