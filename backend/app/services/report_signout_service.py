"""Case sign-out — frozen, versioned, hashed report snapshot (clinical traceability,
Phase 3; see docs/clinical-traceability.md).

Signing out a case freezes the reported result to exactly what produced it: the
annotation/reference versions (the manifest), the reported variant list, each
classification with its frozen evidence snapshot, and the evidence-drift state at the
moment of sign-out. The snapshot is content-hashed (SHA-256) and written append-only
into ``report_signouts`` as a new version; the sign-out is recorded in the immutable
clinical audit trail.

Sign-out is gated on evidence drift: if any classification's backing annotation has
changed since it was made, the caller must explicitly acknowledge the drift.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from .annotation_manifest_service import get_family_annotation_manifest
from .classification_drift_service import evaluate_classification_drift
from .clinical_audit_service import record_clinical_event
from .family_metadata_context import build_family_metadata_context
from .metadata_service import CurrentUser
from .sample_integrity_qc import SampleIntegrityReport
from .sample_integrity_service import get_family_sample_integrity_qc

_REPORT_TAG = "report"

# Sample-integrity QC statuses that BLOCK sign-out unless acknowledged with a reason.
# Per clinical policy, only a hard "fail" (a detected sample/pedigree swap — TF-06 H4,
# rated S5 catastrophic) blocks; "warn"/"skip" are frozen + surfaced but do not gate.
_QC_BLOCKING_STATUSES = {"fail"}


def _canonical_hash(snapshot: dict[str, Any]) -> str:
    """SHA-256 over a canonical (sorted-key) JSON encoding — stable + tamper-evident."""
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_sample_qc(report: SampleIntegrityReport) -> dict[str, Any]:
    """Deterministic dict of the Sample-integrity QC, for freezing into the snapshot.

    The report is a pure function of the deterministically-ordered input genotypes
    (counts/rates/inferred labels — no timestamps, no RNG), so ``dataclasses.asdict``
    yields a structure that content-hashes reproducibly for identical clinical content.
    """
    return dataclasses.asdict(report)


def _qc_failure_summary(qc: dict[str, Any]) -> dict[str, Any]:
    """Compact summary of the concerning QC checks, for the 409 acknowledge prompt."""
    messages: list[str] = []
    for key in ("sex_checks", "relatedness_checks", "mendelian_checks"):
        for check in qc.get(key) or []:
            if check.get("status") in ("warn", "fail"):
                messages.append(check.get("message") or "")
    for key in ("paternity_check", "fetal_sex_check", "category_qc_check"):
        check = qc.get(key)
        if check and check.get("status") in ("warn", "fail"):
            messages.append(check.get("message") or "")
    return {
        "overall_status": qc.get("overall_status"),
        "application_label": qc.get("application_label"),
        "messages": [m for m in messages if m],
    }


async def _reported_reviews(session: AsyncSession, family_uuid: str) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                """
                SELECT variant_id, acmg_class, acmg, tags, note, acmg_evidence_snapshot
                FROM small_variant_reviews
                WHERE family_id = CAST(:family_uuid AS uuid)
                  AND tags @> :report_tag
                ORDER BY variant_id
                """
            ),
            {"family_uuid": family_uuid, "report_tag": json.dumps([_REPORT_TAG])},
        )
    ).mappings().all()
    reported: list[dict[str, Any]] = []
    for row in rows:
        reported.append(
            {
                "variant_id": row["variant_id"],
                "acmg_class": row["acmg_class"],
                "acmg": row["acmg"],
                "tags": sorted(row["tags"] or []),
                "note": row["note"],
                "evidence_snapshot": row["acmg_evidence_snapshot"],
            }
        )
    return reported


async def build_report_snapshot(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Assemble (but do not persist) the frozen report snapshot for a family."""
    context = await build_family_metadata_context(
        session, family_identifier=family_id, user=user, project_id=project_id
    )
    manifest = await get_family_annotation_manifest(
        session, family_id=family_id, user=user, project_id=project_id
    )
    drift = await evaluate_classification_drift(
        session, family_id=family_id, user=user, project_id=project_id
    )
    qc_report = await get_family_sample_integrity_qc(
        session, family_id=family_id, user=user, project_id=project_id
    )
    reported = await _reported_reviews(session, context.family_uuid)
    return {
        "family_id": context.family_id,
        "assembly": manifest.get("assembly"),
        "modules": manifest.get("modules", []),
        # Build identity of the software that produced this snapshot, frozen into the
        # content hash so a signed report is bound to the exact code that made it.
        # These are build-time constants (no per-call/runtime-varying value), so the
        # hash stays deterministic for identical clinical content.
        "software": {"version": settings.app_version, "git_sha": settings.git_sha},
        "drift": {
            "checked": drift["checked"],
            "drifted_count": drift["drifted_count"],
            # The live drift endpoint orders drifted rows by updated_at (non-unique),
            # so the list order is non-deterministic on ties. Sort by the unique,
            # stable variant_id here so the hashed snapshot (content_hash) is
            # reproducible for identical content; json.dumps(sort_keys=True) canonicalizes
            # dict keys but never list-element order. Scoped to the sign-out/hash path
            # only — the endpoint keeps its most-recent-first display order.
            "drifted": sorted(
                drift["drifted"], key=lambda item: item.get("variant_id") or ""
            ),
        },
        # Sample-integrity QC (sample/pedigree-swap detection) frozen into the content
        # hash so the signed record proves QC was run and exactly what it found. A pure
        # function of the deterministically-ordered input genotypes, so it hashes stably.
        "sample_qc": _canonical_sample_qc(qc_report),
        "reported_variants": reported,
    }


async def _next_version(session: AsyncSession, family_uuid: str) -> int:
    result = await session.execute(
        text(
            "SELECT COALESCE(MAX(version), 0) FROM report_signouts "
            "WHERE family_id = CAST(:family_uuid AS uuid)"
        ),
        {"family_uuid": family_uuid},
    )
    return int(result.scalar_one() or 0) + 1


def _serialize_signout(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": row["version"],
        "signed_out_by": row["signed_out_by"],
        "signed_out_at": row["signed_out_at"],
        "content_hash": row["content_hash"],
        "software_version": row.get("software_version"),
        "git_sha": row.get("git_sha"),
        "qc_status": row.get("qc_status"),
        "qc_acknowledged": row.get("qc_acknowledged"),
        "qc_acknowledgement_reason": row.get("qc_acknowledgement_reason"),
        "snapshot": row.get("snapshot"),
    }


async def sign_out_report(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    acknowledge_drift: bool = False,
    acknowledge_qc: bool = False,
    qc_acknowledgement_reason: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    context = await build_family_metadata_context(
        session, family_identifier=family_id, user=user, project_id=project_id
    )
    snapshot_body = await build_report_snapshot(
        session, family_id=family_id, user=user, project_id=project_id
    )

    drifted_count = snapshot_body["drift"]["drifted_count"]
    if drifted_count and not acknowledge_drift:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{drifted_count} classification(s) have evidence changes since they were "
                "made. Re-review, or acknowledge the drift to sign out anyway."
            ),
        )

    # Sample-QC gate (after the drift gate; each gate guards an independent concern and
    # is acknowledged independently). Only a hard "fail" blocks (TF-06 H4 sample/pedigree
    # swap, S5 catastrophic); acknowledging requires a non-empty reason, which — like the
    # QC verdict itself — is frozen into the content hash below.
    qc_status = snapshot_body["sample_qc"]["overall_status"]
    qc_blocks = qc_status in _QC_BLOCKING_STATUSES
    if qc_blocks and not acknowledge_qc:
        raise HTTPException(
            status_code=409,
            detail={
                "gate": "sample_qc",
                "message": (
                    f"Sample-integrity QC status is '{qc_status}' (possible sample or "
                    "pedigree swap — TF-06 H4). Resolve it, or acknowledge with a reason "
                    "to sign out anyway."
                ),
                "qc_summary": _qc_failure_summary(snapshot_body["sample_qc"]),
            },
        )
    qc_reason = (qc_acknowledgement_reason or "").strip()
    if qc_blocks and acknowledge_qc and not qc_reason:
        raise HTTPException(
            status_code=422,
            detail="A reason is required to acknowledge a failing sample-integrity QC.",
        )

    now = datetime.now(timezone.utc)
    version = await _next_version(session, context.family_uuid)
    actor = getattr(user, "username", None) or getattr(user, "email", "") or "unknown"

    snapshot = {
        **snapshot_body,
        "version": version,
        "generated_at": now.isoformat(),
        "signed_out_by": actor,
        "acknowledged_drift": bool(drifted_count) and acknowledge_drift,
        "acknowledged_qc": qc_blocks and acknowledge_qc,
        "qc_acknowledgement_reason": qc_reason if (qc_blocks and acknowledge_qc) else None,
    }
    content_hash = _canonical_hash(snapshot)

    await session.execute(
        text(
            """
            INSERT INTO report_signouts
                (family_id, family_identifier, version, signed_out_by, signed_out_by_id,
                 signed_out_at, content_hash, snapshot)
            VALUES
                (CAST(:family_id AS uuid), :family_identifier, :version, :signed_out_by,
                 CAST(:signed_out_by_id AS uuid), :signed_out_at, :content_hash,
                 CAST(:snapshot AS jsonb))
            """
        ),
        {
            "family_id": context.family_uuid,
            "family_identifier": context.family_id,
            "version": version,
            "signed_out_by": actor,
            "signed_out_by_id": getattr(user, "id", None),
            "signed_out_at": now,
            "content_hash": content_hash,
            "snapshot": json.dumps(snapshot, default=str),
        },
    )
    await record_clinical_event(
        session,
        family_uuid=context.family_uuid,
        family_identifier=context.family_id,
        variant_id=None,
        actor=actor,
        actor_id=getattr(user, "id", None),
        action="sign_out",
        summary=(
            f"Report signed out (v{version}) — {len(snapshot_body['reported_variants'])} "
            f"reported variant(s){', drift acknowledged' if snapshot['acknowledged_drift'] else ''}"
            f"{', QC override acknowledged' if snapshot['acknowledged_qc'] else ''}"
        ),
        after={
            "version": version,
            "content_hash": content_hash,
            "software_version": snapshot_body["software"]["version"],
            "git_sha": snapshot_body["software"]["git_sha"],
            "reported_count": len(snapshot_body["reported_variants"]),
            "drifted_count": drifted_count,
            "qc_status": qc_status,
            "acknowledged_qc": snapshot["acknowledged_qc"],
            "qc_acknowledgement_reason": snapshot["qc_acknowledgement_reason"],
        },
    )
    await session.commit()
    return {
        "version": version,
        "signed_out_by": actor,
        "signed_out_at": now,
        "content_hash": content_hash,
        # Surface the frozen identity at top level so the POST response matches the
        # GET list/detail contract (which extracts it from the JSONB snapshot).
        "software_version": snapshot_body["software"]["version"],
        "git_sha": snapshot_body["software"]["git_sha"],
        "snapshot": snapshot,
    }


async def list_report_signouts(
    session: AsyncSession,
    *,
    family_id: str,
    user: CurrentUser,
    project_id: str | None = None,
) -> dict[str, Any]:
    context = await build_family_metadata_context(
        session, family_identifier=family_id, user=user, project_id=project_id
    )
    rows = (
        await session.execute(
            text(
                """
                SELECT version, signed_out_by, signed_out_at, content_hash,
                       snapshot->'software'->>'version' AS software_version,
                       snapshot->'software'->>'git_sha'  AS git_sha,
                       snapshot->'sample_qc'->>'overall_status' AS qc_status,
                       (snapshot->>'acknowledged_qc')::boolean   AS qc_acknowledged,
                       snapshot->>'qc_acknowledgement_reason'    AS qc_acknowledgement_reason
                FROM report_signouts
                WHERE family_id = CAST(:family_uuid AS uuid)
                ORDER BY version DESC
                """
            ),
            {"family_uuid": context.family_uuid},
        )
    ).mappings().all()
    signouts = [_serialize_signout(dict(row)) for row in rows]
    return {
        "family_id": context.family_id,
        "latest": signouts[0] if signouts else None,
        "signouts": signouts,
    }


async def get_report_signout(
    session: AsyncSession,
    *,
    family_id: str,
    version: int,
    user: CurrentUser,
    project_id: str | None = None,
) -> dict[str, Any]:
    context = await build_family_metadata_context(
        session, family_identifier=family_id, user=user, project_id=project_id
    )
    row = (
        await session.execute(
            text(
                """
                SELECT version, signed_out_by, signed_out_at, content_hash, snapshot,
                       snapshot->'software'->>'version' AS software_version,
                       snapshot->'software'->>'git_sha'  AS git_sha,
                       snapshot->'sample_qc'->>'overall_status' AS qc_status,
                       (snapshot->>'acknowledged_qc')::boolean   AS qc_acknowledged,
                       snapshot->>'qc_acknowledgement_reason'    AS qc_acknowledgement_reason
                FROM report_signouts
                WHERE family_id = CAST(:family_uuid AS uuid) AND version = :version
                """
            ),
            {"family_uuid": context.family_uuid, "version": version},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Sign-out version not found")
    return _serialize_signout(dict(row))
