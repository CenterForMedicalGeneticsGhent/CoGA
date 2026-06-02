# Database Schema

This application no longer uses MongoDB. The live schema is split across `Postgres` and `ClickHouse`.

## Postgres Tables

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

- [001_metadata.sql](../backend/db/schema/postgres/001_metadata.sql)
- [002_repeat_expansions.sql](../backend/db/schema/postgres/002_repeat_expansions.sql)
- [003_interval_tracks.sql](../backend/db/schema/postgres/003_interval_tracks.sql)
- [004_audit_logs.sql](../backend/db/schema/postgres/004_audit_logs.sql)
- [005_gene_panel_description.sql](../backend/db/schema/postgres/005_gene_panel_description.sql)
- [006_project_scoped_variant_tags.sql](../backend/db/schema/postgres/006_project_scoped_variant_tags.sql)
- [007_family_import_jobs.sql](../backend/db/schema/postgres/007_family_import_jobs.sql)
- [008_paraphase_results.sql](../backend/db/schema/postgres/008_paraphase_results.sql)
- [009_structural_variant_reviews.sql](../backend/db/schema/postgres/009_structural_variant_reviews.sql)
- [010_auth_login_attempts.sql](../backend/db/schema/postgres/010_auth_login_attempts.sql)
- [011_pgt_family_roles.sql](../backend/db/schema/postgres/011_pgt_family_roles.sql)
- [012_segmental_duplications.sql](../backend/db/schema/postgres/012_segmental_duplications.sql)
- [013_gene_panel_sources.sql](../backend/db/schema/postgres/013_gene_panel_sources.sql)

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
2. applies the Postgres schema
3. ensures the admin user exists
4. seeds the built-in repeat catalog
5. ensures Homo sapiens GRCh38 exists and imports missing GRCh38 cytobands/genes from UCSC when available
6. seeds built-in hg38 reference tracks such as clinical CNVs and segmental duplications
7. queues the first dbNSFP-backed human gene reference sync when the local dbNSFP gene file is present and `gene_info` is empty
8. waits for ClickHouse
9. applies the ClickHouse schema
10. starts the gene refresh worker
