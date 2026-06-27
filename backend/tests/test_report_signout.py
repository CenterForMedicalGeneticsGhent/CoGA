from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException

from backend.app.services import report_signout_service as rss
from backend.app.services.sample_integrity_qc import SampleIntegrityReport


def test_canonical_hash_is_stable_and_order_independent() -> None:
    a = rss._canonical_hash({"x": 1, "y": [1, 2], "z": "t"})
    b = rss._canonical_hash({"z": "t", "y": [1, 2], "x": 1})
    assert a == b
    assert len(a) == 64  # sha256 hex
    assert a != rss._canonical_hash({"x": 2, "y": [1, 2], "z": "t"})


def _user():
    return types.SimpleNamespace(username="bjorn", email="b@x.org", id=None)


class _Result:
    def scalar_one(self):
        return 0  # no prior sign-out -> next version 1

    def scalar_one_or_none(self):
        return None  # no prior sign-out -> chain genesis (prev_hash is None)


class _Session:
    def __init__(self) -> None:
        self.executed: list = []

    async def execute(self, *args, **kwargs):
        self.executed.append((args, kwargs))
        return _Result()

    async def commit(self) -> None:
        return None


def _patch_common(monkeypatch, *, drifted_count: int, qc_status: str = "pass"):
    async def _ctx(session, *, family_identifier, user, project_id=None):
        return types.SimpleNamespace(family_uuid="u1", family_id="FAM1")

    async def _manifest(session, *, family_id, user, project_id=None):
        return {"assembly": "GRCh38", "modules": [{"key": "clinvar", "version": "2026-05"}]}

    async def _drift(session, *, family_id, user, project_id=None):
        return {
            "checked": drifted_count,
            "drifted_count": drifted_count,
            "drifted": [{"variant_id": "x"}] * drifted_count,
        }

    async def _reviews(session, family_uuid):
        return [{"variant_id": "1-1-A-G", "acmg_class": "acmg_class_4"}]

    async def _audit(*args, **kwargs):
        return None

    async def _qc(session, *, family_id, user, project_id=None):
        # Sample QC is computed inside build_report_snapshot now; stub it with a
        # parameterizable overall_status (default "pass" -> the QC gate stays open).
        return SampleIntegrityReport(overall_status=qc_status)

    monkeypatch.setattr(rss, "build_family_metadata_context", _ctx)
    monkeypatch.setattr(rss, "get_family_annotation_manifest", _manifest)
    monkeypatch.setattr(rss, "evaluate_classification_drift", _drift)
    monkeypatch.setattr(rss, "_reported_reviews", _reviews)
    monkeypatch.setattr(rss, "record_clinical_event", _audit)
    monkeypatch.setattr(rss, "get_family_sample_integrity_qc", _qc)


def test_sign_out_blocks_unacknowledged_drift(monkeypatch) -> None:
    _patch_common(monkeypatch, drifted_count=2)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            rss.sign_out_report(
                _Session(), family_id="FAM1", user=_user(), acknowledge_drift=False
            )
        )
    assert excinfo.value.status_code == 409


def test_sign_out_proceeds_when_clean(monkeypatch) -> None:
    _patch_common(monkeypatch, drifted_count=0)
    out = asyncio.run(
        rss.sign_out_report(_Session(), family_id="FAM1", user=_user(), acknowledge_drift=False)
    )
    assert out["version"] == 1
    assert len(out["content_hash"]) == 64
    assert out["snapshot"]["modules"] == [{"key": "clinvar", "version": "2026-05"}]
    assert out["snapshot"]["acknowledged_drift"] is False


def test_sign_out_proceeds_with_acknowledged_drift(monkeypatch) -> None:
    _patch_common(monkeypatch, drifted_count=1)
    out = asyncio.run(
        rss.sign_out_report(_Session(), family_id="FAM1", user=_user(), acknowledge_drift=True)
    )
    assert out["version"] == 1
    assert out["snapshot"]["acknowledged_drift"] is True
    assert out["snapshot"]["drift"]["drifted_count"] == 1


def test_build_report_snapshot_freezes_software_identity(monkeypatch) -> None:
    _patch_common(monkeypatch, drifted_count=0)
    monkeypatch.setattr(rss.settings, "app_version", "1.2.3")
    monkeypatch.setattr(rss.settings, "git_sha", "abc1234def5")
    body = asyncio.run(rss.build_report_snapshot(_Session(), family_id="FAM1", user=_user()))
    assert body["software"] == {"version": "1.2.3", "git_sha": "abc1234def5"}


def test_software_identity_is_bound_into_content_hash(monkeypatch) -> None:
    # Changing only the software identity changes the frozen content hash, proving the
    # signed report is cryptographically bound to the exact code that produced it.
    # Hashes the time-invariant snapshot BODY so the only varying input is the version.
    def _body_hash(version: str, sha: str) -> str:
        _patch_common(monkeypatch, drifted_count=0)
        monkeypatch.setattr(rss.settings, "app_version", version)
        monkeypatch.setattr(rss.settings, "git_sha", sha)
        body = asyncio.run(rss.build_report_snapshot(_Session(), family_id="FAM1", user=_user()))
        return rss._canonical_hash(body)

    assert _body_hash("1.0.0", "aaa") == _body_hash("1.0.0", "aaa")  # deterministic
    assert _body_hash("1.0.0", "aaa") != _body_hash("1.0.1", "aaa")  # bound to version
    assert _body_hash("1.0.0", "aaa") != _body_hash("1.0.0", "bbb")  # bound to git_sha


def test_software_falls_back_to_honest_unknown_sentinels(monkeypatch) -> None:
    # Unstamped build: the snapshot records the "unknown" sentinels (never blank/None),
    # so the hash stays deterministic and the report honestly states the code is unknown.
    _patch_common(monkeypatch, drifted_count=0)
    monkeypatch.setattr(rss.settings, "app_version", "0.0.0+unknown")
    monkeypatch.setattr(rss.settings, "git_sha", "unknown")
    out = asyncio.run(
        rss.sign_out_report(_Session(), family_id="FAM1", user=_user(), acknowledge_drift=False)
    )
    assert out["snapshot"]["software"] == {"version": "0.0.0+unknown", "git_sha": "unknown"}
    # The POST sign-out response surfaces the same frozen identity at top level as the
    # GET list/detail endpoints (which extract it from the JSONB snapshot).
    assert out["software_version"] == "0.0.0+unknown"
    assert out["git_sha"] == "unknown"


def test_serialize_signout_exposes_frozen_software_identity() -> None:
    # The list/footer path surfaces the JSONB-extracted frozen identity as top-level fields.
    row = {
        "version": 1,
        "signed_out_by": "x",
        "signed_out_at": None,
        "content_hash": "h",
        "software_version": "2.0.0",
        "git_sha": "deadbeef",
    }
    serialized = rss._serialize_signout(row)
    assert serialized["software_version"] == "2.0.0"
    assert serialized["git_sha"] == "deadbeef"


def test_build_report_snapshot_hash_is_drift_order_independent(monkeypatch) -> None:
    # P0-3: identical clinical content with drift rows arriving in different orders
    # (Postgres returns equal-updated_at rows arbitrarily) must hash identically. The
    # canonical hash sorts dict keys but not list element order, so the snapshot must
    # order the drift list by the unique variant_id.
    rows = [
        {"variant_id": "2-200-C-T", "acmg_class": "acmg_class_3"},
        {"variant_id": "1-100-A-G", "acmg_class": "acmg_class_4"},
    ]

    def _patch(drift_rows):
        async def _ctx(session, *, family_identifier, user, project_id=None):
            return types.SimpleNamespace(family_uuid="u1", family_id="FAM1")

        async def _manifest(session, *, family_id, user, project_id=None):
            return {
                "assembly": "GRCh38",
                "modules": [{"key": "clinvar", "version": "2026-05"}],
            }

        async def _drift(session, *, family_id, user, project_id=None):
            return {
                "checked": len(drift_rows),
                "drifted_count": len(drift_rows),
                "drifted": list(drift_rows),
            }

        async def _reviews(session, family_uuid):
            return [{"variant_id": "1-1-A-G", "acmg_class": "acmg_class_4"}]

        async def _qc(session, *, family_id, user, project_id=None):
            return SampleIntegrityReport(overall_status="pass")

        monkeypatch.setattr(rss, "build_family_metadata_context", _ctx)
        monkeypatch.setattr(rss, "get_family_annotation_manifest", _manifest)
        monkeypatch.setattr(rss, "evaluate_classification_drift", _drift)
        monkeypatch.setattr(rss, "_reported_reviews", _reviews)
        monkeypatch.setattr(rss, "get_family_sample_integrity_qc", _qc)

    _patch(rows)
    snap_a = asyncio.run(rss.build_report_snapshot(_Session(), family_id="FAM1", user=_user()))
    _patch(list(reversed(rows)))
    snap_b = asyncio.run(rss.build_report_snapshot(_Session(), family_id="FAM1", user=_user()))

    assert rss._canonical_hash(snap_a) == rss._canonical_hash(snap_b)
    # The hashed snapshot orders the drift list by variant_id, not by input order.
    assert [d["variant_id"] for d in snap_b["drift"]["drifted"]] == [
        "1-100-A-G",
        "2-200-C-T",
    ]


def test_failing_sample_qc_blocks_sign_out(monkeypatch) -> None:
    # P1-2: a "fail" Sample QC (possible sample/pedigree swap, TF-06 H4 / S5) blocks
    # sign-out with a structured 409 carrying the gate discriminator + a failure summary.
    _patch_common(monkeypatch, drifted_count=0, qc_status="fail")
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(rss.sign_out_report(_Session(), family_id="FAM1", user=_user()))
    assert excinfo.value.status_code == 409
    detail = excinfo.value.detail
    assert detail["gate"] == "sample_qc"
    assert detail["qc_summary"]["overall_status"] == "fail"


def test_failing_sample_qc_acknowledged_without_reason_is_422(monkeypatch) -> None:
    _patch_common(monkeypatch, drifted_count=0, qc_status="fail")
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            rss.sign_out_report(
                _Session(),
                family_id="FAM1",
                user=_user(),
                acknowledge_qc=True,
                qc_acknowledgement_reason="   ",  # whitespace-only == empty
            )
        )
    assert excinfo.value.status_code == 422


def test_failing_sample_qc_acknowledged_with_reason_proceeds(monkeypatch) -> None:
    _patch_common(monkeypatch, drifted_count=0, qc_status="fail")
    out = asyncio.run(
        rss.sign_out_report(
            _Session(),
            family_id="FAM1",
            user=_user(),
            acknowledge_qc=True,
            qc_acknowledgement_reason="  Repeat genotyping confirms the samples.  ",
        )
    )
    assert out["version"] == 1
    assert out["snapshot"]["acknowledged_qc"] is True
    # The reason is stripped and frozen into the (content-hashed) record.
    assert out["snapshot"]["qc_acknowledgement_reason"] == "Repeat genotyping confirms the samples."
    assert out["snapshot"]["sample_qc"]["overall_status"] == "fail"


def test_non_failing_qc_signs_out_without_acknowledgement(monkeypatch) -> None:
    # Per policy only "fail" blocks; pass/warn/skip are frozen + surfaced but do not gate.
    for status in ("pass", "warn", "skip"):
        _patch_common(monkeypatch, drifted_count=0, qc_status=status)
        out = asyncio.run(rss.sign_out_report(_Session(), family_id="FAM1", user=_user()))
        assert out["snapshot"]["acknowledged_qc"] is False
        assert out["snapshot"]["qc_acknowledgement_reason"] is None
        assert out["snapshot"]["sample_qc"]["overall_status"] == status


def test_drift_and_qc_gates_are_independent(monkeypatch) -> None:
    # Both failing: the drift gate fires first; acknowledging drift then exposes the QC
    # gate; acknowledging both (with a QC reason) proceeds.
    _patch_common(monkeypatch, drifted_count=2, qc_status="fail")
    with pytest.raises(HTTPException) as drift_exc:
        asyncio.run(rss.sign_out_report(_Session(), family_id="FAM1", user=_user()))
    assert drift_exc.value.status_code == 409
    assert "classification" in str(drift_exc.value.detail)

    _patch_common(monkeypatch, drifted_count=2, qc_status="fail")
    with pytest.raises(HTTPException) as qc_exc:
        asyncio.run(
            rss.sign_out_report(
                _Session(), family_id="FAM1", user=_user(), acknowledge_drift=True
            )
        )
    assert qc_exc.value.status_code == 409
    assert qc_exc.value.detail["gate"] == "sample_qc"

    _patch_common(monkeypatch, drifted_count=2, qc_status="fail")
    out = asyncio.run(
        rss.sign_out_report(
            _Session(),
            family_id="FAM1",
            user=_user(),
            acknowledge_drift=True,
            acknowledge_qc=True,
            qc_acknowledgement_reason="override reason",
        )
    )
    assert out["snapshot"]["acknowledged_drift"] is True
    assert out["snapshot"]["acknowledged_qc"] is True


def test_sample_qc_is_bound_into_content_hash(monkeypatch) -> None:
    # Changing only the QC verdict changes the frozen content hash, proving the signed
    # report is bound to what QC found. Hash the time-invariant snapshot BODY.
    def _body_hash(status: str) -> str:
        _patch_common(monkeypatch, drifted_count=0, qc_status=status)
        body = asyncio.run(rss.build_report_snapshot(_Session(), family_id="FAM1", user=_user()))
        assert body["sample_qc"]["overall_status"] == status
        return rss._canonical_hash(body)

    assert _body_hash("pass") == _body_hash("pass")  # deterministic
    assert _body_hash("pass") != _body_hash("fail")  # bound to the QC verdict


def test_audit_records_qc_status_and_acknowledgement(monkeypatch) -> None:
    captured: dict = {}

    async def _capture(*args, **kwargs):
        captured.update(kwargs)

    _patch_common(monkeypatch, drifted_count=0, qc_status="fail")
    monkeypatch.setattr(rss, "record_clinical_event", _capture)
    asyncio.run(
        rss.sign_out_report(
            _Session(),
            family_id="FAM1",
            user=_user(),
            acknowledge_qc=True,
            qc_acknowledgement_reason="repeat genotyping confirms identity",
        )
    )
    after = captured["after"]
    assert after["qc_status"] == "fail"
    assert after["acknowledged_qc"] is True
    assert after["qc_acknowledgement_reason"] == "repeat genotyping confirms identity"
    assert ", QC override acknowledged" in captured["summary"]
