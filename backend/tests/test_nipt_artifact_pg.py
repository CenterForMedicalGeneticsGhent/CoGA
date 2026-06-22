from __future__ import annotations

import pytest

from backend.app.services.nipt_artifact_pg import load_nipt_artifact_ids


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list = []

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_load_nipt_artifact_ids_returns_variant_id_set() -> None:
    session = _FakeSession([("1-100-A-G",), ("2-200-C-T",)])
    ids = await load_nipt_artifact_ids(
        session,  # type: ignore[arg-type]
        assembly_id="assembly-uuid",
        assay_key="nipt_cfdna",
    )
    assert ids == {"1-100-A-G", "2-200-C-T"}
    assert session.executed  # the query ran


@pytest.mark.asyncio
async def test_load_nipt_artifact_ids_short_circuits_without_assembly() -> None:
    session = _FakeSession([("1-100-A-G",)])
    ids = await load_nipt_artifact_ids(
        session,  # type: ignore[arg-type]
        assembly_id=None,
        assay_key="nipt_cfdna",
    )
    assert ids == set()
    assert session.executed == []
