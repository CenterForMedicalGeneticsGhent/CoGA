"""Phase 0 of SNV + SV compound het: the SV→gene index + the badge summary."""

from __future__ import annotations

import asyncio
import types

from backend.app.services import clickhouse_family_variants as cfv
from backend.app.services.sv_gene_index_service import summarize_second_hit


def _sv(sv_type: str, gt: dict[str, str]) -> dict:
    return {"sv_id": "v", "sv_type": sv_type, "chr": "1", "start": 1, "end": 9, "gt": gt}


def test_deletion_in_affected_is_flagged_and_het() -> None:
    summary = summarize_second_hit([_sv("DEL", {"S1": "0/1"})], ["S1"])
    assert summary["sv_count"] == 1
    assert summary["sv_types"] == ["DEL"]
    assert summary["affected_zygosity"] == "het"
    assert summary["has_deletion"] is True  # the unmasking case


def test_homozygous_sv() -> None:
    summary = summarize_second_hit([_sv("DUP", {"S1": "1/1"})], ["S1"])
    assert summary["affected_zygosity"] == "hom"
    assert summary["has_deletion"] is False


def test_mixed_zygosity_across_svs() -> None:
    summary = summarize_second_hit(
        [_sv("DEL", {"S1": "0/1"}), _sv("INS", {"S1": "1/1"})], ["S1"]
    )
    assert summary["affected_zygosity"] == "mixed"
    assert summary["sv_types"] == ["DEL", "INS"]
    assert summary["has_deletion"] is True


def test_no_affected_genotype_leaves_zygosity_unknown() -> None:
    # SV present in the family but not called in the affected sample.
    summary = summarize_second_hit([_sv("INV", {"S2": "0/1"})], ["S1"])
    assert summary["affected_zygosity"] is None
    assert summary["has_deletion"] is False


def test_scan_groups_svs_by_gene(monkeypatch) -> None:
    rows = [
        # variantId, svType, chrom, start, end, gene_symbols, sampleIds, gts
        ("sv1", "DEL", "1", 100, 200, ["BRCA2", "fgr"], ["S1", "S2"], ["0/1", "0/0"]),
        ("sv2", "DUP", "1", 300, 400, ["BRCA2"], ["S1"], ["1/1"]),
    ]

    async def _fake_execute(query, params):  # noqa: ANN001
        assert params["family_guid"] == "u1"
        return rows

    monkeypatch.setattr(cfv, "execute_clickhouse", _fake_execute)
    context = types.SimpleNamespace(assembly_name="GRCh38", family_uuid="u1")
    gene_map, sv_total = asyncio.run(cfv._scan_family_sv_gene_map(context))

    assert sv_total == 2  # two distinct SVs
    assert set(gene_map) == {"BRCA2", "FGR"}  # gene symbols upper-cased
    assert len(gene_map["BRCA2"]) == 2
    assert gene_map["BRCA2"][0]["gt"] == {"S1": "0/1", "S2": "0/0"}
    assert gene_map["FGR"][0]["sv_id"] == "sv1"
