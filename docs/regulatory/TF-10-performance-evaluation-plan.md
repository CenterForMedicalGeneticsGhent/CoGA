# TF-10 — Performance Evaluation Plan

| Field | Value |
| --- | --- |
| Document ID | TF-10 |
| Version | v0.1 DRAFT |
| Status | Draft for internal review |
| Owner | ‹Clinical lead per application + software lead› |
| Approver | ‹Lab director› |
| Date | 2026-06-25 |
| Basis | IVDR (EU) 2017/746 **Annex XIII Part A**; MDCG 2020-1 (clinical evaluation of MDSW) |

> Performance of a software-only interpretive device is established along the three IVDR
> pillars — **scientific validity, analytical performance, clinical performance** — adapted
> to the fact that CoGA produces *interpretation/decision support*, not a measured analyte.
> The core method is **concordance of CoGA's outputs against CMGG's already-validated,
> accredited reference assays** (the comparator/predicate methods), on defined validation
> sample sets, per clinical application. The resulting evidence is reported in
> [TF-11 Performance Evaluation Report](TF-11-performance-evaluation-report.md).

---

## 1. Performance evaluation strategy

| Pillar | For CoGA this means | Evidence |
| --- | --- | --- |
| **Scientific validity** | The association of the variants/results CoGA surfaces with the clinical conditions is established by the scientific community (ACMG/AMP 2015, ClinGen, gnomAD, ClinVar, GenCC, established inheritance genetics) — CoGA applies, not invents, these associations. | Literature & database references; this is **not** re-established empirically. |
| **Analytical performance** | Does CoGA correctly *process and present* its inputs and correctly *derive* its outputs? Concordance of CoGA's variant lists, classifications, and derived calls against the validated comparator; reproducibility/repeatability. | This plan §3–§4; TF-09 software V&V. |
| **Clinical performance** | Does CoGA's *final, signed-out clinical conclusion* agree with the validated assay's clinical conclusion on real cases? | This plan §3 concordance studies (the validation cases). |

Because the upstream wet-lab and bioinformatics workflows are separately validated and
accredited, this evaluation isolates **CoGA's contribution**: given the same validated
inputs, does CoGA lead the analyst to the same clinical conclusion as the established assay?

## 2. Validation design (overview)

**Method:** retrospective/prospective **concordance study** per application. For each
validation case, the established (already-validated, accredited) assay/result is the
**comparator ("truth")**; the case is independently analysed in CoGA by a qualified
analyst following the intended workflow, and CoGA's outcome is compared to the comparator.

**Validation sample matrix (as specified by CMGG):**

| Application | Validation set | N | Comparator ("truth") |
| --- | --- | --- | --- |
| Expanded carrier screening (BeGECS, long-read) | **BeGECS couples** | **50 couples** | Validated/accredited BeGECS carrier-screening result |
| PGT (shallow WGS) | **PGT embryos** | **100 embryos** | Validated PGT result (‹SNP-array / current PGT-M/-A/-SR method›) and/or confirmatory testing |
| Rare-disorder diagnostics (long-read) | **WGS trios** | **30 trios** | Validated diagnostic NGS result / established clinical conclusion |
| Monogenic NIPT | **Monogenic NIPT samples** | **30 samples** | Validated comparator (‹invasive confirmatory genotype / established NIPT result / known fetal genotype›) |

> **🔲 INPUT NEEDED (per application):** name the exact comparator method, define
> the unit of analysis and the "truth" source, and set the **acceptance criteria** (the
> §3 tables propose defaults to confirm). Also confirm prospective vs retrospective,
> case selection (consecutive vs enriched for positives), and that positive/at-risk cases
> are sufficiently represented to power agreement on the clinically critical calls.

**Statistics:** report agreement as **PPA** (positive percent agreement), **NPA**,
**OPA** (overall percent agreement), and **Cohen's κ** where applicable, each with **95%
confidence intervals** (Clopper–Pearson / Wilson). All **discordances are adjudicated** and
root-caused (CoGA error · comparator error · upstream-input difference · genuine
interpretive disagreement). Enrichment for positive/at-risk cases is documented and its
effect on agreement estimates noted.

## 3. Per-application performance protocols

### 3.1 Expanded carrier screening — BeGECS (50 couples)
- **Unit of analysis:** per-variant carrier calls and the **couple-level at-risk** conclusion (both partners carrying a variant in the same recessive gene / X-linked finding).
- **Inputs:** validated long-read annotated VCFs over the BeGECS gene set; CoGA carrier-screening workflow.
- **Metrics:** variant-level PPA/NPA/OPA of carrier calls vs comparator; couple-level at-risk concordance (the clinically actionable output); concordance of reported ACMG class for reportable variants.
- **Proposed acceptance (confirm):** ≥99% OPA on carrier variant detection; **100% agreement on couple-level at-risk conclusions** (any discordance investigated and resolved); all clinically reportable (P/LP) carrier variants concordant.
- **Edge cases:** technically difficult genes/regions on long-read; pseudogene/Paraphase-relevant loci; CNV/SV-mediated carrier findings.

### 3.2 PGT (100 embryos)
- **Units of analysis:** per-embryo **ROI segregation call** (affected/at-risk · carrier · unaffected · uninformative); **direct mutation** genotype; **aneuploidy** status; **large (>10 Mb) SV** status.
- **Inputs:** shallow-WGS per-embryo and family VCFs, phased/imputed markers, segment/CN/APCD tracks, pedigree (incl. single-parent/donor).
- **Metrics:**
  - Haplotype segregation: concordance of per-embryo call vs comparator (and vs born-child/confirmatory outcome where available); rate and handling of **uninformative** calls.
  - Direct mutation detection: PPA/NPA vs comparator genotype.
  - Aneuploidy: per-chromosome PPA/NPA/OPA vs comparator; **resolution/limit-of-detection claim to define**.
  - Large SV: detection concordance at the **≥10 Mb** claimed threshold; characterize the size/type detection limit.
- **Proposed acceptance (confirm):** 100% concordance on **informative** embryo segregation calls; no **false "unaffected"** on truly at-risk embryos (the safety-critical error); aneuploidy and >10 Mb SV concordance ≥‹threshold›.
- **Edge cases:** recombination near the ROI, sparse informative markers, donor/single-parent families (expected "uninformative" for recessive — verify safe behavior), mosaic embryos, sex chromosomes.

### 3.3 Rare-disorder diagnostics — WGS trios (30 trios)
- **Unit of analysis:** the **diagnostic conclusion** (causal/candidate variant(s) identified and their ACMG class) and the set of reported variants.
- **Inputs:** comprehensive long-read trio data: SNV/indel, SV, repeat expansions (TRGT), Paraphase, mtDNA; HPO; pedigree.
- **Metrics:** concordance of the reported causal/candidate variant(s) with the established diagnosis; PPA for known causal variants across **each data type** (SNV/indel, SV, repeat, Paraphase, mtDNA); ACMG-class concordance; de novo / inheritance-mode concordance via the trio logic.
- **Proposed acceptance (confirm):** 100% detection of the known causal variant(s) among CoGA candidates for previously-solved trios; ACMG class within one tier and same actionability; correct inheritance/de-novo assignment.
- **Edge cases:** each non-SNV data type represented; compound-het (SNV+SV second hit); repeat-expansion and Paraphase-resolved loci; mtDNA heteroplasmy.

### 3.4 Monogenic NIPT (30 samples)
- **Units of analysis:** **fetal-fraction estimate** (quantitative QC, vs comparator/known FF); **per-variant zygosity category**; and the **inheritance-preset conclusions** (de novo, paternal/maternal dominant, recessive at-risk).
- **Inputs:** combined two-sample (paternal + cfDNA) annotated VCFs, coverage, pedigree; external FF where available.
- **Metrics:**
  - FF: bias and correlation (Pearson/Deming, Bland–Altman) of CoGA's cat-7 estimate vs comparator FF; agreement with external FF (disagreement-flag behavior).
  - Category assignment & inheritance calls: PPA/NPA/OPA vs the confirmed fetal genotype/comparator; **false-negative rate** (category-8 dropout behavior).
- **Proposed acceptance (confirm):** FF within ‹±X absolute / ±Y%› of comparator; **no missed at-risk fetal calls** (false-negative is the safety-critical error for a screening test); category concordance ≥‹threshold› at adequate FF/coverage; correct low-confidence behavior at low FF/depth (no forced calls).
- **Edge cases:** low fetal fraction, low depth, category-8 dropout, FF disagreement with external estimate.

## 4. Reproducibility, robustness & cross-cutting checks
- **Reproducibility/repeatability:** same validated input → identical signed report (content-hash equality); re-analysis by a second analyst (inter-operator) on a subset.
- **Robustness:** behavior on degraded inputs (low coverage, missing tracks, malformed VCF) — should fail safe / warn, not silently mis-call.
- **Analytical baseline (optional, recommended):** for SNV/indel handling, a concordance run against a reference material (e.g. **GIAB / Coriell / GeT-RM**) processed through the validated upstream pipeline, to characterize CoGA's variant-handling independently of case-mix.
- **Software V&V cross-reference:** unit/integration/system tests and requirements traceability are in [TF-09](TF-09-verification-validation.md); this plan covers the *clinical/analytical concordance* layer above them.

## 5. Acceptance, discordance handling & reporting
- A study **passes** when every application meets its confirmed acceptance criteria and all discordances are adjudicated with documented root cause and (where a CoGA defect) a fix + re-test.
- Safety-critical errors (false-negative at-risk/affected calls in NIPT/PGT/carrier; missed causal variant in diagnostics) trigger **failure** and a CAPA, regardless of aggregate concordance.
- Results, stratified analyses, CIs, discordance adjudication, limitations, and the
  resulting **claimed performance** and **validated scope** (panels, assays, assemblies,
  populations) are documented in [TF-11](TF-11-performance-evaluation-report.md) and feed
  the IFU (TF-15), the GSPR §9.1 line (TF-03), and the residual-risk review (TF-06).

## 6. Post-market performance follow-up (PMPF)
Ongoing concordance monitoring, drift events, and any new edge cases observed in clinical
use feed back per [TF-16 PMS](TF-16-post-market-surveillance-plan.md); the validated scope
is re-confirmed on material change (new panel, assay, assembly, or algorithm version) via
TF-18 change control, which defines when re-validation is required.
