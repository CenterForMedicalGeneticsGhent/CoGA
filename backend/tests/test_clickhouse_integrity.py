from __future__ import annotations

import asyncio

import pytest

from backend.app.services import clickhouse_variant_storage as cvs

DATASET = "GRCh38"
DATA_TABLES = [
    name for _vt, kind, name in cvs._expected_clickhouse_variant_tables(DATASET) if kind == "table"
]
GENE_INDEX = f"{DATASET}/SNV_INDEL/variants/gene_index"
ANNOTATION_INDEX = f"{DATASET}/SNV_INDEL/variants/annotation_index"


def _integrity_execute(*, existing, check_results, detached, gene_keys, annotation_keys):
    """An async `_execute` stub that dispatches on the query text."""

    async def _execute(query, params=None, data=None):
        q = " ".join(query.split())
        if "FROM system.tables" in q:
            return [(name,) for name in existing]
        if q.startswith("CHECK TABLE"):
            for name in existing:
                if f"`{name}`" in query:
                    return check_results.get(name, [("part_0", 1, "")])
            return [("part_0", 1, "")]
        if "FROM system.detached_parts" in q:
            return detached
        if "uniqExact(key)" in q and "WHERE" in q:  # gene-bearing annotation keys
            return [(annotation_keys,)]
        if "uniqExact(key)" in q:  # gene_index keys
            return [(gene_keys,)]
        raise AssertionError(f"unexpected query: {q[:80]}")

    return _execute


def test_integrity_ok_when_clean(monkeypatch) -> None:
    monkeypatch.setattr(
        cvs, "_execute",
        _integrity_execute(existing=DATA_TABLES, check_results={}, detached=[],
                           gene_keys=100, annotation_keys=100),
    )
    report = asyncio.run(cvs.check_clickhouse_variant_integrity(DATASET))
    assert report["status"] == "ok"
    assert report["gene_index_consistency"]["consistent"] is True
    assert all(t["passed"] for t in report["table_checks"] if t["exists"])


def test_integrity_corrupt_on_failed_part(monkeypatch) -> None:
    monkeypatch.setattr(
        cvs, "_execute",
        _integrity_execute(
            existing=DATA_TABLES,
            check_results={GENE_INDEX: [("part_a", 1, ""), ("part_b", 0, "CHECKSUM_DOESNT_MATCH")]},
            detached=[], gene_keys=100, annotation_keys=100,
        ),
    )
    report = asyncio.run(cvs.check_clickhouse_variant_integrity(DATASET))
    assert report["status"] == "corrupt"
    gi = next(t for t in report["table_checks"] if t["name"] == GENE_INDEX)
    assert gi["passed"] is False and gi["failed_parts"] == 1
    assert "CHECKSUM_DOESNT_MATCH" in gi["messages"][0]


def test_integrity_degraded_on_detached_parts(monkeypatch) -> None:
    monkeypatch.setattr(
        cvs, "_execute",
        _integrity_execute(
            existing=DATA_TABLES, check_results={},
            detached=[(f"{DATASET}/SNV_INDEL/entries", "broken-on-start", 52)],
            gene_keys=100, annotation_keys=100,
        ),
    )
    report = asyncio.run(cvs.check_clickhouse_variant_integrity(DATASET))
    assert report["status"] == "degraded"
    assert report["detached_broken_parts"][0]["count"] == 52
    assert any("storage-volume" in note for note in report["notes"])


def test_integrity_degraded_on_gene_index_drift(monkeypatch) -> None:
    monkeypatch.setattr(
        cvs, "_execute",
        _integrity_execute(existing=DATA_TABLES, check_results={}, detached=[],
                           gene_keys=90, annotation_keys=100),
    )
    report = asyncio.run(cvs.check_clickhouse_variant_integrity(DATASET))
    assert report["status"] == "degraded"
    assert report["gene_index_consistency"]["consistent"] is False
    assert report["gene_index_consistency"]["drift"] == -10


def test_integrity_missing_when_no_tables(monkeypatch) -> None:
    monkeypatch.setattr(
        cvs, "_execute",
        _integrity_execute(existing=[], check_results={}, detached=[],
                           gene_keys=0, annotation_keys=0),
    )
    report = asyncio.run(cvs.check_clickhouse_variant_integrity(DATASET))
    assert report["status"] == "missing"
    assert report["gene_index_consistency"]["checked"] is False


# --- safe gene_index rebuild -------------------------------------------------

def _rebuild_execute(recorder, *, check_rows, rebuilt_keys, source_keys):
    async def _execute(query, params=None, data=None):
        q = " ".join(query.split())
        recorder.append(q)
        if q.startswith("CHECK TABLE"):
            return check_rows
        if "uniqExact(key)" in q and "WHERE" in q:
            return [(source_keys,)]
        if "uniqExact(key)" in q:
            return [(rebuilt_keys,)]
        return None

    return _execute


def _patch_rebuild_env(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    async def _status(dataset):
        return {"assembly_name": dataset}

    monkeypatch.setattr(cvs, "ensure_clickhouse_variant_tables", _noop)
    monkeypatch.setattr(cvs, "get_clickhouse_variant_storage_status", _status)


def test_rebuild_swaps_atomically_when_valid(monkeypatch) -> None:
    recorder: list[str] = []
    _patch_rebuild_env(monkeypatch)
    monkeypatch.setattr(
        cvs, "_execute",
        _rebuild_execute(recorder, check_rows=[("p", 1, "")], rebuilt_keys=100, source_keys=100),
    )
    asyncio.run(cvs.rebuild_small_variant_gene_index(DATASET))
    joined = " || ".join(recorder)
    # Atomic swap, not the old empty-window TRUNCATE of the live table.
    assert "EXCHANGE TABLES" in joined
    assert "TRUNCATE" not in joined
    assert any(q.startswith("CREATE TABLE") for q in recorder)
    assert any(q.startswith("DROP TABLE IF EXISTS") for q in recorder)


def test_rebuild_aborts_without_swap_on_key_mismatch(monkeypatch) -> None:
    recorder: list[str] = []
    _patch_rebuild_env(monkeypatch)
    monkeypatch.setattr(
        cvs, "_execute",
        _rebuild_execute(recorder, check_rows=[("p", 1, "")], rebuilt_keys=90, source_keys=100),
    )
    with pytest.raises(RuntimeError, match="key mismatch"):
        asyncio.run(cvs.rebuild_small_variant_gene_index(DATASET))
    joined = " || ".join(recorder)
    assert "EXCHANGE TABLES" not in joined  # never swap a bad index over good data
    assert any(q.startswith("DROP TABLE IF EXISTS") for q in recorder)  # shadow still cleaned up


def test_rebuild_aborts_on_corrupt_shadow(monkeypatch) -> None:
    recorder: list[str] = []
    _patch_rebuild_env(monkeypatch)
    monkeypatch.setattr(
        cvs, "_execute",
        _rebuild_execute(recorder, check_rows=[("p", 0, "UNKNOWN_CODEC")], rebuilt_keys=100, source_keys=100),
    )
    with pytest.raises(RuntimeError, match="corrupt"):
        asyncio.run(cvs.rebuild_small_variant_gene_index(DATASET))
    assert "EXCHANGE TABLES" not in " || ".join(recorder)
