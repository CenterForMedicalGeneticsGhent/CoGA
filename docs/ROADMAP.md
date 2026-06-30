# Roadmap

_Product direction and platform summary. For the detailed engineering + regulatory
action plan see [`IMPROVEMENT-WORKPLAN.md`](IMPROVEMENT-WORKPLAN.md); for the IVDR
technical file see [`regulatory/`](regulatory/README.md)._

## Current Platform

- FastAPI backend, React/Vite (TypeScript + Tailwind) frontend, orchestrated via Docker Compose.
- Postgres for metadata, access control, review state, and the clinical audit/sign-out trail; ClickHouse for variant storage.
- **Family workspace** spanning small variants, structural variants, CNVs, a cross-modality variant summary, repeat expansions (TRGT), Paraphase, and mtDNA analysis.
- **Visualization suite**: coverage/APCAD charts, small-variant / SV / CNV / gene / segmental-duplication / DGV / blacklist tracks, ideograms, Circos, pedigrees, and the PGT haplotype/lineage tracks (IBD founder colouring + raw phased markers + ROI overview).
- **Clinical pipeline**: semi-automatic ACMG/AMP classification (SNV + CNV + mtDNA), HPO/Monarch phenotype scoring, variant prioritization with a ranking cache, and family report drafting.
- **Monogenic NIPT** (cfDNA-from-plasma): fetal-fraction estimation, the maternal/fetal VAF category model, and sample-integrity QC.
- **Clinical traceability**: annotation/reference-version manifest, per-classification evidence snapshots, classification-drift detection, an append-only hash-chained audit trail with integrity anchors, and case sign-out with a frozen, versioned report snapshot.
- **Gene Explorer** with MANE/RefSeq/canonical transcript badges; **Global Small Variant Explorer** for cross-project, variant-centric aggregation (keyset-paginated).
- **Operability**: build/version identity scaffolding, scheduled ClickHouse integrity monitoring, durable audit/telemetry pipeline, external-call resilience (bounded timeouts + backoff), and TLS for Postgres/ClickHouse.

## Regulatory Framing

CoGA is operated as an **in-house IVD under IVDR Article 5(5)** at CMGG (ISO 15189).
The device boundary is _annotated VCF → signed clinical report_, and the technical
file lives in [`regulatory/`](regulatory/README.md). Engineering work is weighed for
its GSPR / ISO 14971 / IEC 62304 / ISO 27001 / GDPR consequences, not engineering
merit alone — see the workplan for the per-finding mapping.

## Near-Term Direction

- **Close the live workplan's Phase 1/3 items** — finish the version-identity → sign-out binding, reference-DB/SOUP provenance capture, and the change-control evidence (release tags, CHANGELOG, signed release records).
- **Execute the performance evaluation** (TF-10 → TF-11): the largest substantive regulatory gap; gated on clinical-lead comparators/thresholds/N.
- **Operational maturity**: backups + tested restore, a `/metrics` substrate, the versioned migration ledger, and a stuck-import reaper.

## Product Work

- Extend the variant explorer toward additional aggregation views (gene-centric, transcript-centric, cohort allele frequencies).
- Continue refining family review and sign-out workflows.
- Improve project-level administration and import observability.
- Ingest per-transcript MANE Select / MANE Plus Clinical tags during gene-reference sync so the Gene Explorer badges populate from source data.
