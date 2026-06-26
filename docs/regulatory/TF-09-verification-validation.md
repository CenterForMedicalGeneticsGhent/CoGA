# TF-09 — Software Verification & Validation Plan & Requirements Traceability

| Field | Value |
| --- | --- |
| Document ID | TF-09 |
| Version | v0.1 DRAFT |
| Status | Draft for internal review |
| Owner | ‹CMGG software lead› |
| Approver | ‹Lab director› |
| Date | 2026-06-25 |
| Standards | IEC 62304 §5.5–5.7, §5.1.6 (traceability); IVDR Annex I §16.1 |

> Defines how CoGA is **verified** (built right: requirements → design → code → tests) and
> **validated** (right product: meets clinical need). Verification is largely operational
> via the test suites and CI; validation is covered by the performance evaluation
> ([TF-10](TF-10-performance-evaluation-plan.md)) and usability validation ([TF-12](TF-12-usability.md)).
>
> **In CMGG QMS terms (H11.1-OP5):** this document is the **bio-IT ingangsvalidatie** of the
> software — the entry validation done at first use, with acceptance criteria, test results
> and conclusion, captured on template **H11.1-F12.2** as report **`VAL-Sxxxx`**, and
> embedding the risk analysis ([TF-06](TF-06-risk-management-plan.md)). It is distinct from
> the **clinical validation per analysis/method** (H11.1-OP1 §8), which is
> [TF-10](TF-10-performance-evaluation-plan.md)/[TF-11](TF-11-performance-evaluation-report.md).
> Acceptance testing uses **real data in an environment closely matching production**.

---

## 1. Verification strategy & levels

| Level | Method | Where | Gate |
| --- | --- | --- | --- |
| Unit | pytest (backend), vitest (frontend) | `backend/tests`, `frontend/src/**/*.test.tsx` | CI `backend`, `frontend` jobs |
| Static analysis | TypeScript `tsc`, ESLint | frontend | CI `frontend` job |
| Integration | Real-startup smoke against Postgres 16 + ClickHouse 25.3 (schema init, admin seed, health probe) | `backend/tests/integration` | CI `smoke` job |
| System / clinical | Concordance vs validated assays | [TF-10](TF-10-performance-evaluation-plan.md) | Performance report TF-11 |
| Regression | Full suite re-run on every PR & push to main | CI | Required checks |

**CI enforcement:** the gates in `.github/workflows/ci.yml` run on every PR and on push to
`main`. **🔲 ACTION:** mark `backend`, `smoke`, and `frontend` as **required status checks**
in branch protection (a GitHub setting, not in the workflow file) so they must pass before
merge — without this, the gates are advisory. (Noted as open in [security-posture.md §5](../security-posture.md).)

**Test level ↔ version level (H11.1-OP5 §4.4.6).** The depth of testing required for a change
is tied to its semantic-version level ([TF-18](TF-18-change-configuration-management.md)):
**patch** focuses on system tests confirming existing functionality is unaffected; **minor**
verifies new *and* existing functionality (incl. integration tests); **major** requires
thorough testing across all levels plus clinical opvolgvalidatie.

## 2. Validation strategy

- **Clinical/analytical validation:** concordance against validated comparator assays per application — 50 BeGECS couples, 100 PGT embryos, 30 WGS trios, 30 monogenic NIPT samples ([TF-10](TF-10-performance-evaluation-plan.md)); results in [TF-11](TF-11-performance-evaluation-report.md).
- **Usability validation:** summative evaluation that intended users can use CoGA without unacceptable use error ([TF-12](TF-12-usability.md)).
- **Reproducibility validation:** same validated input → identical content-hashed signed report (a 62304 §16.1 repeatability requirement; mechanism exists via the frozen sign-out).

## 3. Software Requirements Specification (SRS)

The SRS is maintained as the controlled companion document
**[TF-09a — Software Requirements Specification](TF-09a-software-requirements-specification.md)**:
71 requirements with stable IDs across 13 areas (functional per application, performance,
interface/input, risk-control, security, usability, reporting), each with a 62304 safety class
and a link to its TF-06 hazard. It is derived from the per-feature design docs and the
implementation/test inventory, and revised under change control (TF-18).

## 4. Requirements traceability matrix (RTM)

The RTM — the spine 62304/IVDR expect — is maintained as the controlled companion document
**[TF-09b — Requirements Traceability Matrix](TF-09b-requirements-traceability-matrix.md)**:
each SRS requirement traced forward to implementation (`file::function`), verifying test(s),
and back to its hazard, with an honest status (✅ directly verified · ◐ partial / clinically
validated in TF-10 · ⚠ verification gap). TF-09b §3 lists the verification gaps as a CAPA
backlog that must be closed before the first clinical release (see §6 below).

## 5. Anomaly handling

Defects found in verification or in the field are recorded, risk-assessed (could it affect a
clinical result? → severity per TF-06), fixed under change control (TF-18), regression-tested,
and — where clinically relevant — fed to vigilance/CAPA (TF-17). The append-only clinical
audit trail aids reconstruction of any affected case.

## 6. Release verification checklist (per clinical release)

- [ ] All CI gates green (backend, smoke, frontend) on the release commit.
- [ ] RTM updated; no requirement without a passing verifying test.
- [ ] Risk file (TF-06) reviewed for new/affected hazards; controls verified.
- [ ] SOUP register / SBOM (TF-08/TF-13) reconciled; no unaddressed high-severity vuln.
- [ ] Change-significance assessed (TF-18); re-validation run if triggered (TF-10).
- [ ] Version/build identifier updated and visible in the report footer.
- [ ] Release record signed (TF-18); lab director authorization.
