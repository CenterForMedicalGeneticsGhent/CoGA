# Database Schema

The live schema is split across `Postgres` and `ClickHouse`.

## Postgres Tables

The Postgres schema lives in five domain-grouped, idempotent baseline files under `backend/db/schema/postgres/`. Each table is created once in its final form (later `ALTER ... ADD COLUMN` steps are folded into the `CREATE TABLE`). The domains are: `01_access` (pgcrypto + genome foundation + identity/authorization), `02_reference` (reference/annotation data), `03_assay` (families/samples + per-sample assay data + review/curation), `04_traceability` (import provenance + append-only hash-chained clinical audit + integrity), and `05_grants` (the restricted `coga_app` runtime role + grants/revokes).

Metadata and access:

- `users`
- `species`
- `assemblies`
- `projects`
- `project_users`
- `families`
- `family_projects`
- `samples`
- `sample_projects`
- `family_members`

Reference data:

- `chromosomes`
- `genes`
- `blacklist`
- `clinical_cnvs`
- `segmental_duplications`

Review and annotation state:

- `small_variant_reviews`
- `structural_variant_reviews`
- `small_variant_filter_presets`
- `small_variant_tag_definitions`
- `small_variant_tag_definition_project_links`
- `gene_panels`
- `gene_panel_genes`
- `gene_panel_regions`
- `gene_info`
- `gene_info_refresh_jobs`
- `audit_log_events`

Repeat expansions and tracks:

- `repeat_loci`
- `repeat_expansions`
- `sample_interval_track_sources`
- `sample_paraphase_results`

Import jobs:

- `family_import_jobs`

Canonical schema files:

- [01_access.sql](../backend/db/schema/postgres/01_access.sql) — pgcrypto extension + genome foundation (`species`, `assemblies`, `chromosomes`) + identity/authorization (`users`, `projects`, `project_users`, `auth_login_attempts`)
- [02_reference.sql](../backend/db/schema/postgres/02_reference.sql) — reference/annotation data (`genes`, `gene_info`, `blacklist`, `clinical_cnvs`, `dgv_variants`, `segmental_duplications`, `gene_panels` and children, `hpo_*`, `monarch_*`, `repeat_loci`, `reference_dataset_imports`)
- [03_assay.sql](../backend/db/schema/postgres/03_assay.sql) — families/samples + per-sample assay data + review/curation (`families`, `samples`, `family_members`, `family_projects`, `sample_projects`, `individual_hpo`, `repeat_expansions`, `sample_paraphase_results`, `sample_interval_track_sources`, `small_variant_reviews`, `structural_variant_reviews`, tag/preset tables, `family_sv_gene_index`, `family_variant_ranking_cache`, `family_import_jobs`)
- [04_traceability.sql](../backend/db/schema/postgres/04_traceability.sql) — import provenance + append-only hash-chained clinical audit + integrity (`audit_log_events`, `ui_events`, `raw_import_files`, `family_annotation_manifest`, `clinical_audit_events`, `report_signouts`, `integrity_anchors`) plus the immutability trigger functions/triggers
- [05_grants.sql](../backend/db/schema/postgres/05_grants.sql) — the restricted `coga_app` runtime role + grants/revokes

## ClickHouse Tables

The ClickHouse SQL bootstrap creates the database:

- [001_coga_variant_storage.sql](../backend/db/schema/clickhouse/001_coga_variant_storage.sql)

Per-assembly variant and interval tables are created at runtime by:

- [clickhouse_variant_storage.py](../backend/app/services/clickhouse_variant_storage.py)
- [clickhouse_interval_tracks.py](../backend/app/services/clickhouse_interval_tracks.py)

The important logical entities are:

- small variant records
- small variant sample calls
- structural variant records
- structural variant sample calls
- interval track records for coverage, WisecondorX segments, APCAD, PCF APCAD segment overlays, and haplotypes

## Identifier Rules

- Metadata rows use UUID primary keys.
- API-facing variant IDs are stable string identifiers.
- Human-facing family/sample identifiers remain `family_id` and `sample_id`.

## Relationships

- `species -> assemblies`
- `assemblies -> chromosomes / genes / blacklist / clinical_cnvs / segmental_duplications`
- `projects -> species + assemblies`
- `families <-> projects`
- `samples -> families`
- `samples <-> projects`
- `family_members` maps pedigree roles and affected state
- `small_variant_reviews` attach Postgres annotations to ClickHouse variant IDs/keys

## Startup Behavior

Application startup:

1. waits for Postgres
2. applies the Postgres schema — the loader re-applies all five baseline files in sorted name order on every boot (idempotent; there is no migration ledger)
3. ensures the admin user exists
4. seeds the built-in repeat catalog
5. ensures Homo sapiens GRCh38 exists and imports missing GRCh38 cytobands/genes from UCSC when available
6. seeds built-in hg38 reference tracks such as clinical CNVs and segmental duplications
7. queues the first dbNSFP-backed human gene reference sync when the local dbNSFP gene file is present and `gene_info` is empty
8. waits for ClickHouse
9. applies the ClickHouse schema
10. starts the gene refresh worker
