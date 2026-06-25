from __future__ import annotations

import asyncio
import random
import types

from backend.app.services import sample_integrity_service
from backend.app.services.family_metadata_context import FamilyMetadataContext

SAMPLES = ["FATHER", "MOTHER", "CHILD"]


def _context() -> FamilyMetadataContext:
    sample_rows = [
        {"sample_id": "FATHER", "role": "father", "sex": "male"},
        {"sample_id": "MOTHER", "role": "mother", "sex": "female"},
        {"sample_id": "CHILD", "role": "proband", "sex": "male"},
    ]
    relationship_rows = [
        {"relationship_type": "parent_child", "sample_id_a": "FATHER", "sample_id_b": "CHILD", "role_a": "father"},
        {"relationship_type": "parent_child", "sample_id_a": "MOTHER", "sample_id_b": "CHILD", "role_a": "mother"},
    ]
    return FamilyMetadataContext(
        family_uuid="fam-uuid",
        family_id="FAM1",
        project_ids=[],
        sample_rows=sample_rows,
        sample_uuid_to_name={f"uuid-{s}": s for s in SAMPLES},
        sample_name_to_uuid={s: f"uuid-{s}" for s in SAMPLES},
        affected_sample_names=["CHILD"],
        assembly_id="asm",
        assembly_name="GRCh38",
        relationship_rows=relationship_rows,
    )


def _phased(gt: tuple[int, int]) -> str:
    return f"{gt[0]}|{gt[1]}"


def _autosomal_rows(n: int, seed: int, swap_child: bool):
    rng = random.Random(seed)
    rows = []
    stranger = random.Random(seed + 777)
    for i in range(n):
        f = (int(rng.random() < 0.5), int(rng.random() < 0.5))
        m = (int(rng.random() < 0.5), int(rng.random() < 0.5))
        if swap_child:
            c = (int(stranger.random() < 0.5), int(stranger.random() < 0.5))
        else:
            c = (rng.choice(f), rng.choice(m))
        rows.append((i, "A", "G", SAMPLES, [_phased(f), _phased(m), _phased(c)]))
    return rows


def _x_rows(n: int):
    rng = random.Random(3)
    rows = []
    for i in range(n):
        father = (1, 1) if i % 2 else (0, 0)  # male: hemizygous -> hom
        child = (0, 0) if i % 2 else (1, 1)  # male
        mother = (int(rng.random() < 0.5), int(rng.random() < 0.5))  # female: het
        rows.append((i, "A", "G", SAMPLES, [_phased(father), _phased(mother), _phased(child)]))
    return rows


def _patch(monkeypatch, *, swap_child: bool, metadata: dict | None = None):
    async def _fake_context(session, *, family_identifier, user, project_id=None):
        return _context()

    async def _fake_get_family(session, family_id, user):
        return types.SimpleNamespace(metadata=metadata or {})

    async def _fake_sources(context):
        return ["clair3"]

    async def _fake_fetch(context, *, chrom, start, end, limit, source=None):
        if chrom == sample_integrity_service.QC_X_CHROM:
            return _x_rows(600)
        return _autosomal_rows(800, seed=hash(chrom) % 1000, swap_child=swap_child)

    monkeypatch.setattr(sample_integrity_service, "build_family_metadata_context", _fake_context)
    monkeypatch.setattr(sample_integrity_service, "get_family_record", _fake_get_family)
    monkeypatch.setattr(sample_integrity_service, "fetch_family_variant_sources", _fake_sources)
    monkeypatch.setattr(sample_integrity_service, "fetch_imputed_phased_genotypes", _fake_fetch)


def test_service_clean_trio_passes(monkeypatch) -> None:
    _patch(monkeypatch, swap_child=False)
    report = asyncio.run(
        sample_integrity_service.get_family_sample_integrity_qc(
            session=None, family_id="FAM1", user=None
        )
    )
    assert report.overall_status == "pass"
    assert {c.sample_id for c in report.sex_checks} == set(SAMPLES)
    assert all(c.status == "pass" for c in report.sex_checks)
    pc = [c for c in report.relatedness_checks if c.expected_relationship == "parent-child"]
    assert len(pc) == 2 and all(c.status == "pass" for c in pc)
    assert all(c.status == "pass" for c in report.mendelian_checks)
    # A trio with parent-child edges resolves to the WGS application on clair3.
    assert report.application == "wgs"
    assert report.genotype_source == "clair3"
    # 3 autosomes * 800 sites = 2400 autosomal sites loaded.
    assert report.autosomal_sites == 3 * 800


def test_service_swapped_child_fails(monkeypatch) -> None:
    _patch(monkeypatch, swap_child=True)
    report = asyncio.run(
        sample_integrity_service.get_family_sample_integrity_qc(
            session=None, family_id="FAM1", user=None
        )
    )
    assert report.overall_status == "fail"
    pc = [c for c in report.relatedness_checks if c.expected_relationship == "parent-child"]
    assert any(c.status == "fail" for c in pc)
    assert any(c.status == "fail" for c in report.mendelian_checks)


def test_service_nipt_runs_paternity_parent_sex_and_category_qc(monkeypatch) -> None:
    # A monogenic-NIPT family runs paternity (cat 7/8) + fetal sex + the category
    # distribution QC + germline parent sex (X zygosity, cfDNA excluded), but no
    # genotype relatedness/Mendelian checks.
    _patch(monkeypatch, swap_child=False, metadata={"analysis_type": "monogenic_nipt"})
    # The cfDNA sample is the mother member's maternal-plasma sample, so it sexes
    # the mother; there is no separate maternal germline sample.
    monkeypatch.setattr(
        sample_integrity_service, "resolve_nipt_trio",
        lambda family: types.SimpleNamespace(
            father_sample_id="FATHER", cfdna_sample_id="MOTHER"
        ),
    )
    import backend.app.services.nipt_service as nipt_service

    async def _fake_nipt(session, *, family_id, user, project_id=None, **kwargs):
        return types.SimpleNamespace(
            category_counts={1: 1, 2: 30, 3: 16, 4: 14, 7: 40, 8: 2},
            fetal_sex=types.SimpleNamespace(
                inferred="female", x_transmitted=12, x_not_transmitted=0, informative_sites=12
            ),
        )

    monkeypatch.setattr(nipt_service, "run_family_nipt_analysis", _fake_nipt)

    report = asyncio.run(
        sample_integrity_service.get_family_sample_integrity_qc(
            session=None, family_id="FAM1", user=None
        )
    )
    assert report.application == "nipt"
    assert report.relatedness_checks == [] and report.mendelian_checks == []
    # The two germline parents are sexed from X zygosity; the cfDNA mixture is not.
    assert {c.sample_id for c in report.sex_checks} == {"FATHER", "MOTHER"}
    assert all(c.status == "pass" for c in report.sex_checks)
    assert report.paternity_check is not None
    assert report.paternity_check.father == "FATHER"
    assert report.paternity_check.status == "pass"
    # Fetal sex from paternal-X transmission rides along with the NIPT path.
    assert report.fetal_sex_check is not None and report.fetal_sex_check.inferred_sex == "female"
    # Category QC: ~50% maternal transmission (30/60), de-novo low.
    assert report.category_qc_check is not None
    assert report.category_qc_check.maternal_inherited == 30
    assert report.category_qc_check.maternal_informative == 60
    assert report.category_qc_check.status == "pass"
    assert report.overall_status == "pass"


def test_service_nipt_degrades_to_warning_when_analysis_fails(monkeypatch) -> None:
    # Mock/partial data: the cfDNA analysis raises -> the page degrades to a
    # warning with an explanatory note instead of 500-ing.
    _patch(monkeypatch, swap_child=False, metadata={"analysis_type": "monogenic_nipt"})
    monkeypatch.setattr(
        sample_integrity_service, "resolve_nipt_trio",
        lambda family: types.SimpleNamespace(father_sample_id="FATHER", cfdna_sample_id="MOTHER"),
    )
    import backend.app.services.nipt_service as nipt_service

    async def _boom(session, *, family_id, user, project_id=None, **kwargs):
        raise RuntimeError("no cfDNA variants")

    monkeypatch.setattr(nipt_service, "run_family_nipt_analysis", _boom)

    report = asyncio.run(
        sample_integrity_service.get_family_sample_integrity_qc(
            session=None, family_id="FAM1", user=None
        )
    )
    assert report.overall_status == "warn"
    assert any("NIPT cfDNA analysis could not run" in note for note in report.notes)
    assert report.paternity_check is None
