from types import SimpleNamespace

import pytest

from backend.app.services import variant_explorer_service as ves


def _patch_common(monkeypatch, *, rows, cap=2):
    monkeypatch.setattr(ves, "_VARIANT_CARRIER_ROW_LIMIT", cap)

    async def fake_scope(session, user, assembly_id):
        return SimpleNamespace(assembly_name="GRCh38", project_ids=["p1"])

    captured: dict = {}

    async def fake_execute(query, params):
        captured["query"] = query
        captured["params"] = params
        return rows

    async def fake_family_meta(session, project_ids, family_uuids):
        return {
            fam: {"family_name": fam.upper(), "project_id": "p1", "project_name": "Proj1"}
            for fam in family_uuids
        }

    async def fake_sample_meta(session, sample_keys):
        return {}

    monkeypatch.setattr(ves, "resolve_scope", fake_scope)
    monkeypatch.setattr(ves, "execute_clickhouse", fake_execute)
    monkeypatch.setattr(ves, "_fetch_family_meta", fake_family_meta)
    monkeypatch.setattr(ves, "_fetch_sample_meta", fake_sample_meta)
    return captured


@pytest.mark.asyncio
async def test_get_variant_carriers_flags_truncation(monkeypatch) -> None:
    rows = [
        ("famA", "s1", "0/1", "vid"),
        ("famA", "s2", "0/1", "vid"),
        ("famB", "s3", "0/1", "vid"),  # beyond the cap of 2 -> truncated away
    ]
    captured = _patch_common(monkeypatch, rows=rows, cap=2)

    result = await ves.get_variant_carriers(None, user=SimpleNamespace(), variant_key=1)

    # The query is bounded with a LIMIT (fetching cap + 1).
    assert "LIMIT %(carrier_limit)s" in captured["query"]
    assert captured["params"]["carrier_limit"] == 3
    # Truncated to the first 2 rows -> 2 carriers, both in famA.
    assert result.truncated is True
    assert result.total_samples == 2
    assert result.total_families == 1
    assert {group.family_uuid for group in result.families} == {"famA"}


@pytest.mark.asyncio
async def test_get_variant_carriers_exact_under_cap(monkeypatch) -> None:
    rows = [
        ("famA", "s1", "0/1", "vid"),
        ("famB", "s2", "1/1", "vid"),
    ]
    _patch_common(monkeypatch, rows=rows, cap=2)

    result = await ves.get_variant_carriers(None, user=SimpleNamespace(), variant_key=1)

    assert result.truncated is False
    assert result.total_samples == 2
    assert result.het_samples == 1
    assert result.hom_samples == 1
    assert result.total_families == 2
