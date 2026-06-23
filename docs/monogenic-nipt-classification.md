# Monogenic NIPT — Fetal Fraction & Classification Algorithm

> **Status: implemented; this remains the algorithm reference.** This describes
> **Phase 3** of the [Monogenic NIPT](monogenic-nipt.md) feature — the fetal-fraction
> estimator and the per-variant classifier that together form
> `backend/app/services/nipt_analysis.py` — which has shipped (built test-first against
> synthetic data). It assumes the conceptual maths and the eight categories defined in
> the [main spec](monogenic-nipt.md#the-classification-maths).

The backend has **no numpy/scipy** dependency, so everything here is expressed for a
**pure-Python** implementation (`math.lgamma`, `math.log`, `math.exp`). That is
deliberate; do not add a heavy numeric dependency for this.

---

## 0. What this module does

```text
joined father+cfDNA site observations
        │
        ▼
[ quality filter ] ──► failed_quality (counted)
        │
        ▼
[ artifact filter ] ──► failed_artifact (counted)
        │
        ▼
[ estimate_fetal_fraction ]  ◄── optional external FF
        │   (FF + CI + N + disagreement flag)
        ▼
[ classify_site ] for every passing site
        │   (category 1–8 + maternal/fetal decomposition + confidence + flags)
        ▼
aggregate → NiptAnalysisResult
```

Two pure functions carry the maths — `estimate_fetal_fraction()` and `classify_site()` —
wrapped by an orchestrator `run_nipt_analysis()` that does the filtering, counting and
aggregation. Keep the two pure functions free of I/O so they can be unit-tested in
isolation against synthetic site lists.

---

## 1. Inputs

A combined two-sample VCF is joint-genotyped, so **every variant row carries both a
father call and a cfDNA call** (a hom-ref sample is `0/0`/`./.`, not missing). After
reading the `entries` table, each site is normalised into:

```python
@dataclass(slots=True)
class NiptSiteObservation:
    variant_id: str            # chr-pos-ref-alt
    chrom: str
    pos: int
    is_autosomal: bool

    # cfDNA (maternal plasma mixture) — the signal we classify
    cf_present: bool           # caller emitted alt support here
    cf_dp: int | None          # depth (prefer sum of AD)
    cf_alt_reads: int | None   # alt-supporting reads (prefer AD[alt])
    cf_vaf: float | None       # cf_alt_reads / cf_dp; fallback ab / af[0]
    cf_qual: float | None      # site-level VCF QUAL (Phase 1; a variant-level column)

    # father — used only to resolve father_state
    father_state: str          # 'hom_ref' | 'het' | 'hom_alt' | 'missing'
    father_dp: int | None
    father_qual: float | None
```

**`cf_vaf` vs `(cf_alt_reads, cf_dp)`.** The classifier works on **integer counts**
`(k = cf_alt_reads, n = cf_dp)` because the likelihood is binomial. Always derive these
from **AD** when present (`k = AD[alt]`, `n = AD[ref] + AD[alt]`); fall back to
`k = round(ab · dp)` only when AD is absent, and flag the site `approx_counts`.

**`father_state` derivation.** Father is germline, so its allele fraction clusters at
0 / 0.5 / 1. Prefer the GT; when GT is unreliable use AD:

```text
hom_ref  : gt in {0/0} OR (af_f < 0.10)
het      : gt in {0/1,1/0} OR (0.20 ≤ af_f ≤ 0.80 AND alt_reads_f ≥ 3)
hom_alt  : gt in {1/1} OR (af_f > 0.85)
missing  : father_dp < min_father_dp OR no coverage
```

A `missing` father is consequential: it makes category 1 (de novo) and category 7
(paternal-transmitted) indistinguishable, and makes category 8 unassessable. Such sites
are classified but flagged `father_no_coverage`.

---

## 2. Quality thresholds (configurable)

```python
@dataclass(slots=True)
class NiptQualityThresholds:
    min_cf_dp: int = 20          # cfDNA depth to trust a per-site VAF
    min_cf_alt_reads: int = 3    # alt reads to call a site "present"
    min_qual: float = 20.0       # site QUAL floor
    min_vaf: float = 0.0         # presence VAF floor (caller-dependent)
    min_father_dp: int = 10      # father coverage to trust father_state
    min_father_qual: float = 20.0
```

These thresholds drive both the **quality filter** (Phase 3 orchestrator, with drop
counts) and the **site-selection** inside FF estimation. They are the knobs the analyst
adjusts; the funnel UI (total → failed_quality → failed_artifact → analysed) reports the
effect.

---

## 3. Fetal-fraction estimation

### 3.1 Site selection (category-7 sites)

The fetal fraction is read off **category-7 sites**: the mother is hom-ref, the father
carries the allele, and the variant is present in cfDNA — so the only alt signal is the
fetus's single obligately-inherited paternal allele, sitting at a clean **FF/2**, *for
both father-het and father-hom-alt* (the maternal allele is ref either way).

We cannot *observe* "mother hom-ref" directly (cfDNA is the mixture), so we select these
sites operationally: **father carries + cfDNA VAF is low**. A genuinely maternal variant
(categories 2–6) sits at ≥ `0.5 − FF/2`, far above the FF/2 cluster, so a low-VAF ceiling
cleanly isolates the FF/2 sites. Crucially, requiring **father carries** excludes
category-1 de novo and maternal-mosaicism sites (father hom-ref), which would otherwise
contaminate the estimate at the same FF/2 VAF.

Selection predicate for an FF site:

```text
is_autosomal
AND father_state in {het, hom_alt} AND father_dp ≥ min_father_dp AND father_qual ok
AND cf_present AND cf_dp ≥ min_cf_dp AND cf_alt_reads ≥ min_cf_alt_reads AND cf_qual ok
AND 0 < cf_vaf ≤ vaf_ceiling           # vaf_ceiling = 0.25 (FF never ≥ 50% ⇒ FF/2 < 0.25)
AND not in artifact list               # already removed upstream
```

`vaf_ceiling = 0.25` is safe: realistic FF (≈4–20%) gives FF/2 ≤ ~0.10, while the nearest
maternal band (category 2) is ≥ 0.375 even at an implausible FF = 0.25. With a ~5,000-gene
target, paternally-transmitted sites typically number in the hundreds to thousands.

### 3.2 Estimator and confidence

Two estimators, reported together:

- **Pooled (headline):** `p̂ = Σ cf_alt_reads / Σ cf_dp`, then `FF_pooled = 2 · p̂`.
  This is the depth-weighted MLE under a shared-`p` binomial model. Its CI is a **Wilson
  score interval** on `p̂` (pure-Python), scaled ×2.
- **Per-site median (robustness cross-check):** `FF_median = 2 · median(cf_vaf_i)`.
  Robust to a few outlier/residual-artifact sites. If `FF_pooled` and `FF_median` disagree
  by more than the CI half-width, flag `ff_estimator_disagreement` (suggests artifact
  contamination or a sub-population).

```text
Wilson 95% CI for proportion p̂ from x successes in N trials (z = 1.96):
  centre = (p̂ + z²/2N) / (1 + z²/N)
  half   = z/(1 + z²/N) · sqrt( p̂(1−p̂)/N + z²/4N² )
  CI(p)  = centre ± half        →  CI(FF) = 2 · CI(p)
```

**Trust gating** on the estimate:

- `n_sites < min_sites` (default 30) → `low_confidence = True` (still report if
  `n_sites ≥ hard_floor`, default 5; below that `ff_computed = None`).
- CI half-width on FF wider than `max_ci_halfwidth` (default 0.03) → `low_confidence`.

### 3.3 External-FF reconciliation

```text
ff_computed   = FF_pooled (or None if too few sites)
ff_external   = provided value or None
disagreement  = ff_external is not None
                AND |ff_external − ff_computed| > max(disagreement_tol, ci_halfwidth)
ff (used)     = ff_external if prefer_external else (ff_computed ?? ff_external)
```

The **computed estimate stays the default**; an external value is recorded and surfaced
beside it with a disagreement flag rather than silently overriding. `disagreement_tol`
default 0.03 (3 absolute FF points).

### 3.4 Signature

```python
def estimate_fetal_fraction(
    sites: Iterable[NiptSiteObservation],
    qc: NiptQualityThresholds,
    *,
    external_ff: float | None = None,
    vaf_ceiling: float = 0.25,
    min_sites: int = 30,
    hard_floor: int = 5,
    max_ci_halfwidth: float = 0.03,
    disagreement_tol: float = 0.03,
    prefer_external: bool = False,
) -> "FetalFractionEstimate": ...

@dataclass(slots=True)
class FetalFractionEstimate:
    ff: float                  # value used downstream
    ff_computed: float | None  # category-7 pooled estimate
    ff_external: float | None
    ff_median: float | None    # cross-check
    ci_low: float | None
    ci_high: float | None
    n_sites: int
    method: str                # 'category7_pooled' | 'external' | 'category7_pooled+external'
    low_confidence: bool
    disagreement: bool
```

---

## 4. Per-variant classification

### 4.1 The likelihood model

Each category `j` has a fixed expected VAF `p_j(FF)` (from the
[main spec table](monogenic-nipt.md#the-classification-maths)):

| Cat | p_j(FF) | Requires |
| --- | --- | --- |
| 1 (de novo) | FF/2 | father hom-ref, present |
| 2 | 0.5 − FF/2 | present |
| 3 | 0.5 | present |
| 4 | 0.5 + FF/2 | present |
| 5 | 1 − FF/2 | present |
| 6 | 1.0 | present |
| 7 (paternal) | FF/2 | father carries, present |
| 8 (false-neg) | (FF/2 expected) | father hom-alt, **absent** |

Score each candidate with a **beta-binomial** log-likelihood, **not** a plain binomial.
At high depth a binomial draws razor-thin, unsupportable distinctions between
`p_2 = 0.5 − FF/2` and `p_3 = 0.5`; the beta-binomial's overdispersion `ρ` reflects real
sequencing noise and keeps confidence honest. `ρ → 0` recovers the binomial.

```text
Beta-binomial(k | n, μ, ρ):
  s = (1 − ρ)/ρ ;  α = μ·s ;  β = (1 − μ)·s
  logP = lgamma(n+1) − lgamma(k+1) − lgamma(n−k+1)
       + lgamma(k+α) + lgamma(n−k+β) − lgamma(n+α+β)
       + lgamma(α+β) − lgamma(α) − lgamma(β)
```

Clamp each `μ = p_j` into `[ε, 1−ε]` (ε ≈ 1e-4) so categories at 0.0/1.0 stay finite.
Default `ρ ≈ 0.005` (configurable).

### 4.2 Candidate sets

The father genotype and presence prune the candidates — this is what makes the otherwise
degenerate `p_1 = p_7 = FF/2` separable:

```text
present & father hom_ref  → {1, 2, 3, 4, 5, 6}     # de novo OR maternal (father doesn't carry)
present & father carries  → {2, 3, 4, 5, 6, 7}     # maternal OR (mother hom-ref ⇒ paternal=cat7)
present & father missing  → {1, 2, 3, 4, 5, 6, 7}  # cannot separate de novo vs paternal → flag
absent  & father hom_alt  → {8} or undetectable     # see §4.4
absent  & father het      → 'paternal_not_transmitted' (legitimate absence, category None)
absent  & otherwise       → category None
```

### 4.3 Assignment, prior, confidence

```text
for each candidate j:  LL_j = log_betabinom(k, n, μ=clamp(p_j(FF)), ρ) + log_prior_j
posterior_j = softmax(LL_j) over candidates
category*    = argmax posterior
confidence   = posterior[category*]          # also report runner-up + its posterior
```

- **Prior.** Default near-flat, with a **down-weighted category 1** (de novo is rare), so
  a de novo call must clear a real evidence bar. In addition, gate category 1 explicitly:
  require father confidently hom-ref *with coverage*, `cf_alt_reads ≥ min_cf_alt_reads`,
  and `cf_vaf` within the FF CI of `FF/2`; otherwise demote to noise/undetermined.
- **Confidence.** A call is `high_confidence` when `posterior[category*] ≥ min_separation`
  (default 0.90) **and** depth is adequate **and** FF is not flagged `ff_too_low`.

### 4.4 Absence and the false-negative (category 8)

Absence is only meaningful when detection was *expected*. The expected alt-read count for
a fetal-only allele is `E = cf_dp · FF/2`:

```text
absent & father hom_alt:
    if cf_dp ≥ min_cf_dp and E ≥ detect_min (≈3):  category 8  (false_negative)
    elif cf_dp < min_cf_dp:                          None, flag 'low_depth_dropout'
    else (E < detect_min):                           None, flag 'undetectable_at_ff'
```

So a hom-alt-father site missing from cfDNA is a **true QC failure** only when FF and
depth made it detectable; otherwise it is honestly "couldn't have seen it."

### 4.5 Output and the maternal/fetal decomposition

The category is decomposed into the two clinically-actionable axes, reported separately
because they have **very different reliability** (see §5):

```python
@dataclass(slots=True)
class NiptClassification:
    variant_id: str
    category: int | None
    category_label: str
    maternal_state: str        # 'hom_ref' | 'het' | 'hom' | 'absent' | 'unknown'
    fetal_inheritance: str     # 'de_novo' | 'paternal_transmitted' |
                               # 'paternal_not_transmitted' | 'maternal_inherited_het' |
                               # 'maternal_inherited_hom' | 'maternal_not_inherited' |
                               # 'shared_hom' | 'unknown'
    expected_vaf: float
    observed_vaf: float | None
    confidence: float          # posterior of chosen category
    runner_up_category: int | None
    runner_up_confidence: float | None
    flags: list[str]

def classify_site(
    site: NiptSiteObservation,
    ff_estimate: "FetalFractionEstimate",
    qc: NiptQualityThresholds,
    *,
    overdispersion: float = 0.005,
    min_separation: float = 0.90,
    detect_min: int = 3,
    ff_too_low: float = 0.01,
) -> NiptClassification: ...
```

Category → axes mapping: `1→(absent, de_novo)`, `2→(het, maternal_not_inherited)`,
`3→(het, maternal_inherited_het)`, `4→(het, maternal_inherited_hom)`,
`5→(hom, paternal? — het fetus)`/`6→(hom, shared_hom)`, `7→(hom_ref, paternal_transmitted)`,
`8→(hom_ref, paternal_not_transmitted + false_negative flag)`.

---

## 5. The honest part: what is and isn't resolvable

As `FF → 0` the fetal contribution is a vanishing perturbation on the maternal genotype,
so the band centres collapse:

| FF | cat1/7 | cat2 | cat3 | cat4 | cat5 | cat6 |
| --- | --- | --- | --- | --- | --- | --- |
| 40% | 0.20 | 0.30 | 0.50 | 0.70 | 0.80 | 1.00 |
| 10% | 0.05 | 0.45 | 0.50 | 0.55 | 0.95 | 1.00 |
| 4% | 0.02 | 0.48 | 0.50 | 0.52 | 0.98 | 1.00 |

Distinguishing **whether the fetus inherited a *maternal* allele** (cat 2 vs 3 vs 4)
requires resolving a `±FF/2` shift around 0.5, i.e. depth on the order of `1/FF²`
(≈ hundreds of reads at FF = 4%). Therefore the module reports two tiers of reliability,
and the UI/clinical filters must respect them:

- **Robust regardless of FF/depth:** de novo (cat 1), paternal transmission (cat 7
  present vs absent), and the coarse **maternal carrier state** (low VAF / ~0.5 band /
  ~1.0 band → hom-ref / het / hom). These are the high-value, dependable signals.
- **FF- and depth-limited:** the **fetal inheritance of a maternal allele** (cat 2 vs 3
  vs 4, and cat 5 vs 6). Below adequate depth or `ff_too_low`, `classify_site` returns the
  maternal_state but sets `fetal_inheritance = 'unknown'` and flags `ff_too_low` /
  `insufficient_depth_for_maternal_phasing` rather than guessing.

This split is what makes the recessive workflow trustworthy: the **paternal** allele's
fetal inheritance (via cat 7) is robust, and the **maternal** allele's inheritance
(cat 2 vs 3/4) is reported with explicit confidence so an at-risk call is never asserted
on noise.

---

## 6. Edge cases (must be covered by tests)

| Case | Handling |
| --- | --- |
| FF below `ff_too_low` (≈1%) | maternal_state only; `fetal_inheritance='unknown'`; flag `ff_too_low` |
| Very high cfDNA depth | beta-binomial `ρ` prevents overconfident cat2/cat3/cat4 splits |
| Low cfDNA depth | wide likelihoods → low confidence, flag `low_depth` |
| Father no coverage (`missing`) | cat 1 vs 7 ambiguous; classify with both candidates, flag `father_no_coverage`; cat 8 not assessable |
| Absent but undetectable (`E < detect_min`) | category None, flag `undetectable_at_ff` (not a false negative) |
| Multi-allelic site | v1: take max-AD alt, flag `multiallelic`; document as limitation |
| Indel / low-complexity | classify but flag `indel` (VAF less reliable) |
| Local CNV / aneuploidy at locus | breaks the `m,f ∈ {0,½,1}` dosage assumption — **out of scope**, documented limitation |
| Sex chromosomes | v1: excluded from FF and classification, flag `sex_chromosome_unsupported` (fetal sex unknown, X/Y dosage differs); future: infer fetal sex from chrY/chrX read ratio + FF, then handle |
| AD absent (only AB/AF) | `k = round(ab·dp)`, flag `approx_counts` |
| Residual artifact at FF/2 | mitigated by artifact filter upstream + `ff_estimator_disagreement` cross-check |

---

## 7. Orchestrator and result

```python
@dataclass(slots=True)
class NiptAnalysisResult:
    fetal_fraction: FetalFractionEstimate
    category_counts: dict[int, int]         # {1..8: count}
    filter_counts: dict[str, int]           # total_in, passed, failed_quality, failed_artifact
    classifications: list[NiptClassification]

def run_nipt_analysis(
    sites: Iterable[NiptSiteObservation],
    qc: NiptQualityThresholds,
    *,
    artifact_lookup: "Callable[[str], bool]",   # variant_id → is_artifact (assay-scoped)
    external_ff: float | None = None,
) -> NiptAnalysisResult: ...
```

Flow: count `total_in`; drop+count `failed_quality` (thresholds in `qc`) and
`failed_artifact` (`artifact_lookup`); `estimate_fetal_fraction` over survivors; classify
each survivor; tally `category_counts`. The orchestrator is the only part touching
ClickHouse (Phase 5 wires `sites` from the `entries` read helpers and `artifact_lookup`
from the `nipt_artifact_variants` table); the two pure functions stay I/O-free.

---

## 8. Worked sanity checks (FF = 10%, ρ = 0.005)

- Site `k=6, n=120` (VAF 0.05), father het → candidate set {2,3,4,5,6,7}; `p_7 = 0.05`
  dominates → **category 7** (paternal transmitted), high confidence.
- Site `k=60, n=120` (VAF 0.50), father hom-ref → {1..6}; `p_3 = 0.50` → **category 3**
  (het mother, het fetus); cat 2 (0.45) and cat 4 (0.55) are the runners-up — at n=120
  their posteriors are non-trivial, so `confidence` is moderate and the maternal-phasing
  flag may fire. At `n=1500` the call sharpens to high confidence.
- Site `k=2, n=140` (VAF ~0.014), father hom-ref → cat-1 gate: VAF within CI of FF/2=0.05?
  borderline-low → likely demoted to `undetermined`/noise unless alt reads/CI support it.
- Site absent, father hom-alt, `n=120`, `E = 120·0.05 = 6 ≥ 3` → **category 8**
  (false negative). Same site at `n=30` → `E = 1.5 < 3` → `undetectable_at_ff`, not a FN.

---

## 9. Test plan (Phase 3 deliverable)

Pure-function tests against **synthetic site lists** (no DB):

1. **FF recovery** — generate sites at known FF ∈ {2,4,10,20,40}% with binomial sampling
   at varied depth; assert `ff_computed` within CI of truth; assert `low_confidence` fires
   when sites are few/shallow.
2. **External reconciliation** — agreeing and disagreeing external FF set/clear the flag.
3. **Per-category assignment** — simulate each category's VAF at adequate depth; assert
   correct `category` and decomposition; confirm cat 1 vs 7 split tracks father_state.
4. **Confidence honesty** — low FF + low depth around 0.5 yields `fetal_inheritance =
   'unknown'`, not a forced cat2/3/4; high depth resolves it.
5. **Absence logic** — cat 8 only when `E ≥ detect_min`; otherwise `undetectable_at_ff`.
6. **Edge flags** — father_no_coverage, multiallelic, sex chromosome, approx_counts.
7. **Filter counts** — quality + artifact drops are counted and sum to `total_in`.

---

## Related documentation

- [Monogenic NIPT Analysis](monogenic-nipt.md) — feature overview, data model, workplan.
- [ACMG Classification](acmg-classification.md) — sibling points/scoring model, for style.
