"""End-to-end signed chain-head anchor (real Postgres, smoke job).

Drives the real writer + the real anchor service against Postgres: a signed anchor over
the live chain heads VERIFIES; a subsequent owner-bypass re-chain (recompute a head's
row_hash) or truncation (delete a head) DIVERGES from the signed anchor; tampering an
anchor's signature is caught; and anchors chain (prev_anchor_hash). This is the evidence
that the anchor closes the P1-4 owner-re-chain / truncation gap that the in-DB chain alone
cannot detect.

Skipped unless ``RUN_INTEGRATION=1`` (see conftest.py); the CI ``smoke`` job sets it. Pure
signing/canonicalisation logic is unit-tested in ``backend/tests/test_integrity_anchor.py``.
"""

from __future__ import annotations

import asyncio
import base64
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from sqlalchemy import text

from backend.app.core.config import settings

pytestmark = pytest.mark.integration


def _gen_key_b64() -> str:
    raw = Ed25519PrivateKey.generate().private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    return base64.b64encode(raw).decode()


async def _bypass_trigger_mutate(session, table: str, sql: str, params: dict) -> None:
    await session.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
    await session.execute(text(sql), params)
    await session.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))
    await session.commit()


def test_integrity_anchor_signs_verifies_and_detects_rechain_and_truncation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "integrity_anchor_signing_key", _gen_key_b64())

    from backend.app.core.postgres import (
        close_postgres_engine,
        get_postgres_sessionmaker,
        init_postgres_schema,
    )
    from backend.app.services.clinical_audit_service import record_clinical_event
    from backend.app.services.integrity_anchor_service import (
        create_integrity_anchor,
        verify_against_latest_anchor,
    )

    async def _chain(session, family_uuid, label, n):
        for i in range(n):
            await record_clinical_event(
                session, family_uuid=family_uuid, family_identifier=label,
                variant_id=f"1-{i}-A-G", actor="alice", actor_id=None,
                action="classification", summary=f"e{i}", metadata={},
            )
        await session.commit()

    async def _fresh_family(session, label):
        return (
            await session.execute(
                text("INSERT INTO families (family_id) VALUES (:f) RETURNING id::text"),
                {"f": label},
            )
        ).scalar_one()

    async def _head_id(session, label):
        return (
            await session.execute(
                text(
                    "SELECT id::text FROM clinical_audit_events WHERE family_identifier = :f "
                    "AND row_hash IS NOT NULL ORDER BY created_at DESC, id DESC LIMIT 1"
                ),
                {"f": label},
            )
        ).scalar_one()

    async def _run() -> None:
        try:
            await init_postgres_schema()
            sm = get_postgres_sessionmaker()
            label_x = f"p1-anchor-x-{uuid4()}"

            # Build a chain and seal it with a signed anchor.
            async with sm() as s:
                fam_x = await _fresh_family(s, label_x)
                await _chain(s, fam_x, label_x, 3)
            async with sm() as s:
                a1 = await create_integrity_anchor(s)
                assert a1["algo"] == "ed25519" and a1["signature"] and a1["anchor_seq"] >= 1, a1

            # A signed anchor over the untouched chains verifies.
            async with sm() as s:
                v = await verify_against_latest_anchor(s)
                assert v.status == "ok", v

            # Owner-bypass RE-CHAIN of family X's head (recompute its row_hash) → divergence.
            async with sm() as s:
                head = await _head_id(s, label_x)
            async with sm() as s:
                await _bypass_trigger_mutate(
                    s, "clinical_audit_events",
                    "UPDATE clinical_audit_events SET row_hash = 're-chained-by-owner' "
                    "WHERE id = CAST(:id AS uuid)",
                    {"id": head},
                )
                v = await verify_against_latest_anchor(s)
                assert v.status == "diverged", v
                assert any(
                    d["family_identifier"] == label_x and d["issue"] == "rechained"
                    for d in v.diverged
                ), v.diverged

            # Fresh anchor A2 (captures current state, chains to A1); then TRUNCATE a family.
            label_y = f"p1-anchor-y-{uuid4()}"
            async with sm() as s:
                fam_y = await _fresh_family(s, label_y)
                await _chain(s, fam_y, label_y, 3)
            async with sm() as s:
                a2 = await create_integrity_anchor(s)
                assert a2["prev_anchor_hash"] == a1["anchor_hash"], (a2, a1)  # anchors chain
            async with sm() as s:
                assert (await verify_against_latest_anchor(s)).status == "ok"
            async with sm() as s:
                head_y = await _head_id(s, label_y)
                await _bypass_trigger_mutate(
                    s, "clinical_audit_events",
                    "DELETE FROM clinical_audit_events WHERE id = CAST(:id AS uuid)",
                    {"id": head_y},
                )
                v = await verify_against_latest_anchor(s)
                assert v.status == "diverged", v
                assert any(
                    d["family_identifier"] == label_y and d["issue"] == "truncated_or_shrunk"
                    for d in v.diverged
                ), v.diverged

            # Tampering the latest anchor's signature is caught before the prefix check.
            async with sm() as s:
                await _bypass_trigger_mutate(
                    s, "integrity_anchors",
                    "UPDATE integrity_anchors SET signature = 'AAAA' "
                    "WHERE anchor_seq = :seq",
                    {"seq": a2["anchor_seq"]},
                )
                v = await verify_against_latest_anchor(s)
                assert v.status == "signature_invalid", v
        finally:
            await close_postgres_engine()

    asyncio.run(_run())
