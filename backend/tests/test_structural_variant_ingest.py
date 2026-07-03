"""Malformed structural-variant records must be skipped, not abort the whole ingest.

A single bad POS/END used to raise mid-loop, leaving partially-flushed ClickHouse rows
behind (issue #334). The record iterators now coerce coordinates and skip records that
can't be positioned — mirroring the package-import SV path.
"""

from app.services.structural_variant_ingest import (
    _coerce_int,
    _coerce_qual,
    iter_structural_variant_records,
)


def test_coerce_int_and_qual_are_tolerant() -> None:
    assert _coerce_int("100") == 100
    assert _coerce_int("100.0") == 100
    assert _coerce_int("junk") is None
    assert _coerce_int(".") is None
    assert _coerce_qual("60") == 60.0
    assert _coerce_qual(".") is None
    assert _coerce_qual("nan") is None
    assert _coerce_qual("junk") is None


def test_manual_records_skip_unparseable_coordinates() -> None:
    text = "\n".join(
        [
            "SV1 chr1 100 200 N <DEL> DEL 0/1",
            "SV2 chr1 notanumber 300 N <DEL> DEL 0/1",  # bad start -> skipped
            "SV3 chr2 400 500 N <DUP> DUP 1/1",
        ]
    )
    records = list(iter_structural_variant_records(text, "manual"))
    assert [r.variant_id for r in records] == ["SV1", "SV3"]
    assert records[0].start == 100 and records[0].end == 200


def test_sniffles_records_skip_bad_pos_and_tolerate_qual() -> None:
    rows = [
        "chr1\t100\tSV1\tN\t<DEL>\t60\tPASS\tSVTYPE=DEL;END=200\tGT\t0/1",
        "chr1\tXX\tSV2\tN\t<DEL>\t60\tPASS\tSVTYPE=DEL;END=300\tGT\t0/1",  # bad POS
        "chr2\t400\tSV3\tN\t<DUP>\tbadqual\tPASS\tSVTYPE=DUP;END=500\tGT\t1/1",
    ]
    records = list(iter_structural_variant_records("\n".join(rows), "sniffles"))
    assert [r.variant_id for r in records] == ["SV1", "SV3"]
    # A non-numeric QUAL is tolerated as None rather than aborting the record.
    assert records[1].qual is None
    assert records[0].qual == 60.0
