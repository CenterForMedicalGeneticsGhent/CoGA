# TF-17 — Vigilance, Incident & CAPA Procedure

| Field | Value |
| --- | --- |
| Document ID | TF-17 |
| Version | v0.1 DRAFT |
| Status | Draft for internal review |
| Owner | ‹CMGG quality› |
| Approver | ‹Lab director› |
| Date | 2026-06-25 |
| Basis | IVDR Art. 82 (in-house vigilance), Art. 88 (trend); integrated with the CMGG ISO 15189 nonconformity/CAPA system |

> Defines how problems with CoGA are detected, reported, investigated, and corrected.
> Integrates with the existing CMGG ISO 15189 nonconformity/CAPA process rather than creating
> a parallel one. **🔲 INPUT NEEDED:** confirm the Belgian in-house-device reporting
> expectations with FAMHP and the CMGG quality manager (Art. 82 lets Member States set
> vigilance requirements for in-house devices).

---

## 1. Definitions
- **Incident:** a malfunction or deterioration of CoGA, or an inadequacy in its information, that directly or indirectly led, might have led, or might lead to a wrong clinical result or harm.
- **Serious incident:** an incident that led/might lead to death, serious deterioration of health, or a serious public-health threat — including a wrong clinical result acted upon.
- **Near-miss:** caught before clinical impact (e.g. at sign-out review) — recorded and trended.

## 2. Detection & intake
Incidents/near-misses are detected via clinical-use review, the QC/drift signals, user
reports (TF-15 contact), audit logs, or testing. All are logged in the incident register
with: date, reporter, device version, application, affected case(s), description, and
immediate containment.

## 3. Triage & risk assessment
Each incident is risk-assessed against TF-06 (could it cause a wrong clinical result? what
severity?). The **immutable audit trail and content-hashed sign-out** enable reconstruction
of exactly what produced an affected report and identification of other potentially affected
cases (same version/filter/reference data).

## 4. Reporting to the competent authority
- Serious incidents and trends are reported to **FAMHP** as required for in-house devices under IVDR Art. 82/88 and Belgian national provisions. **🔲 INPUT NEEDED:** confirm reportability criteria, timelines, and channel with CMGG RA/FAMHP.
- A breach of personal data follows the separate **GDPR Art. 33/34** notification path (DPO; see TF-14).

## 5. Investigation, correction & CAPA
1. **Containment** — e.g. flag/suspend the affected workflow, notify users, identify affected cases.
2. **Root-cause analysis** — software defect, reference-data issue, use error, input/upstream issue, or genuine interpretive limit.
3. **Correction** — fix under change control (TF-18) with verification + regression (TF-09).
4. **Corrective/preventive action (CAPA)** — address the systemic cause; update risk file (TF-06), tests (TF-09), usability (TF-12), IFU (TF-15), or process as needed.
5. **Field action analog** — for an in-house device, "field safety corrective action" means notifying CMGG users and, if a released report is affected, **amending the affected case(s)** via the versioned amend mechanism and informing the responsible clinician.
6. **Effectiveness check** — verify the action resolved the issue and did not introduce new risk.

## 6. Trend reporting
Recurring non-serious incidents/near-misses are trended (TF-16 PMS); a statistically/clinically
significant trend is treated as a signal and escalated.

## 7. Records
Incident register, investigations, CAPA records, CA reports, and effectiveness checks are
retained per the CMGG QMS and available to FAMHP on request.
