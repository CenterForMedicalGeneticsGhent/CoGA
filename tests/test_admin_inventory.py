import pytest

from backend.app.services import admin_service


@pytest.mark.asyncio
async def test_list_data_inventory_page_sums_variant_counts_per_family(monkeypatch) -> None:
    family_rows = [
        {
            "family_uuid": "fam-1",
            "family_id": "F1",
            "project_ids": ["p1"],
            "assembly_names": ["GRCh38", "GRCh37"],
            "sample_count": 2,
            "metadata": {},
        },
        {
            "family_uuid": "fam-2",
            "family_id": "F2",
            "project_ids": ["p2"],
            "assembly_names": ["GRCh38"],
            "sample_count": 1,
            "metadata": {},
        },
    ]

    async def fake_family_rows(session, *, search=None, page=1, page_size=50):
        return (2, family_rows)

    small_map = {("GRCh38", "fam-1"): 10, ("GRCh37", "fam-1"): 5, ("GRCh38", "fam-2"): 7}
    sv_map = {("GRCh38", "fam-1"): 1, ("GRCh37", "fam-1"): 2, ("GRCh38", "fam-2"): 3}
    small_calls: list[tuple] = []
    sv_calls: list[tuple] = []

    async def fake_small(assembly_name, family_uuid, *, project_ids=None):
        small_calls.append((assembly_name, family_uuid, tuple(project_ids or ())))
        return small_map[(assembly_name, family_uuid)]

    async def fake_sv(assembly_name, family_uuid, *, project_ids=None):
        sv_calls.append((assembly_name, family_uuid, tuple(project_ids or ())))
        return sv_map[(assembly_name, family_uuid)]

    async def fake_interval(session, uuids):
        return {}

    async def fake_repeat(session, uuids):
        return {}

    monkeypatch.setattr(admin_service, "_family_rows", fake_family_rows)
    monkeypatch.setattr(admin_service, "count_family_small_variants", fake_small)
    monkeypatch.setattr(admin_service, "count_family_structural_variants", fake_sv)
    monkeypatch.setattr(admin_service, "_interval_counts_by_family", fake_interval)
    monkeypatch.setattr(admin_service, "_repeat_counts_by_family", fake_repeat)

    page = await admin_service.list_data_inventory_page(None, page=1, page_size=50)

    assert page.total == 2
    by_family = {item.family_id: item for item in page.items}
    # Counts summed across each family's assemblies.
    assert by_family["F1"].track_counts["small_variants"] == 15
    assert by_family["F1"].track_counts["structural_variants"] == 3
    assert by_family["F2"].track_counts["small_variants"] == 7
    assert by_family["F2"].track_counts["structural_variants"] == 3
    # Per-family project scoping is preserved on every count query.
    assert ("GRCh38", "fam-1", ("p1",)) in small_calls
    assert ("GRCh37", "fam-1", ("p1",)) in small_calls
    assert ("GRCh38", "fam-2", ("p2",)) in small_calls
    assert ("GRCh38", "fam-1", ("p1",)) in sv_calls
