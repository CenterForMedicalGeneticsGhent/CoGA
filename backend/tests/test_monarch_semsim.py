"""Tests for Monarch semsim phenotype-matching helpers (no network)."""

import pytest

from backend.app.services import monarch_semsim
from backend.app.services.monarch_semsim import (
    MonarchSemsimError,
    _normalize_results,
    semsim_search,
)


def test_normalize_results_assigns_ranks_and_extracts_subject() -> None:
    payload = [
        {"subject": {"id": "HGNC:11764", "name": "TG", "category": "biolink:Gene"},
         "score": 12.3},
        {"subject": {"id": "HGNC:21071", "name": "IYD", "category": "biolink:Gene"},
         "score": 11.4},
    ]
    results = _normalize_results(payload)

    assert [r["rank"] for r in results] == [1, 2]
    assert results[0]["id"] == "HGNC:11764"
    assert results[0]["name"] == "TG"
    assert results[0]["score"] == 12.3


def test_normalize_results_skips_entries_without_subject_id() -> None:
    payload = [
        {"subject": {}, "score": 1.0},
        {"subject": {"id": "HGNC:1", "name": "A", "category": "biolink:Gene"}, "score": 2.0},
    ]
    results = _normalize_results(payload)

    assert len(results) == 1
    assert results[0]["id"] == "HGNC:1"
    assert results[0]["rank"] == 1


def test_normalize_results_rejects_non_list() -> None:
    with pytest.raises(MonarchSemsimError):
        _normalize_results({"not": "a list"})


@pytest.mark.asyncio
async def test_semsim_search_short_circuits_on_empty_termset() -> None:
    # Must not touch the network when there are no usable terms.
    assert await semsim_search([], group="Human Genes") == []
    assert await semsim_search(["", "   "], group="Human Genes") == []


@pytest.mark.asyncio
async def test_semsim_search_rejects_unknown_group() -> None:
    with pytest.raises(ValueError):
        await semsim_search(["HP:0001250"], group="Martian Genes")


def test_cache_round_trip_and_size_bound() -> None:
    monarch_semsim._cache.clear()
    key = ("Human Genes", ("HP:1",), 10)
    monarch_semsim._cache_put(key, [{"rank": 1, "id": "HGNC:1"}])
    assert monarch_semsim._cache_get(key) == [{"rank": 1, "id": "HGNC:1"}]
    monarch_semsim._cache.clear()
