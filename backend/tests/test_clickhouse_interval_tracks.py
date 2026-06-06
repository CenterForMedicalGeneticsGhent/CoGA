from __future__ import annotations

import pytest

from backend.app.services import clickhouse_interval_tracks


@pytest.mark.asyncio
async def test_track_presence_applies_region_filter_for_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object] | None, object | None]] = []

    async def fake_execute(query: str, params=None, data=None):
        calls.append((query, params, data))
        if query.lstrip().upper().startswith("CREATE TABLE"):
            return None
        return [("sample-uuid",)]

    monkeypatch.setattr(clickhouse_interval_tracks, "_execute", fake_execute)

    present = await clickhouse_interval_tracks.get_interval_track_presence_by_sample(
        "GRCh38",
        family_uuid="family-uuid",
        sample_uuid_to_name={"sample-uuid": "S1"},
        track_type="coverage",
        chromosomes=["1"],
        start=1000,
        end=2000,
    )

    assert present == {"S1"}
    query, params, _data = calls[-1]
    assert "start <= %(window_end)s AND end >= %(window_start)s" in query
    assert params is not None
    assert params["window_start"] == 1000
    assert params["window_end"] == 2000
