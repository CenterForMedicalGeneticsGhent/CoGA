from __future__ import annotations

import asyncio
import random

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


def _patch(monkeypatch, *, swap_child: bool):
    async def _fake_context(session, *, family_identifier, user, project_id=None):
        return _context()

    async def _fake_fetch(context, *, chrom, start, end, limit):
        if chrom == sample_integrity_service.QC_X_CHROM:
            return _x_rows(600)
        return _autosomal_rows(800, seed=hash(chrom) % 1000, swap_child=swap_child)

    monkeypatch.setattr(sample_integrity_service, "build_family_metadata_context", _fake_context)
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
