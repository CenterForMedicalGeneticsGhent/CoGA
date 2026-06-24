from __future__ import annotations

import random

from backend.app.services.sample_integrity_qc import (
    PedigreeSpec,
    classify_relatedness,
    evaluate_sample_integrity,
    infer_sex,
    king_relatedness,
    mendelian_stats,
)

N_SITES = 4_000


def _founder(rng: random.Random, n: int = N_SITES, p: float = 0.5):
    return [(int(rng.random() < p), int(rng.random() < p)) for _ in range(n)]


def _child(rng: random.Random, father, mother):
    # Inherit one allele from each parent at every site.
    return [(rng.choice(f), rng.choice(m)) for f, m in zip(father, mother)]


def _trio(seed: int):
    rng = random.Random(seed)
    father = _founder(rng)
    mother = _founder(rng)
    child = _child(rng, father, mother)
    return father, mother, child


# --- KING relatedness --------------------------------------------------------

def test_king_duplicate_is_half() -> None:
    father, _mother, _child = _trio(1)
    kinship, ibs0, n = king_relatedness(father, father)
    assert n == N_SITES
    assert kinship == 0.5
    assert classify_relatedness(kinship, ibs0, n) == "duplicate"


def test_king_parent_child_is_first_degree_with_zero_ibs0() -> None:
    father, _mother, child = _trio(2)
    kinship, ibs0, n = king_relatedness(father, child)
    assert 0.18 < kinship < 0.32  # ~0.25
    assert ibs0 == 0.0  # a true parent and child are never opposite homozygotes
    assert classify_relatedness(kinship, ibs0, n) == "parent-child"


def test_king_unrelated_parents_are_unrelated() -> None:
    father, mother, _child = _trio(3)
    kinship, ibs0, n = king_relatedness(father, mother)
    assert kinship < 0.0442
    assert classify_relatedness(kinship, ibs0, n) == "unrelated"


def test_king_full_siblings_are_first_degree_with_nonzero_ibs0() -> None:
    rng = random.Random(4)
    father = _founder(rng)
    mother = _founder(rng)
    sib1 = _child(rng, father, mother)
    sib2 = _child(rng, father, mother)
    kinship, ibs0, n = king_relatedness(sib1, sib2)
    assert 0.18 < kinship < 0.32
    assert ibs0 > 0.0  # siblings can be opposite homozygotes
    assert classify_relatedness(kinship, ibs0, n) == "sibling"


def test_classify_relatedness_needs_minimum_sites() -> None:
    assert classify_relatedness(0.25, 0.0, 10) == "indeterminate"


# --- Sex inference -----------------------------------------------------------

def test_infer_sex_male_from_hemizygous_x() -> None:
    # Males call essentially no heterozygotes on the X.
    x = [(1, 1) if i % 2 else (0, 0) for i in range(N_SITES)]
    inferred, het_rate, n = infer_sex(x)
    assert inferred == "male"
    assert het_rate == 0.0
    assert n == N_SITES


def test_infer_sex_female_from_heterozygous_x() -> None:
    rng = random.Random(5)
    x = _founder(rng)  # ~50% het
    inferred, het_rate, _n = infer_sex(x)
    assert inferred == "female"
    assert het_rate is not None and het_rate > 0.15


def test_infer_sex_indeterminate_without_enough_sites() -> None:
    inferred, _rate, n = infer_sex([(0, 1), (1, 1)])
    assert inferred == "indeterminate"
    assert n == 2


# --- Mendelian errors --------------------------------------------------------

def test_mendelian_clean_trio_has_no_errors() -> None:
    father, mother, child = _trio(6)
    informative, errors = mendelian_stats(child, father, mother)
    assert informative == N_SITES
    assert errors == 0


def test_mendelian_swapped_child_has_many_errors() -> None:
    father, mother, _child = _trio(7)
    stranger = _founder(random.Random(99))  # unrelated "child"
    informative, errors = mendelian_stats(stranger, father, mother)
    assert informative == N_SITES
    # An unrelated child violates transmission at a large fraction of sites.
    assert errors / informative > 0.1


def test_mendelian_single_parent_flags_no_shared_allele() -> None:
    # child shares an allele with the parent at every site -> no error.
    parent = [(0, 1)] * 100
    child_ok = [(1, 1)] * 100
    informative, errors = mendelian_stats(child_ok, parent, None)
    assert (informative, errors) == (100, 0)
    # child homozygous for an allele the parent lacks -> error every site.
    child_bad = [(0, 0)] * 100
    parent_alt = [(1, 1)] * 100
    informative, errors = mendelian_stats(child_bad, parent_alt, None)
    assert (informative, errors) == (100, 100)


# --- Orchestration ----------------------------------------------------------

def _trio_spec(sexes: dict[str, str]) -> PedigreeSpec:
    return PedigreeSpec(
        recorded_sex=sexes,
        parents_of={"CHILD": {"father": "FATHER", "mother": "MOTHER"}},
    )


def test_evaluate_clean_trio_passes() -> None:
    father, mother, child = _trio(10)
    autosomal = {"FATHER": father, "MOTHER": mother, "CHILD": child}
    x = {
        "FATHER": [(0, 0)] * N_SITES,
        "MOTHER": _founder(random.Random(11)),
        "CHILD": [(0, 0)] * N_SITES,
    }
    spec = _trio_spec({"FATHER": "male", "MOTHER": "female", "CHILD": "male"})
    report = evaluate_sample_integrity(autosomal, x, spec)

    assert report.overall_status == "pass"
    pc = [c for c in report.relatedness_checks if c.expected_relationship == "parent-child"]
    assert len(pc) == 2 and all(c.status == "pass" for c in pc)
    assert all(c.status == "pass" for c in report.mendelian_checks)
    assert all(c.status == "pass" for c in report.sex_checks)


def test_evaluate_swapped_child_fails_relatedness_and_mendel() -> None:
    father, mother, _child = _trio(12)
    stranger = _founder(random.Random(123))
    autosomal = {"FATHER": father, "MOTHER": mother, "CHILD": stranger}
    spec = _trio_spec({"FATHER": "male", "MOTHER": "female", "CHILD": "male"})
    report = evaluate_sample_integrity(autosomal, {}, spec)

    assert report.overall_status == "fail"
    pc = [c for c in report.relatedness_checks if c.expected_relationship == "parent-child"]
    assert any(c.status == "fail" for c in pc)
    assert any(c.status == "fail" for c in report.mendelian_checks)


def test_evaluate_sex_mismatch_fails() -> None:
    father, mother, child = _trio(13)
    autosomal = {"FATHER": father, "MOTHER": mother, "CHILD": child}
    # CHILD genotypes on X are heterozygous (female-like) but recorded male.
    x = {"CHILD": _founder(random.Random(14))}
    spec = _trio_spec({"FATHER": "male", "MOTHER": "female", "CHILD": "male"})
    report = evaluate_sample_integrity(autosomal, x, spec)

    child_sex = next(c for c in report.sex_checks if c.sample_id == "CHILD")
    assert child_sex.inferred_sex == "female"
    assert child_sex.status == "fail"
    assert report.overall_status == "fail"
