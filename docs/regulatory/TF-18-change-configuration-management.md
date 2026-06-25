# TF-18 — Change & Configuration Management

| Field | Value |
| --- | --- |
| Document ID | TF-18 |
| Version | v0.1 DRAFT |
| Status | Draft for internal review |
| Owner | ‹CMGG software lead + quality› |
| Approver | ‹Lab director› |
| Date | 2026-06-25 |
| Basis | IEC 62304 §6 (maintenance) & §8 (configuration management); **IVDR Article 5(5)(h)** (devices produced per the documentation) |

> Article 5(5)(h) requires CMGG to ensure CoGA is **manufactured in accordance with its
> documentation**. For software that means controlled configuration, controlled change, and a
> defined rule for **when a change requires re-verification, re-validation, or an updated
> declaration**.

---

## 1. Configuration items (what is under control)
- **Source code** — Git repository; releases are tagged; every clinical build maps to a commit hash.
- **Dependencies** — `backend/requirements.txt` (pin all — see TF-08 open item), `frontend/package-lock.json`, container base-image digests.
- **Database schema & migrations** — versioned SQL migrations applied on startup.
- **Reference data & content** — assembly, ClinVar/gnomAD/dbNSFP/VEP/etc. releases (versioned via the manifest), gene panels and their source version, NIPT artifact lists, ACMG criterion-positioning rules.
- **Configuration/secrets** — environment settings (secrets in a manager, not in VCS).
- **Documentation** — this technical file and the per-feature design docs.

## 2. Version identification
- A single **device version identifier** (semantic version + git commit hash) identifies the released software; it is shown in-app and in every report footer (the UDI-DI-equivalent for this in-house device). **🔲 INPUT NEEDED:** finalize the scheme and where reference-data versions attach to it.
- Each signed report already embeds the device + reference-data versions (content-hashed) — this is the per-case configuration record.

## 3. Change-control workflow
```
Change request → impact analysis → significance assessment → implement (branch)
   → CI gates + review (TF-09) → risk review (TF-06) → re-verify / re-validate (if triggered)
   → release approval (lab director) → release record → deploy → docs/RTM/SBOM updated
```

## 4. Significance assessment (the key rule)
For each change, classify and act:

| Change type | Examples | Required actions |
| --- | --- | --- |
| **Non-significant** | Cosmetic UI, docs, internal refactor with no behavior change | CI + review; release record. |
| **Functional, non-safety** | New non-clinical view, performance optimization | CI + review; affected-requirement re-verification (TF-09). |
| **Safety/performance-affecting** | Change to a classifier, filter, FF estimator, haplotype/embryo-call logic, SV/aneuploidy thresholds | Risk review (TF-06); **targeted re-validation** of the affected application (TF-10) before clinical release. |
| **Reference-data/content update** | New ClinVar/gnomAD/panel release | Version-pinned via manifest; drift detection runs; assess whether validated scope still holds; record validated versions. |
| **Intended-purpose / scope change** | New application, new panel/assay/assembly, changed claim | Update TF-01/TF-02; re-run/extend performance evaluation; **update the Declaration (TF-04) and equivalence (TF-05)**; re-assess GSPR (TF-03). |
| **Security-affecting** | Auth/crypto/dependency-CVE | TF-13 process; security re-verification. |

> Rule of thumb: a change that could alter a **clinical output** or the **validated scope**
> cannot reach clinical use without the corresponding re-validation and document update.

## 5. Release & deployment
- Releases are built from a tagged commit with pinned dependencies (reproducible build).
- The **release verification checklist** (TF-09 §6) must be complete and signed.
- Deployment to the clinical environment is controlled; the running version is verifiable in-app.
- Rollback: the prior tagged release is retained; signed reports are reproducible from their frozen snapshots regardless of the deployed version.

## 6. Branch protection (enforcement gap)
**🔲 ACTION:** enforce the CI gates (`backend`, `smoke`, `frontend`) as **required status
checks** on `main` so no change merges without passing them (also flagged in TF-09 and
[security-posture.md §5](../security-posture.md)). Until enforced, the gates are advisory.

## 7. Records
Change requests, impact/significance assessments, review and CI evidence, re-validation
results, release records, and configuration baselines are retained per the CMGG QMS and
available to FAMHP on request (Art. 5(5)(e),(h)).
