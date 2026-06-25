# TF-03 — General Safety & Performance Requirements (GSPR) Conformity Checklist

| Field | Value |
| --- | --- |
| Document ID | TF-03 |
| Version | v0.1 DRAFT |
| Status | Draft for internal review |
| Owner | ‹CMGG RA / quality› |
| Approver | ‹Lab director› |
| Date | 2026-06-25 |
| Basis | IVDR (EU) 2017/746 **Annex I** |

> Clause-by-clause mapping of the IVDR Annex I GSPRs to applicability, the method of
> conformity, and the evidence in this technical file. This is the core of the Article
> 5(5)(f) declaration: the institution declares the device meets these requirements, and
> states with justification any that are not fully met. **Clause numbering must be
> verified against the current regulation text by CMGG RA.** "Met by" cites the
> controlling document(s); ◐ = partially evidenced today, action tracked.

Legend — **Status:** ✅ met (evidence exists) · ◐ in progress · ⬜ not started · N/A.

## Chapter I — General requirements

| § | Requirement (paraphrased) | Applic. | Status | Method of conformity / evidence |
| --- | --- | --- | --- | --- |
| 1 | Achieve intended performance; safe & effective; risks acceptable vs benefit | Yes | ◐ | [TF-01](TF-01-intended-purpose.md), [TF-06](TF-06-risk-management-plan.md), TF-10/TF-11 (performance) |
| 2 | Reduce risks as far as possible without adverse benefit-risk | Yes | ◐ | [TF-06](TF-06-risk-management-plan.md) risk controls; design controls in TF-07 |
| 3 | Establish & maintain a **risk management system** | Yes | ◐ | [TF-06](TF-06-risk-management-plan.md) (ISO 14971) |
| 4 | Risk-control measures in priority order (inherent safety → protective → information) | Yes | ◐ | TF-06 risk-control table; IFU warnings TF-15 |
| 5 | Reduce risks related to **use error** (ergonomics, user knowledge) | Yes | ⬜ | TF-12 Usability (IEC 62366-1) |
| 6 | Performance & safety maintained over the device **lifetime** | Yes | ◐ | TF-18 change control; TF-16 PMS; evidence-drift surfacing ([clinical-traceability](../clinical-traceability.md)) |
| 7 | Transport/storage conditions | N/A | N/A | Software, no physical media; delivered/operated within CMGG |
| 8 | Benefit-risk acceptable under normal use | Yes | ◐ | TF-06 §benefit-risk; TF-11 performance report |

## Chapter II — Performance, design & manufacture

| § | Requirement (paraphrased) | Applic. | Status | Method of conformity / evidence |
| --- | --- | --- | --- | --- |
| 9.1 | Performance characteristics — **analytical & clinical performance** appropriate to intended purpose | Yes | ◐ | [TF-10 Performance Evaluation Plan](TF-10-performance-evaluation-plan.md); TF-11 report; Annex XIII |
| 9.3 | Metrological traceability of assigned values | N/A* | N/A | CoGA assigns no measured analyte value; *traceability of interpretation* handled via version manifest ([clinical-traceability](../clinical-traceability.md)) |
| 9.4 | Analytical performance maintained; revalidate on change | Yes | ⬜ | TF-18 change control → re-verification triggers; TF-09 |
| 10 | Chemical/physical/biological properties | N/A | N/A | Software only |
| 11 | Infection & microbial contamination | N/A | N/A | Software only |
| 12 | Materials of biological origin | N/A | N/A | Software only |
| 13 | Construction & interaction with environment | Partial | ◐ | IT environment & integration: [security-posture](../security-posture.md); TF-13 |
| 14 | Devices with a **measuring function** | N/A* | N/A | Qualitative/interpretive; *NIPT fetal fraction is a derived QC estimate with CI, not a diagnostic measurement* — verify classification with RA |
| 15 | Protection against radiation | N/A | N/A | — |
| **16.1** | **Software/programmable systems shall ensure repeatability, reliability & performance** in line with intended use; single-fault safety | Yes | ◐ | Reproducible content-hashed sign-out + server-side recompute ([clinical-traceability](../clinical-traceability.md)); TF-09 V&V; TF-06 |
| **16.2** | Software developed per **state of the art**: development lifecycle, risk management incl. **information security**, verification & validation | Yes | ◐ | [TF-07 Software Lifecycle Plan](TF-07-software-lifecycle-plan.md) (IEC 62304/82304-1); TF-06; TF-09; TF-13 |
| 16.3 | Mobile-platform-specific design considerations | N/A | N/A | Desktop browser in a controlled lab environment; no mobile intended use |
| **16.4** | Set out **minimum hardware / IT-network / IT-security requirements** incl. protection against unauthorised access | Yes | ◐ | [security-posture](../security-posture.md) (RBAC, audit, secrets); TF-13; TF-15 IFU minimum-requirements section |
| 17 | Devices connected to / equipped with energy sources | N/A | N/A | — |
| 18 | Protection against mechanical/thermal risks | N/A | N/A | — |
| 19 | Devices for self-testing / near-patient testing | N/A | N/A | Professional use only, accredited lab (TF-01) |
| 20.1–20.2 | **Information supplied with the device** — label & IFU, comprehensible to intended user | Yes | ⬜ | TF-15 IFU & labelling; in-app `/docs` user guide |
| 20.4.1 | Intended-purpose elements stated | Yes | ✅ | [TF-01](TF-01-intended-purpose.md) §2 |
| 20.4.1 | Limitations, warnings, residual-risk information, required upstream conditions | Yes | ◐ | TF-01 §4; TF-15; provenance footer |
| 20.4.1 | Version / build identification accessible to user | Yes | ◐ | Report footer + version manifest; TF-02 §8 (UDI-equiv scheme **🔲 INPUT NEEDED**) |

\* Items marked N/A* are formally non-applicable but have an analogous control noted, because
the device's interpretive nature changes how the classical IVD wording maps.

## Requirements not (yet) fully met — Article 5(5)(f)(iii) reasoned justifications

The Article 5(5) declaration must list any GSPR **not fully met**, with justification.
Current open items (to be closed before declaration, or carried with justification):

| § | Gap | Plan / justification |
| --- | --- | --- |
| 5 | No formal usability engineering file yet | TF-12 to be produced; interim: professional-only users, training under ISO 15189 competency. |
| 9.1 | Performance evaluation not yet executed | TF-10 plan defined (concordance vs validated assays: 50 BeGECS couples, 100 PGT embryos, 30 WGS trios, 30 NIPT); TF-11 report pending execution. |
| 13/16.4 | Deployment-level encryption-at-rest, TLS between services, secrets manager, byte-level S3 audit | Tracked in [security-posture](../security-posture.md) "Remaining (deployment)"; close via infrastructure work before clinical go-live. |
| 16.2 | Formal IEC 62304 lifecycle documentation incomplete | Codebase practices exist (CI gates, tests, audit); to be formalized in TF-07/TF-09. |
| 20.1 | IFU not yet issued as a controlled document | TF-15; in-app docs exist as basis. |

> No GSPR is proposed to be *permanently* unmet; all open items have a remediation path.
> The declaration should be signed only once these are closed or carry an accepted,
> documented justification.
