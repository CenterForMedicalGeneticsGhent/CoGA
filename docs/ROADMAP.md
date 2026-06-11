# Roadmap

## Current Platform

- FastAPI backend
- React/Vite frontend
- Postgres metadata and review state
- ClickHouse variant storage
- Family workspace with small/structural variants, variant summary, repeat expansions (TRGT), Paraphase, and mtDNA analysis
- Gene Explorer with MANE/RefSeq/canonical transcript badges
- Global Small Variant Explorer for cross-project, variant-centric aggregation

## Near-Term Work

- Add broader backend integration tests against Postgres and ClickHouse containers
- Ingest per-transcript MANE Select / MANE Plus Clinical tags during gene-reference sync so those Gene Explorer badges populate from source data

## Product Work

- Extend the variant explorer toward additional aggregation views (gene-centric, transcript-centric, cohort allele frequencies)
- Continue refining family review workflows
- Improve project-level administration and import observability
