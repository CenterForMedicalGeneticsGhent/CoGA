# TF-07 — Software Development & Lifecycle Plan

| Field | Value |
| --- | --- |
| Document ID | TF-07 |
| Version | v0.1 DRAFT |
| Status | Draft for internal review |
| Owner | ‹CMGG software lead› |
| Approver | ‹Lab director› |
| Date | 2026-06-25 |
| Standards | IEC 62304:2006+A1:2015 (software lifecycle); IEC 82304-1 (health software product); supports IVDR Annex I §16.2 |

> Defines the lifecycle processes by which CoGA is developed, verified, released and
> maintained "in accordance with the state of the art" (IVDR Annex I §16.2). It documents
> the **existing engineering practice** of the project and the gaps to formalize.

---

## 1. Software safety classification (IEC 62304 §4.3)

| | |
| --- | --- |
| **Proposed class** | **Class C** — a software failure (e.g. a missed pathogenic variant, a wrong embryo segregation call, a wrong fetal-risk category) could, if not caught, contribute to a serious clinical decision (embryo transfer/discard, reproductive decision, missed diagnosis). |
| Justification | Per IEC 62304, classification reflects the *worst-case* harm if the software fails and external risk controls are insufficient. Although a qualified professional signs out every result (a strong control), professional review alone is not treated as sufficient to downgrade below C for the safety-critical calls (TF-06). |
| Effect | Class C requires the full set of 62304 development, architecture, detailed-design, integration, system-test, and maintenance activities, with documented traceability. **🔲 INPUT NEEDED:** confirm classification with CMGG quality; a documented decomposition could assign lower classes to non-safety items (e.g. cosmetic UI) if justified. |

## 2. Lifecycle model

CoGA uses an **iterative/incremental** model (feature branches → PR → CI gates → review →
merge → release), mapped onto the IEC 62304 processes below. The existing per-feature design
docs (e.g. [monogenic-nipt.md](../monogenic-nipt.md), [clinical-traceability.md](../clinical-traceability.md))
are the project's de-facto design records; this plan formalizes the structure around them.

| IEC 62304 process | How CoGA realizes it | Evidence / location |
| --- | --- | --- |
| 5.1 Development planning | This document; per-feature design docs | `docs/`, this file |
| 5.2 Requirements analysis | Software Requirements Spec (to formalize) + per-feature "clinical question" sections | TF-09 §SRS; `docs/*.md` |
| 5.3 Architectural design | [application-scheme.md](../application-scheme.md), [storage-architecture.md](../storage-architecture.md), [TF-02](TF-02-device-description.md) | `docs/` |
| 5.4 Detailed design | Per-feature design docs; code-level docstrings | `docs/`, source |
| 5.5 Implementation & unit verification | Python/TypeScript implementation + pytest/vitest unit tests | `backend/tests`, `frontend/src/**/*.test.tsx` |
| 5.6 Integration & integration testing | Smoke suite booting real Postgres+ClickHouse | `backend/tests/integration` |
| 5.7 System testing | Performance/concordance evaluation; end-to-end fixtures | [TF-10](TF-10-performance-evaluation-plan.md), TF-09 |
| 5.8 Release | Tagged version + build identifier; release checklist | TF-18 |
| 6 Maintenance | Bugfix/enhancement under same gates; change control | TF-18 |
| 7 Risk management | ISO 14971 process | [TF-06](TF-06-risk-management-plan.md) |
| 8 Configuration management | Git, pinned deps, migrations | TF-18, [TF-08](TF-08-soup-register.md) |
| 9 Problem resolution | Issue tracking + CAPA | [TF-17](TF-17-vigilance-capa.md) |

## 3. Roles & responsibilities

| Role | Responsibility |
| --- | --- |
| Software lead / developer(s) | Requirements, design, implementation, unit/integration tests, SOUP monitoring |
| Reviewer (independent) | Code review of every PR; verification that controls/tests exist |
| Clinical lead(s) | Clinical requirements, acceptance criteria, performance-evaluation oversight |
| Quality/RA | Lifecycle compliance, document control, risk file, release approval |
| Lab director | Release authorization, residual-risk acceptance |

**🔲 INPUT NEEDED:** name holders; confirm independence of review for Class C.

## 4. Development environment & tooling

- Languages/runtimes: Python 3.10 (backend), Node 20 / TypeScript 6 (frontend).
- Source control: Git/GitHub; feature branches; **branch protection with required status checks** (to be enforced — see TF-09 §CI).
- Build/packaging: Docker / Docker Compose; pinned `backend/requirements.txt`, `frontend/package-lock.json`.
- CI: GitHub Actions (`.github/workflows/ci.yml`) — backend pytest, real-startup smoke, frontend tsc+eslint+vitest.
- Tool validation: development tools (linters, test runners, CI) are not part of the device; their adequacy is evidenced by the gates they enforce. Compilers/build tools are configuration-controlled via pinned versions.

## 5. Deliverables per increment

For each change reaching a clinical release: updated requirements/design where affected,
implementation, unit + integration tests (green in CI), updated traceability (TF-09),
risk-file review (TF-06) when a new hazard or control is touched, and a release record (TF-18).

## 6. Maintenance & legacy

CoGA is an actively maintained product. Maintenance changes follow the same process and gates
as development; the change-control procedure (TF-18) determines, per change, whether
re-verification and/or re-validation (TF-09/TF-10) is required and whether the change is
"significant" enough to warrant a new declaration/notification. Reference-data and SOUP
updates are handled per [TF-08](TF-08-soup-register.md).

## 7. Records

Lifecycle records (design docs, PRs/reviews, CI results, test reports, release records,
risk-file revisions) are retained per the CMGG QMS retention policy for in-house IVDs.
