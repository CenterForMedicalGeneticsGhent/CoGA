import pytest

from backend.app.services import bed_service
from backend.app.services.family_metadata_context import SampleMetadataContext


def _ctx() -> SampleMetadataContext:
    return SampleMetadataContext(
        sample_uuid="s-uuid",
        sample_id="s",
        family_uuid="f-uuid",
        family_id="fam",
        sex="female",
        project_ids=["p"],
        assembly_id="a-uuid",
        assembly_name="GRCh38",
    )


def _patch_fetch(monkeypatch, rows):
    calls: list[dict] = []

    async def fake_fetch(assembly_name, **kwargs):
        calls.append({"assembly_name": assembly_name, **kwargs})
        return rows

    monkeypatch.setattr(bed_service, "fetch_interval_track_rows", fake_fetch)
    return calls


@pytest.mark.asyncio
async def test_fetch_bed_records_for_chroms_uses_one_query_and_groups_by_chrom(monkeypatch) -> None:
    rows = [
        {"chr": "1", "start": 10, "end": 20, "value": 1.0, "origin": "und"},
        {"chr": "1", "start": 30, "end": 40, "value": 2.0, "origin": "und"},
        {"chr": "2", "start": 5, "end": 8, "value": 3.0, "origin": "und"},
        # Mitochondrion stored as "M" while the request used "MT".
        {"chr": "M", "start": 1, "end": 2, "value": 4.0, "origin": "und"},
    ]
    calls = _patch_fetch(monkeypatch, rows)

    records = await bed_service._fetch_bed_records_for_chroms(
        None,
        sample_context=_ctx(),
        bed_type="segments",
        chroms=["1", "2", "MT"],
        window=None,
        start=None,
        end=None,
        limit=100,
    )

    # One ClickHouse query for every requested chromosome, no DB-side limit.
    assert len(calls) == 1
    assert calls[0]["chromosomes"] == ["1", "2", "MT"]
    assert "limit" not in calls[0] or calls[0]["limit"] is None
    # Grouped in request order; the "MT" bucket matched the stored "M" alias.
    assert [r["chr"] for r in records] == ["1", "1", "2", "M"]


@pytest.mark.asyncio
async def test_fetch_bed_records_for_chroms_applies_per_chromosome_limit(monkeypatch) -> None:
    rows = [
        {"chr": "1", "start": 10, "end": 20, "value": 1.0, "origin": "und"},
        {"chr": "1", "start": 30, "end": 40, "value": 2.0, "origin": "und"},
        {"chr": "2", "start": 5, "end": 8, "value": 3.0, "origin": "und"},
    ]
    _patch_fetch(monkeypatch, rows)

    records = await bed_service._fetch_bed_records_for_chroms(
        None,
        sample_context=_ctx(),
        bed_type="segments",
        chroms=["1", "2"],
        window=None,
        start=None,
        end=None,
        limit=1,
    )

    # limit is applied per chromosome (chrom 1's two rows truncated to one).
    assert [r["chr"] for r in records] == ["1", "2"]
    assert [r["start"] for r in records] == [10, 5]


@pytest.mark.asyncio
async def test_fetch_bed_records_for_chroms_windowed_apcad_keeps_chrom_per_bucket(monkeypatch) -> None:
    rows = [
        {"chr": "1", "start": 100, "end": 200, "value": 0.5, "origin": "paternal"},
        {"chr": "2", "start": 300, "end": 400, "value": 0.6, "origin": "paternal"},
    ]
    calls = _patch_fetch(monkeypatch, rows)

    records = await bed_service._fetch_bed_records_for_chroms(
        None,
        sample_context=_ctx(),
        bed_type="apcad",
        chroms=["1", "2"],
        window=1000,
        start=None,
        end=None,
        limit=100,
    )

    # APCAD requests paternal/maternal origins.
    assert calls[0]["origins"] == ["paternal", "maternal"]
    # Each chromosome is windowed independently, so chr 2's bin keeps "2"
    # (it would be mis-stamped "1" if all chroms were binned in one call).
    by_chrom = {r["chr"] for r in records}
    assert by_chrom == {"1", "2"}


def test_windowed_apcad_rows_is_chromosome_aware() -> None:
    rows = [
        {"chr": "1", "start": 100, "end": 200, "value": 0.5, "origin": "paternal"},
        # Same (origin, bin_start) as the chr-1 row but a different chromosome:
        # must NOT collapse into one averaged bin stamped "1".
        {"chr": "2", "start": 100, "end": 200, "value": 0.6, "origin": "paternal"},
        # An out-of-[0.05, 0.95] extreme on chr 2 must keep its own chromosome.
        {"chr": "2", "start": 5, "end": 6, "value": 0.99, "origin": "maternal"},
    ]

    out = bed_service._windowed_apcad_rows(rows, window=1000, limit=100)

    bins_by_chrom = {
        (r["chr"], r["origin"]): r["value"]
        for r in out
        if r["start"] == 0 and r["end"] == 1000
    }
    assert abs(bins_by_chrom[("1", "paternal")] - 0.5) < 1e-9
    assert abs(bins_by_chrom[("2", "paternal")] - 0.6) < 1e-9
    # The extreme keeps chr "2", not chr "1".
    assert any(r["chr"] == "2" and r["origin"] == "maternal" and r["value"] == 0.99 for r in out)
