from __future__ import annotations

from backend.app.services.data_scope import is_primary_chromosome
from backend.app.services.gene_metadata_service import _pick_primary_gene_doc


def test_is_primary_chromosome_accepts_main_assembly_only() -> None:
    for value in ("1", "22", "X", "Y", "MT", "M", "chr1", "chrX"):
        assert is_primary_chromosome(value), value
    for value in ("1_KI270766v1_alt", "Un_GL000195v1", "17_GL000205v2_random", "GL000009.2", "23", ""):
        assert not is_primary_chromosome(value), value


def test_pick_primary_gene_doc_prefers_effective_chromosome_over_larger_alt_contig() -> None:
    # The ALT-contig copy is intentionally "larger"/exon-richer so the old
    # size-only heuristic would have chosen it.
    alt_contig = {"chr": "1_KI270766v1_alt", "start": 0, "end": 100_000, "exons": [1, 2, 3, 4], "gene_id": "ALT"}
    primary = {"chr": "1", "start": 1_000, "end": 50_000, "exons": [1, 2], "gene_id": "PRIMARY"}

    chosen = _pick_primary_gene_doc([alt_contig, primary])

    assert chosen["chr"] == "1"
    assert chosen["gene_id"] == "PRIMARY"


def test_pick_primary_gene_doc_falls_back_to_alt_contig_when_no_primary_exists() -> None:
    alt_only = {"chr": "Un_GL000195v1", "start": 0, "end": 10_000, "exons": [], "gene_id": "ALT"}

    chosen = _pick_primary_gene_doc([alt_only])

    assert chosen["gene_id"] == "ALT"
