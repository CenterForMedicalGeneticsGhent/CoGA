"""Sample-integrity / pedigree-concordance QC (pure core).

In a pedigree-driven pipeline the worst silent failure is a sample swap or a
mislabelled relationship: the variants are real but attributed to the wrong
person, so inheritance reasoning is quietly wrong. This module runs three
reference-free checks that catch that before interpretation:

  * Sex concordance -- genotype-inferred sex (chrX heterozygosity) vs the
    recorded sex.
  * Relatedness concordance -- KING-robust kinship + IBS0 between sample pairs
    vs the relationship the pedigree asserts (parent-child / sibling / unrelated).
  * Mendelian error rate -- parent-child / trio transmission consistency.

All inputs are pre-parsed genotype arrays; there is no I/O here so the maths is
unit-testable. The loader and pedigree resolution live in the service layer.

Genotypes are ``tuple[int, int]`` allele-index pairs (e.g. ``(0, 1)``); ``None``
marks a missing / unusable call at that site. Arrays for different samples are
aligned by index (same site at the same position in every sample's list).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Genotype = tuple[int, int]
Status = Literal["pass", "warn", "fail", "skip"]

# --- Relatedness (KING-robust) thresholds -----------------------------------
# Standard KING kinship cut-points (Manichaikul et al. 2010): duplicate ~0.5,
# first-degree ~0.25, second-degree ~0.125, third-degree ~0.0625.
MIN_RELATEDNESS_SITES = 1_000
KINSHIP_DUPLICATE = 0.354
KINSHIP_FIRST_DEGREE = 0.177
KINSHIP_SECOND_DEGREE = 0.0884
KINSHIP_THIRD_DEGREE = 0.0442
# Within first-degree, parent-child share an allele at every site so IBS0 ~ 0,
# whereas full siblings are opposite homozygotes at a few percent of sites.
IBS0_PARENT_CHILD_MAX = 0.008

# --- Sex inference (chrX heterozygosity) ------------------------------------
MIN_X_SITES = 200
MALE_MAX_X_HET = 0.05  # hemizygous males call almost no X heterozygotes
FEMALE_MIN_X_HET = 0.15

# --- Mendelian error rate ----------------------------------------------------
MIN_MENDEL_SITES = 200
MENDEL_WARN_RATE = 0.02
MENDEL_FAIL_RATE = 0.05


@dataclass(slots=True)
class SexCheck:
    sample_id: str
    recorded_sex: str
    inferred_sex: str  # "male" | "female" | "indeterminate"
    x_het_rate: float | None
    x_sites: int
    status: Status
    message: str


@dataclass(slots=True)
class RelatednessCheck:
    sample_a: str
    sample_b: str
    expected_relationship: str
    inferred_relationship: str
    kinship: float
    ibs0_rate: float
    informative_sites: int
    status: Status
    message: str


@dataclass(slots=True)
class MendelianCheck:
    child: str
    parents: list[str]
    informative_sites: int
    mendel_errors: int
    mendel_rate: float
    status: Status
    message: str


@dataclass(slots=True)
class SampleIntegrityReport:
    overall_status: Status
    sex_checks: list[SexCheck] = field(default_factory=list)
    relatedness_checks: list[RelatednessCheck] = field(default_factory=list)
    mendelian_checks: list[MendelianCheck] = field(default_factory=list)
    autosomal_sites: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PedigreeSpec:
    """The pedigree's assertions, resolved from family metadata."""

    recorded_sex: dict[str, str]  # sample_id -> "male" | "female" | "unknown"
    # child -> {"father": id, "mother": id} (either parent may be absent)
    parents_of: dict[str, dict[str, str]]


_STATUS_RANK: dict[Status, int] = {"skip": 0, "pass": 1, "warn": 2, "fail": 3}


def _worst(statuses: list[Status]) -> Status:
    worst: Status = "skip"
    for status in statuses:
        if _STATUS_RANK[status] > _STATUS_RANK[worst]:
            worst = status
    return worst


def _is_het(gt: Genotype) -> bool:
    return gt[0] != gt[1]


def _is_biallelic(gt: Genotype) -> bool:
    return gt[0] in (0, 1) and gt[1] in (0, 1)


# --- chrX heterozygosity → sex ----------------------------------------------

def x_heterozygosity(genotypes: list[Genotype | None]) -> tuple[float | None, int]:
    """(het_rate, n_called) over biallelic chrX sites."""
    called = 0
    het = 0
    for gt in genotypes:
        if gt is None or not _is_biallelic(gt):
            continue
        called += 1
        if _is_het(gt):
            het += 1
    if called == 0:
        return None, 0
    return het / called, called


def infer_sex(genotypes: list[Genotype | None]) -> tuple[str, float | None, int]:
    het_rate, n = x_heterozygosity(genotypes)
    if het_rate is None or n < MIN_X_SITES:
        return "indeterminate", het_rate, n
    if het_rate <= MALE_MAX_X_HET:
        return "male", het_rate, n
    if het_rate >= FEMALE_MIN_X_HET:
        return "female", het_rate, n
    return "indeterminate", het_rate, n


# --- KING-robust kinship + IBS0 ---------------------------------------------

def king_relatedness(
    a: list[Genotype | None], b: list[Genotype | None]
) -> tuple[float, float, int]:
    """KING-robust kinship and IBS0 rate over jointly-called biallelic sites.

    kinship = (N_het,het - 2*N_opposite-hom) / (N_het(a) + N_het(b)); duplicates
    ~0.5, first-degree ~0.25. IBS0 (opposite homozygotes) separates parent-child
    (~0) from full siblings within the first-degree band.
    """
    het_a = het_b = het_het = opp_hom = n = 0
    for ga, gb in zip(a, b):
        if ga is None or gb is None or not _is_biallelic(ga) or not _is_biallelic(gb):
            continue
        n += 1
        a_het, b_het = _is_het(ga), _is_het(gb)
        if a_het:
            het_a += 1
        if b_het:
            het_b += 1
        if a_het and b_het:
            het_het += 1
        elif not a_het and not b_het and ga[0] != gb[0]:
            opp_hom += 1
    if n == 0:
        return 0.0, 0.0, 0
    denom = het_a + het_b
    kinship = (het_het - 2 * opp_hom) / denom if denom else 0.0
    return kinship, opp_hom / n, n


def classify_relatedness(kinship: float, ibs0_rate: float, n_sites: int) -> str:
    if n_sites < MIN_RELATEDNESS_SITES:
        return "indeterminate"
    if kinship > KINSHIP_DUPLICATE:
        return "duplicate"
    if kinship > KINSHIP_FIRST_DEGREE:
        return "parent-child" if ibs0_rate < IBS0_PARENT_CHILD_MAX else "sibling"
    if kinship > KINSHIP_SECOND_DEGREE:
        return "second-degree"
    if kinship > KINSHIP_THIRD_DEGREE:
        return "third-degree"
    return "unrelated"


# --- Mendelian consistency ---------------------------------------------------

def _mendelian_consistent(father: Genotype, mother: Genotype, child: Genotype) -> bool:
    """Child genotype forms from one paternal + one maternal allele."""
    child_state = tuple(sorted(child))
    for pa in father:
        for ma in mother:
            if tuple(sorted((pa, ma))) == child_state:
                return True
    return False


def _shares_allele(a: Genotype, b: Genotype) -> bool:
    return bool({a[0], a[1]} & {b[0], b[1]})


def mendelian_stats(
    child: list[Genotype | None],
    father: list[Genotype | None] | None,
    mother: list[Genotype | None] | None,
) -> tuple[int, int]:
    """(informative_sites, mendel_errors) for a child against present parent(s).

    A trio site is informative when child and both present parents are called;
    an error is a transmission the parents cannot produce. With a single known
    parent the only detectable error is the child sharing no allele with it.
    """
    informative = errors = 0
    n = len(child)
    for i in range(n):
        c = child[i]
        if c is None:
            continue
        f = father[i] if father is not None and i < len(father) else None
        m = mother[i] if mother is not None and i < len(mother) else None
        if father is not None and mother is not None:
            if f is None or m is None:
                continue
            informative += 1
            if not _mendelian_consistent(f, m, c):
                errors += 1
        else:
            parent = f if father is not None else m
            if parent is None:
                continue
            informative += 1
            if not _shares_allele(parent, c):
                errors += 1
    return informative, errors


# --- Orchestration -----------------------------------------------------------

def _norm_sex(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text in ("male", "m", "1"):
        return "male"
    if text in ("female", "f", "2"):
        return "female"
    return "unknown"


def _evaluate_sex(
    sample_id: str, recorded: str, x_gts: list[Genotype | None] | None
) -> SexCheck:
    if not x_gts:
        return SexCheck(sample_id, recorded, "indeterminate", None, 0, "skip",
                        "No chrX genotypes available for sex inference.")
    inferred, het_rate, n = infer_sex(x_gts)
    rate_text = f"{het_rate:.1%} chrX het over {n} sites" if het_rate is not None else "no sites"
    if inferred == "indeterminate":
        return SexCheck(sample_id, recorded, inferred, het_rate, n, "warn",
                        f"Could not infer sex ({rate_text}).")
    if recorded == "unknown":
        return SexCheck(sample_id, recorded, inferred, het_rate, n, "warn",
                        f"Sex not recorded; genotypes indicate {inferred} ({rate_text}).")
    if inferred == recorded:
        return SexCheck(sample_id, recorded, inferred, het_rate, n, "pass",
                        f"Genotype-inferred sex matches the record ({rate_text}).")
    return SexCheck(sample_id, recorded, inferred, het_rate, n, "fail",
                    f"Recorded {recorded} but genotypes indicate {inferred} "
                    f"({rate_text}) — possible sample swap or mislabel.")


def _relationship_check(
    a: str,
    b: str,
    expected: str,
    autosomal: dict[str, list[Genotype | None]],
) -> RelatednessCheck:
    kinship, ibs0, n = king_relatedness(autosomal.get(a, []), autosomal.get(b, []))
    inferred = classify_relatedness(kinship, ibs0, n)
    metrics = f"kinship {kinship:.3f}, IBS0 {ibs0:.2%}, {n} sites"
    status, message = _relationship_status(expected, inferred, n, metrics)
    return RelatednessCheck(a, b, expected, inferred, kinship, ibs0, n, status, message)


# A first-degree observation covers both parent-child and sibling.
_FIRST_DEGREE = {"parent-child", "sibling"}


def _relationship_status(
    expected: str, inferred: str, n: int, metrics: str
) -> tuple[Status, str]:
    if inferred == "indeterminate" or n < MIN_RELATEDNESS_SITES:
        return "warn", f"Too few shared sites to assess relatedness ({metrics})."
    if expected == "parent-child":
        if inferred == "parent-child":
            return "pass", f"Confirmed parent-child ({metrics})."
        return "fail", (
            f"Recorded parent-child but genotypes look {inferred} ({metrics}) — "
            "possible sample swap or wrong parent."
        )
    if expected == "sibling":
        if inferred in _FIRST_DEGREE:
            return "pass", f"Consistent with full siblings ({metrics})."
        return "fail", f"Recorded siblings but genotypes look {inferred} ({metrics})."
    # Expected unrelated (co-parents, or any pair with no asserted relationship).
    if inferred == "unrelated":
        return "pass", f"Unrelated, as expected ({metrics})."
    if inferred in ("third-degree", "second-degree"):
        return "warn", f"Unexpected relatedness — looks {inferred} ({metrics})."
    return "fail", (
        f"Recorded unrelated but genotypes look {inferred} ({metrics}) — "
        "possible duplicate or swap."
    )


def _mendelian_check(
    child: str,
    parents: dict[str, str],
    autosomal: dict[str, list[Genotype | None]],
) -> MendelianCheck | None:
    # Robust to the pedigree's parent-side keys ("father"/"mother"/"parent"):
    # use whichever stated parents actually have genotypes.
    parent_ids = [pid for pid in dict.fromkeys(parents.values()) if pid in autosomal]
    if not parent_ids:
        return None
    if len(parent_ids) >= 2:
        father, mother = autosomal[parent_ids[0]], autosomal[parent_ids[1]]
        parent_ids = parent_ids[:2]
    else:
        father, mother = autosomal[parent_ids[0]], None
    informative, errors = mendelian_stats(autosomal.get(child, []), father, mother)
    rate = errors / informative if informative else 0.0
    metrics = f"{errors}/{informative} sites ({rate:.2%})"
    if informative < MIN_MENDEL_SITES:
        status: Status = "warn"
        message = f"Too few informative sites for a reliable estimate ({metrics})."
    elif rate >= MENDEL_FAIL_RATE:
        status = "fail"
        message = f"High Mendelian-error rate {metrics} — likely swap or wrong parent."
    elif rate >= MENDEL_WARN_RATE:
        status = "warn"
        message = f"Elevated Mendelian-error rate {metrics}."
    else:
        status = "pass"
        message = f"Mendelian-error rate within tolerance ({metrics})."
    return MendelianCheck(child, parent_ids, informative, errors, rate, status, message)


def _sibling_pairs(parents_of: dict[str, dict[str, str]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    children = sorted(parents_of)
    for i, c1 in enumerate(children):
        for c2 in children[i + 1:]:
            shared = set(parents_of[c1].values()) & set(parents_of[c2].values())
            if shared:
                pairs.add((c1, c2))
    return pairs


def evaluate_sample_integrity(
    autosomal: dict[str, list[Genotype | None]],
    x_genotypes: dict[str, list[Genotype | None]],
    spec: PedigreeSpec,
) -> SampleIntegrityReport:
    """Run all three QC checks and roll up an overall status."""
    samples = sorted(autosomal)
    notes: list[str] = []

    sex_checks = [
        _evaluate_sex(s, _norm_sex(spec.recorded_sex.get(s)), x_genotypes.get(s))
        for s in samples
    ]

    # Build expected relationships from the pedigree, then assess every pair.
    expected: dict[tuple[str, str], str] = {}
    for child, parents in spec.parents_of.items():
        for parent in parents.values():
            if parent in autosomal and child in autosomal:
                expected[tuple(sorted((parent, child)))] = "parent-child"
    for a, b in _sibling_pairs(spec.parents_of):
        if a in autosomal and b in autosomal:
            expected.setdefault(tuple(sorted((a, b))), "sibling")

    relatedness_checks: list[RelatednessCheck] = []
    for i, a in enumerate(samples):
        for b in samples[i + 1:]:
            key = (a, b)
            exp = expected.get(key, "unrelated")
            check = _relationship_check(a, b, exp, autosomal)
            # Suppress the noise of "unrelated, as expected" pairs that carry no
            # pedigree assertion; keep only asserted pairs or surprising findings.
            if exp == "unrelated" and check.status == "pass":
                continue
            relatedness_checks.append(check)

    mendelian_checks: list[MendelianCheck] = []
    for child, parents in spec.parents_of.items():
        if child not in autosomal:
            continue
        check = _mendelian_check(child, parents, autosomal)
        if check is not None:
            mendelian_checks.append(check)

    autosomal_sites = max((len(v) for v in autosomal.values()), default=0)
    if not autosomal:
        notes.append("No genotypes were available; QC could not run.")
    elif autosomal_sites < MIN_RELATEDNESS_SITES:
        notes.append(
            f"Only {autosomal_sites} autosomal sites were available; "
            "relatedness estimates may be unreliable."
        )

    all_statuses = (
        [c.status for c in sex_checks]
        + [c.status for c in relatedness_checks]
        + [c.status for c in mendelian_checks]
    )
    overall = _worst(all_statuses) if all_statuses else "skip"

    return SampleIntegrityReport(
        overall_status=overall,
        sex_checks=sex_checks,
        relatedness_checks=relatedness_checks,
        mendelian_checks=mendelian_checks,
        autosomal_sites=autosomal_sites,
        notes=notes,
    )
