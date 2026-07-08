# Semi-automatic ACMG Classification

CoGA provides a guided ACMG/AMP (2015) classifier for small variants. From any
variant card or table row, **ACMG classify** opens a modal that pre-evaluates the
ACMG criteria from data already available, lets the analyst confirm/adjust each
one, and scores them on a green→red points scale.

This document is the canonical reference for **how each criterion is
auto-positioned** ("pre-check" / exclusion rules). It complements the in-app user
guide (`/docs` → *Semi-automatic ACMG classification*).

> **Decision support, not an autoclassifier.** Every criterion is overridable.
> Suggestions are pre-positioned from the data; the analyst confirms strengths,
> adds a rationale note, and saves. The final class and points are **recomputed on
> the server** on save, so a stored classification never depends on the browser.

---

## Scoring model

Scoring uses the Tavtigian/ClinGen Bayesian **points** system. Each *applied*
criterion contributes points by its applied strength; benign criteria are
negative. The signed total maps onto the five ACMG classes.

| Strength             | Pathogenic | Benign |
| -------------------- | ---------: | -----: |
| Supporting (PP / BP) |        +1  |    −1  |
| Moderate (PM)        |        +2  |    −2  |
| Strong (PS / BS)     |        +4  |    −4  |
| Very strong (PVS1)   |        +8  |     —  |

**Class bands (point total):**

| Points       | Class                  | Tag           |
| ------------ | ---------------------- | ------------- |
| ≥ 10         | Pathogenic (class 5)   | `acmg_class_5`|
| 6 … 9        | Likely Pathogenic (4)  | `acmg_class_4`|
| 0 … 5        | VUS (class 3)          | `acmg_class_3`|
| −1 … −6      | Likely benign (2)      | `acmg_class_2`|
| ≤ −7         | Benign (class 1)       | `acmg_class_1`|

`BA1` (allele frequency ≥ 5%) is a **stand-alone override**: an applied BA1
classifies the variant Benign regardless of any other evidence.

On save the computed class is written to the variant's `classification` and the
matching `acmg_class_N` review tag (so cards and summaries reflect it), and the
full per-criterion blob is persisted for audit and reuse.

### VUS sub-tiers (hot / warm / cold)

Following the MAGI-ACMG approach, the VUS band (points 0–5) is split into three
tiers by proximity to the Likely-Pathogenic threshold (6):

| Points | VUS sub-tier | Tag             | Reading                                   |
| ------ | ------------ | --------------- | ----------------------------------------- |
| 4 … 5  | **Hot**      | `acmg_vus_hot`  | Leans pathogenic; chase more evidence.    |
| 2 … 3  | **Warm**     | `acmg_vus_warm` | Intermediate / mixed evidence.            |
| 0 … 1  | **Cold**     | `acmg_vus_cold` | Little pathogenic support.                |

The tier is computed alongside the class (frontend `score.vusTierForPoints`,
backend `acmg_points.vus_tier_for_points`, kept in parity) and is `null` for any
non-VUS class. It is shown as a chip on the scale bar and, on save, written back as
an `acmg_vus_<tier>` review tag next to `acmg_class_3` — so a "hot VUS" is
filterable through the ordinary review-tag pipeline. Reclassifying a variant out of
the VUS band clears the tier and its tag.

---

## Criterion states

Auto-evaluation positions each criterion into one of four states. **All states
are overridable** — clicking a criterion always toggles it.

| State | UI | Meaning |
| ----- | -- | ------- |
| **Applied** | checked, green | Data clearly supports it; pre-checked and counts toward the score. |
| **Consider** | ● amber, unchecked | A relevant but not decisive signal; confirm if appropriate. |
| **Argues against** | ✕ red, unchecked | Data points the other way (e.g. in-silico benign when looking at PP3). |
| **Not applicable** | greyed, struck-through | Cannot apply to this variant (type / frequency / family); greyed as a hint but still clickable. |

Hover any criterion to see the exact evidence string behind its state. Families
are laid out **benign-left → pathogenic-right** to mirror the scale bar.

---

## Pre-check rules (positive evidence)

Data sources: the `SmallVariant` record (consequence, gnomAD, in-silico, ClinVar),
the gene profile (`GET /genes/profile` → ClinGen dosage, GenCC inheritance,
gene–phenotype HPO), the family members + genotypes, and the proband's "present"
HPO annotations (`GET /families/{id}/hpo`).

| Criterion | State | Rule |
| --------- | ----- | ---- |
| **PVS1** | Applied (Very strong / Strong), else Consider | Predicted-null consequence: `stop_gained`, `frameshift_variant`, `splice_acceptor_variant`, `splice_donor_variant`, `start_lost`, `transcript_ablation`. **Very strong** when LOFTEE = `HC` **and** ClinGen haploinsufficiency = "Sufficient evidence"; **Strong** when the mechanism is otherwise supported; shown as **Consider** when the LOF disease mechanism is unconfirmed. |
| **PM2** | Applied (Supporting) | Absent from gnomAD, or allele frequency < 1×10⁻⁴. |
| **BA1** | Applied (Stand-alone) | gnomAD allele frequency ≥ 5%. Stand-alone benign override. |
| **BS1** | Applied (Strong) | gnomAD allele frequency ≥ 1% and < 5%. |
| **BS2** | Applied (Strong) / Consider | Homozygotes present in gnomAD. **Strong** when GenCC marks the gene recessive; otherwise **Consider**. |
| **PM4** | Consider (Moderate) | In-frame indel / stop-loss (`inframe_insertion`, `inframe_deletion`, `stop_lost`, `protein_altering_variant`). Confirm outside a repeat region. |
| **PP2** | Applied (Supporting) | Missense in a missense-constrained gene (gnomAD missense Z ≥ 3.09). |
| **PP3** | Applied (Supporting / Moderate / Strong) | REVEL ≥ 0.644 / 0.773 / 0.932 respectively; or SpliceAI max Δ ≥ 0.2 (Supporting) / ≥ 0.5 (Moderate); or AlphaMissense = likely pathogenic. Flags **BP4** as *argues against*. |
| **BP4** | Applied (Supporting / Moderate / Strong) | REVEL ≤ 0.290 / 0.183 / 0.016 respectively (with SpliceAI < 0.1); or AlphaMissense = likely benign. Flags **PP3** as *argues against*. |
| **BP7** | Applied (Supporting) | Synonymous variant with SpliceAI max Δ < 0.1 (no predicted splice impact). |
| **PP5** | Applied (Supporting) | ClinVar reports this exact variant pathogenic / likely pathogenic. Flags **BP6** *argues against*. |
| **BP6** | Applied (Supporting) | ClinVar reports this exact variant benign / likely benign. Flags **PP5** *argues against*. |
| **PP4** | Applied (Supporting / Moderate) | Phenotype specific for the gene. When a Monarch gene↔proband phenotype-match score is present (set by phenotype prioritisation), strength scales: ≥ 0.6 Moderate, ≥ 0.3 Supporting, below that not suggested. Without a score, falls back to a direct proband-HPO ∩ gene-HPO overlap at Supporting. Auto-capped at Moderate; raise to Strong manually for a highly specific single-gene phenotype. |
| **PM6** | Applied (Moderate) | Trio: variant present in the proband, absent in **both** sequenced parents (assumed de novo; parentage not molecularly confirmed — upgrade to PS2 manually if it is). |
| **PP1** | Consider (Supporting) | Variant carried by ≥ 2 affected family members (cosegregation). |
| **BS4** | Consider (Strong) | An affected relative does **not** carry the variant (lack of segregation). |

**REVEL → strength** thresholds follow the ClinGen Sequence Variant Interpretation
calibration (2022):

| Direction | Supporting | Moderate | Strong |
| --------- | ---------- | -------- | ------ |
| PP3 (≥)   | 0.644      | 0.773    | 0.932  |
| BP4 (≤)   | 0.290      | 0.183    | 0.016  |

---

## Exclusion rules (greyed as "not applicable")

Criteria that cannot apply to the variant in front of you are greyed out so the
working set stays honest. They remain clickable for manual override.

### By molecular consequence

| Consequence class | Greyed (not applicable) |
| ----------------- | ----------------------- |
| Missense | PVS1, PM4, BP3, BP7 |
| Loss-of-function | PP2, PM5, BP1, BP7, BP3 |
| Synonymous | PVS1, PM4, PP2, PM5, BP1, BP3 |
| In-frame / length-changing | PVS1, PP2, PM5, BP1, BP7 |
| Splice-region | PVS1, PP2, PM5, BP1, PM4 |

### By population frequency

Only the frequency criterion matching the observed gnomAD band stays active; the
others are greyed:

| Allele frequency | Active | Greyed |
| ---------------- | ------ | ------ |
| ≥ 5% | BA1 | PM2, BS1 |
| 1% … 5% | BS1 | BA1, PM2 |
| < 1×10⁻⁴ or absent | PM2 | BA1, BS1 |
| 1×10⁻⁴ … 1% (borderline) | — | BA1, BS1, PM2 |
| No homozygotes in gnomAD | — | BS2 |

### By in-silico availability

| Condition | Greyed |
| --------- | ------ |
| No REVEL / SpliceAI / AlphaMissense prediction | PP3, BP4 |

### By family / segregation

| Condition | Greyed |
| --------- | ------ |
| No complete trio (missing parental genotypes) | PS2, PM6 |
| Variant inherited from a parent | PS2, PM6 |
| No additional affected carrier | PP1 |
| No affected relative lacking the variant | BS4 |

---

## Not auto-evaluated (manual only)

These criteria need information CoGA does not hold and are always left for the
analyst:

- **PS1 / PM5** — same / different change at an amino-acid residue already
  established pathogenic. Requires a residue-level ClinVar index (not available;
  CoGA only stores the variant's own ClinVar significance).
- **PS3 / BS3** — functional studies.
- **PS4** — case–control prevalence / enrichment in affecteds.
- **PM1** — mutational hotspot / functional domain.
- **PM3 / BP2** — in-trans / in-cis phasing with a pathogenic variant.

---

## Mitochondrial (mtDNA) variants

Opening **ACMG classify** on a variant from the family **mtDNA analysis** routes
to a dedicated mt-specific evaluator (`frontend/src/lib/acmg/evaluateMito.ts`,
after the ClinGen/Wong–McCormick 2020 mtDNA specifications) instead of the nuclear
`evaluate.ts`. The selection is by `chr === 'MT'`; the points scale, the five
classes and the VUS sub-tiers are identical — only the pre-evaluation changes,
because mtDNA is haploid and maternally inherited and the nuclear in-silico
predictors are not computed for it.

| Criterion | mtDNA behaviour |
| --------- | --------------- |
| **PVS1** | Applies only to predicted-null changes in a **protein-coding** mt gene; `not_applicable` for tRNA / rRNA / control-region loci. |
| **PM2 / BS1 / BA1** | gnomAD-MT thresholds: `MT_BA1_AF = 0.005` (stand-alone), `MT_BS1_AF = 2e-4`, `MT_PM2_AF = 2e-5` / absent. A MITOMAP common polymorphism (or haplogroup marker) is routed to **BS1**. |
| **PP5 / BP6** | From MITOMAP / ClinVar `clinical_significance` (pathogenic → PP5; benign / polymorphism → BP6), mutually contraindicating. |
| **PP3 / BP4** | `not_applicable` — mt predictors (MitoTIP / APOGEE / HmtVar) are not yet loaded, so nothing is auto-applied. |
| **PM1** | `consider` (Moderate) for tRNA loci. |
| **PS2 / PM6** | `not_applicable` — maternally inherited, so de novo does not apply. |
| **PP1 / BS4** | Maternal segregation from the maternal-line calls + heteroplasmy/zygosity (≥ 2 affected maternal carriers → PP1; an affected relative lacking the variant → BS4). |
| **PP4** | Proband HPO ∩ gene HPO, noting the proband's heteroplasmy level. |
| Nuclear-only (PP2, PM5, PM3, PM4, BP1–3, BP7, BS2) | `not_applicable`. |

mt context (locus category, MITOMAP status, disorders, maternal transmission,
haplogroup, per-call heteroplasmy) is carried on `SmallVariant.mito`, populated by
the `toSmallVariantForAcmg` adapter in
`frontend/src/pages/families/FamilyMitoDNAAnalysisPage.tsx`.

---

## External evidence links

The modal header carries quick links for the variant:

- **gnomAD**, **ClinVar**, **DECIPHER** — same URLs as the variant card.
- **Smart PubMed** — `gene (OR protein change) AND ("HPO term 1" OR "HPO term 2" …)`
  built from the proband's present HPO terms, to check whether the gene–phenotype
  association has been published.

---

## Persistence (developer notes)

- Postgres schema `backend/db/schema/postgres/03_assay.sql` adds
  `acmg` (JSONB), `acmg_point_total` (INTEGER) and `acmg_class` (TEXT) to
  `small_variant_reviews`. **Apply it before the save path works end-to-end.**
- The save reuses `PUT /families/{family_id}/small-variants/{variant_id}/review`.
  The server validates criterion codes and **recomputes** `acmg_point_total` /
  `acmg_class` from the submitted criteria (`backend/app/services/acmg_points.py`,
  which mirrors the frontend scorer and is parity-tested). The recomputed blob also
  stores `vus_tier` (`acmg_points.vus_tier_for_points`).
- The VUS-tier tags (`acmg_vus_hot` / `acmg_vus_warm` / `acmg_vus_cold`) are system
  tags seeded from `DEFAULT_SMALL_VARIANT_TAGS` in
  `backend/app/services/small_variant_review_pg.py` — no migration needed. The modal
  manages them automatically alongside the `acmg_class_*` tags.
- Frontend engine: `frontend/src/lib/acmg/` (`criteria.ts`, `score.ts`,
  `evaluate.ts`, `evaluateMito.ts`, `index.ts`) — pure and unit-tested. UI:
  `frontend/src/pages/families/AcmgClassificationModal.tsx` +
  `AcmgScaleBar.tsx`.

### Scope

Family small-variants page **and** the family mtDNA analysis page (via the
mt-specific evaluator). The global Variant Explorer and structural variants share
the review payload type and are a straightforward follow-up.
