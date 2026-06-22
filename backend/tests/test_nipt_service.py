from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.schemas import FamilyMemberOut, FamilyOut
from backend.app.services import nipt_service
from backend.app.services.clickhouse_family_variants import SmallVariantCall, SmallVariantRecord
from backend.app.services.nipt_service import (
    build_nipt_observations,
    derive_father_state,
    get_family_nipt_variants,
    run_family_nipt_analysis,
)


def _call(sample: str, gt: str, *, dp=None, af=None, ad=None) -> SmallVariantCall:
    return SmallVariantCall(sample=sample, gt=gt, gq=None, dp=dp, af=af or [], ad=ad or [], ps=None)


def _record(
    variant_id: str,
    *,
    chrom: str = "1",
    calls: list[SmallVariantCall],
    qual: float | None = 30.0,
    start: int = 100,
) -> SmallVariantRecord:
    return SmallVariantRecord(
        variant_key=None,
        variant_id=variant_id,
        chr=chrom,
        start=start,
        end=start,
        ref="A",
        alt="G",
        source=None,
        rsid=None,
        filters=[],
        gene_symbols=[],
        annotations=[],
        calls=calls,
        qual=qual,
    )


# --------------------------------------------------------------------------- #
# derive_father_state
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "gt,expected",
    [
        ("0/0", "hom_ref"),
        ("0/1", "het"),
        ("1/0", "het"),
        ("0|1", "het"),
        ("1/1", "hom_alt"),
        ("1|1", "hom_alt"),
        ("./.", "missing"),
        ("", "missing"),
    ],
)
def test_derive_father_state(gt: str, expected: str) -> None:
    assert derive_father_state(_call("father-1", gt)) == expected


def test_derive_father_state_missing_when_no_call() -> None:
    assert derive_father_state(None) == "missing"


# --------------------------------------------------------------------------- #
# build_nipt_observations
# --------------------------------------------------------------------------- #

def test_build_observation_paternal_transmitted_site() -> None:
    record = _record(
        "1-100-A-G",
        calls=[
            _call("father-1", "0/1", dp=50, ad=[25, 25]),
            _call("cfdna-1", "0/1", dp=120, af=[0.05], ad=[114, 6]),
        ],
        qual=42.0,
    )
    sites = build_nipt_observations(
        [record], father_sample_id="father-1", cfdna_sample_id="cfdna-1"
    )
    assert len(sites) == 1
    site = sites[0]
    assert site.variant_id == "1-100-A-G"
    assert site.is_autosomal
    assert site.father_state == "het"
    assert site.father_dp == 50
    assert site.cf_dp == 120
    assert site.cf_alt_reads == 6
    assert site.cf_vaf == pytest.approx(0.05)
    assert site.cf_present
    assert site.cf_qual == 42.0


def test_build_observation_false_negative_site_is_absent() -> None:
    record = _record(
        "1-200-A-G",
        calls=[
            _call("father-1", "1/1", dp=50, ad=[0, 50]),
            _call("cfdna-1", "0/0", dp=100, ad=[100, 0]),
        ],
    )
    site = build_nipt_observations(
        [record], father_sample_id="father-1", cfdna_sample_id="cfdna-1"
    )[0]
    assert site.father_state == "hom_alt"
    assert site.cf_alt_reads == 0
    assert not site.cf_present


def test_build_observation_missing_father_and_sex_chromosome() -> None:
    record = _record(
        "X-100-A-G",
        chrom="X",
        calls=[_call("cfdna-1", "0/1", dp=120, af=[0.05], ad=[114, 6])],
    )
    site = build_nipt_observations(
        [record], father_sample_id="father-1", cfdna_sample_id="cfdna-1"
    )[0]
    assert site.father_state == "missing"
    assert site.father_dp is None
    assert not site.is_autosomal


def test_build_observation_skips_sites_without_cfdna_call() -> None:
    record = _record("1-300-A-G", calls=[_call("father-1", "0/1", dp=50, ad=[25, 25])])
    assert build_nipt_observations(
        [record], father_sample_id="father-1", cfdna_sample_id="cfdna-1"
    ) == []


# --------------------------------------------------------------------------- #
# run_family_nipt_analysis (I/O mocked)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_run_family_nipt_analysis_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    family = FamilyOut(
        id="family-uuid",
        family_id="NIPT001",
        created_at=datetime.now(timezone.utc),
        members=[
            FamilyMemberOut(sample_id="father-1", role="father", affected=False),
            FamilyMemberOut(
                sample_id="cfdna-1",
                role="mother",
                affected=False,
                sample_metadata={"assay": "nipt_cfdna"},
            ),
        ],
        metadata={"analysis_type": "monogenic_nipt"},
    )

    records = [
        _record(
            f"1-{i}-A-G",
            start=i,
            calls=[
                _call("father-1", "0/1", dp=50, ad=[25, 25]),
                _call("cfdna-1", "0/1", dp=400, af=[0.05], ad=[380, 20]),
            ],
        )
        for i in range(40)
    ]
    records.append(
        _record(
            "1-9000-A-G",
            start=9000,
            calls=[
                _call("father-1", "0/0", dp=50, ad=[50, 0]),
                _call("cfdna-1", "0/1", dp=600, af=[0.5], ad=[300, 300]),
            ],
        )
    )

    async def fake_get_family_record(_session, _family_id, _user):
        return family

    async def fake_build_context(_session, *, family_identifier, user, project_id=None):
        return object()

    async def fake_fetch(_context, _filters, *, limit=None, **_kwargs):
        return records

    monkeypatch.setattr(nipt_service, "get_family_record", fake_get_family_record)
    monkeypatch.setattr(nipt_service, "build_family_metadata_context", fake_build_context)
    monkeypatch.setattr(nipt_service, "_fetch_small_variant_rows", fake_fetch)

    result = await run_family_nipt_analysis(
        session=None,  # type: ignore[arg-type]
        family_id="NIPT001",
        user=None,  # type: ignore[arg-type]
    )

    assert result.fetal_fraction.ff_computed == pytest.approx(0.10, abs=0.01)
    assert result.fetal_fraction.n_sites == 40
    assert result.category_counts[7] == 40
    assert result.category_counts[3] == 1


@pytest.mark.asyncio
async def test_run_family_nipt_analysis_rejects_non_nipt_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family = FamilyOut(
        id="family-uuid",
        family_id="FAM001",
        created_at=datetime.now(timezone.utc),
        members=[FamilyMemberOut(sample_id="father-1", role="father", affected=False)],
        metadata={},
    )

    async def fake_get_family_record(_session, _family_id, _user):
        return family

    monkeypatch.setattr(nipt_service, "get_family_record", fake_get_family_record)

    with pytest.raises(Exception) as excinfo:
        await run_family_nipt_analysis(
            session=None,  # type: ignore[arg-type]
            family_id="FAM001",
            user=None,  # type: ignore[arg-type]
        )
    assert "monogenic NIPT" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# get_family_nipt_variants (I/O mocked)
# --------------------------------------------------------------------------- #

def _nipt_family() -> FamilyOut:
    return FamilyOut(
        id="family-uuid",
        family_id="NIPT001",
        created_at=datetime.now(timezone.utc),
        members=[
            FamilyMemberOut(sample_id="father-1", role="father", affected=False),
            FamilyMemberOut(
                sample_id="cfdna-1",
                role="mother",
                affected=False,
                sample_metadata={"assay": "nipt_cfdna"},
            ),
        ],
        metadata={"analysis_type": "monogenic_nipt"},
    )


def _wire_variants_mocks(monkeypatch: pytest.MonkeyPatch, *, cohort, filtered) -> None:
    async def fake_get_family_record(_session, _family_id, _user):
        return _nipt_family()

    async def fake_build_context(_session, *, family_identifier, user, project_id=None):
        return object()

    async def fake_fetch(_context, filters, *, limit=None, **_kwargs):
        # The cohort (FF) load carries no gene filter; the variant load does.
        return cohort if filters.gene is None else filtered

    monkeypatch.setattr(nipt_service, "get_family_record", fake_get_family_record)
    monkeypatch.setattr(nipt_service, "build_family_metadata_context", fake_build_context)
    monkeypatch.setattr(nipt_service, "_fetch_small_variant_rows", fake_fetch)


def _cohort_cat7_records() -> list[SmallVariantRecord]:
    return [
        _record(
            f"1-{i}-A-G",
            start=i,
            calls=[
                _call("father-1", "0/1", dp=50, ad=[25, 25]),
                _call("cfdna-1", "0/1", dp=400, af=[0.05], ad=[380, 20]),
            ],
        )
        for i in range(40)
    ]


def _de_novo_and_cat3_records() -> list[SmallVariantRecord]:
    de_novo = _record(
        "1-9000-A-G",
        start=9000,
        calls=[
            _call("father-1", "0/0", dp=50, ad=[50, 0]),
            _call("cfdna-1", "0/1", dp=300, af=[0.05], ad=[285, 15]),
        ],
    )
    cat3 = _record(
        "1-9100-A-G",
        start=9100,
        calls=[
            _call("father-1", "0/0", dp=50, ad=[50, 0]),
            _call("cfdna-1", "0/1", dp=600, af=[0.5], ad=[300, 300]),
        ],
    )
    return [de_novo, cat3]


@pytest.mark.asyncio
async def test_get_family_nipt_variants_classifies_filtered_subset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_variants_mocks(
        monkeypatch, cohort=_cohort_cat7_records(), filtered=_de_novo_and_cat3_records()
    )

    result = await get_family_nipt_variants(
        session=None,  # type: ignore[arg-type]
        family_id="NIPT001",
        user=None,  # type: ignore[arg-type]
        query_filters={"gene": "BRCA1"},
    )

    assert result.fetal_fraction.ff_computed == pytest.approx(0.10, abs=0.01)
    assert result.total == 2
    categories = {item.classification.category for item in result.variants}
    assert categories == {1, 3}


@pytest.mark.asyncio
async def test_get_family_nipt_variants_category_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_variants_mocks(
        monkeypatch, cohort=_cohort_cat7_records(), filtered=_de_novo_and_cat3_records()
    )

    result = await get_family_nipt_variants(
        session=None,  # type: ignore[arg-type]
        family_id="NIPT001",
        user=None,  # type: ignore[arg-type]
        query_filters={"gene": "BRCA1"},
        categories=[1],
    )

    assert result.total == 1
    assert result.variants[0].classification.category == 1


@pytest.mark.asyncio
async def test_get_family_nipt_variants_de_novo_inheritance_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_variants_mocks(
        monkeypatch, cohort=_cohort_cat7_records(), filtered=_de_novo_and_cat3_records()
    )

    result = await get_family_nipt_variants(
        session=None,  # type: ignore[arg-type]
        family_id="NIPT001",
        user=None,  # type: ignore[arg-type]
        query_filters={"gene": "BRCA1"},
        inheritance="de_novo",
    )

    assert {item.classification.category for item in result.variants} == {1}


@pytest.mark.asyncio
async def test_get_family_nipt_variants_rejects_unsupported_preset() -> None:
    with pytest.raises(Exception) as excinfo:
        await get_family_nipt_variants(
            session=None,  # type: ignore[arg-type]
            family_id="NIPT001",
            user=None,  # type: ignore[arg-type]
            inheritance="recessive_at_risk",
        )
    assert "inheritance preset" in str(excinfo.value)
