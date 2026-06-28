# Test Overview

A catalogue of CoGA's automated tests — **what each test file verifies**, with a link to the
file. This is the **file-centric** view; for the **requirement-centric** view (each
requirement → its verifying test), see the Requirements Traceability Matrix
[docs/regulatory/TF-09b](regulatory/TF-09b-requirements-traceability-matrix.md).

| Suite | Files | Tests | Runner |
| --- | --- | --- | --- |
| Backend (Python) | 104 | ~662 | `pytest` |
| Frontend (TypeScript/React) | 94 | 388 | `vitest` |

> Counts are point-in-time; the test tree is the source of truth. Regenerate the inventory
> with the commands in [§ Keeping this current](#keeping-this-current).

---

## Test strategy

- **Unit-first, self-contained.** The backend unit suite mocks Postgres/ClickHouse access, so it runs with no service containers. Pure analysis logic (NIPT, haplotype/PGT, ACMG/CNV, mtDNA, prioritization) is tested directly against synthetic inputs.
- **Integration smoke.** A small integration suite boots the real app against **Postgres + ClickHouse** (schema init, admin seed, health probe) to catch startup/schema failures the unit suite cannot.
- **Frontend component + logic.** `vitest` + Testing Library cover pure `lib/` logic, visualization components (canvas mocked), and page behaviour; safety-relevant UI (route guards, ACMG/CNV/NIPT readouts, sign-out/drift) is explicitly covered.
- **Fail-safe / degraded input.** Across NIPT, ACMG, CNV and haplotype, degraded/empty input must abstain (low-confidence / VUS / uninformative), never silently mis-call.
- **Two backend test roots.** Tests live in both the top-level `tests/` and `backend/tests/` (both are on `pytest.ini` `testpaths`). A few filenames exist in **both** directories as distinct suites.

## How to run

```bash
# Backend — unit suite (mocked datastores; honours pytest.ini testpaths)
python -m pytest -q                       # CI; or backend/.venv/bin/python -m pytest

# Backend — integration smoke (needs Postgres + ClickHouse; CI sets RUN_INTEGRATION=1)
python -m pytest backend/tests/integration -q

# Frontend — the full gate (matches CI)
cd frontend && npm run tsc && npm run lint && npm run test
```

## Continuous integration

`.github/workflows/ci.yml` runs four jobs on every PR and push to `main`:

| Job | What it runs | Notes |
| --- | --- | --- |
| **backend** | `pip install -r backend/requirements-dev.txt` → `pytest -q` | Self-contained unit suite (no containers). |
| **smoke** | `pytest backend/tests/integration` against `postgres:16` + `clickhouse/clickhouse-server:25.3` services | Real lifespan: schema init, migrations, admin seed, health probe. |
| **frontend** | `npm ci` → `npm run tsc` → `npm run lint` → `npm run test` | Type-check + ESLint + vitest. |
| **sbom** | CycloneDX SBOM for backend + frontend, uploaded as artifacts | Supply-chain evidence (see [sbom/README.md](../sbom/README.md)). |

The `backend`, `smoke` and `frontend` jobs are **required status checks** on `main`
(branch protection), so a change cannot merge unless they pass.

---

## Backend tests

### Monogenic NIPT
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_nipt.py](../backend/tests/test_nipt.py) | NIPT family/trio identification and assay-key resolution. |
| [backend/tests/test_nipt_analysis.py](../backend/tests/test_nipt_analysis.py) | Fetal-fraction estimation (+ external-FF reconciliation), fetal-sex inference, 8-category site classification, empty-input fail-safe. |
| [backend/tests/test_nipt_coverage.py](../backend/tests/test_nipt_coverage.py) | On-target coverage summarization, weighted-median, low-coverage flagging. |
| [backend/tests/test_nipt_end_to_end.py](../backend/tests/test_nipt_end_to_end.py) | End-to-end NIPT on a demo VCF: FF + category recovery, recessive-at-risk. |
| [backend/tests/test_nipt_artifact_pg.py](../backend/tests/test_nipt_artifact_pg.py) | Recurrent-artifact list CRUD, auto-seed, per-assay scoping. |
| [backend/tests/test_nipt_package_import.py](../backend/tests/test_nipt_package_import.py) | Discovery/validation of NIPT family packages (manifest/PED, analysis-type tags). |
| [backend/tests/test_nipt_service.py](../backend/tests/test_nipt_service.py) | NIPT orchestration: observation building, filters, coverage, inheritance presets. |

### Expanded carrier screening / gene panels
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_panel_filter_constraints.py](../backend/tests/test_panel_filter_constraints.py) | Panel-filter constraint fetch and application in variant queries. |
| [backend/tests/test_panel_metadata_service.py](../backend/tests/test_panel_metadata_service.py) | Panel version management, JSONB parsing, name-uniqueness. |
| [backend/tests/test_panelapp_service.py](../backend/tests/test_panelapp_service.py) | PanelApp import parsing and summary extraction. |
| [backend/tests/test_gene_panel_versions.py](../backend/tests/test_gene_panel_versions.py) | Panel version creation, normalization, list/detail retrieval. |

### PGT / haplotype segregation
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_haplotype_lineage_service.py](../backend/tests/test_haplotype_lineage_service.py) | Pedigree-aware IBD haplotype colouring, homolog assignment, relative greying. |
| [backend/tests/test_phased_marker_service.py](../backend/tests/test_phased_marker_service.py) | Phased-marker retrieval, parent resolution, Mendel-error/informative-site QC. |
| [backend/tests/test_bed_service_lineage_precompute.py](../backend/tests/test_bed_service_lineage_precompute.py) | Genome-overview lineage precompute: fingerprint, origin-packed intervals, hash-guarded reads. |
| [tests/test_bed_service.py](../tests/test_bed_service.py) | Interval-track / lineage retrieval and sample-context handling. |

### Rare-disorder diagnostics (trio, SV, repeats, Paraphase, mtDNA)
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_de_novo_detection.py](../backend/tests/test_de_novo_detection.py) | Trio de-novo detection with confident hom-ref matching and full-trio requirement. |
| [backend/tests/test_sv_gene_index.py](../backend/tests/test_sv_gene_index.py) | SV→gene index and SV second-hit (compound-het) summarization. |
| [backend/tests/test_mitochondrial_analysis.py](../backend/tests/test_mitochondrial_analysis.py) | mtDNA variant collection, heteroplasmy, maternal transmission, review attachment. |
| [tests/test_paraphase_pg.py](../tests/test_paraphase_pg.py) | Paraphase SMN metrics (copy number, read counts, haplotype groups). |
| [tests/test_repeat_expansion_pg.py](../tests/test_repeat_expansion_pg.py) | Repeat-expansion family table storage/retrieval (TRGT). |
| [tests/test_presence_count_only.py](../tests/test_presence_count_only.py) | `count_only` presence mode for repeat/Paraphase tables. |
| [tests/test_structural_variant_ingest.py](../tests/test_structural_variant_ingest.py) | Manual SV record parsing incl. remote breakend partners. |

### Variant classification (ACMG / CNV)
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_acmg_classification.py](../backend/tests/test_acmg_classification.py) | ACMG points, ClinGen thresholds, BA1 override, VUS tiers, no-evidence→VUS fail-safe. |
| [backend/tests/test_cnv_acmg_points.py](../backend/tests/test_cnv_acmg_points.py) | ClinGen-2019 CNV point system, class thresholds, empty/missing-flag/malformed handling. |

### Clinical traceability & audit
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_annotation_manifest.py](../backend/tests/test_annotation_manifest.py) | Annotation/version-manifest layer merge and canonical ordering. |
| [backend/tests/test_classification_drift.py](../backend/tests/test_classification_drift.py) | Evidence-snapshot build and drift detection across annotation versions. |
| [backend/tests/test_clinical_audit.py](../backend/tests/test_clinical_audit.py) | Clinical-audit diff generation (classification/tags/notes), one event per change. |
| [backend/tests/test_report_signout.py](../backend/tests/test_report_signout.py) | Sign-out canonical content-hash (order-independent), drift gate, versioning. |
| [backend/tests/test_hash_chain.py](../backend/tests/test_hash_chain.py) | Tamper-evidence hash-chain primitives (P1-4): canonical determinism, genesis anchoring, and `verify_chain` flagging content tampering / deletion / reordering. |
| [backend/tests/test_integrity_anchor.py](../backend/tests/test_integrity_anchor.py) | Signed chain-head anchor (P1-4 follow-up): Ed25519 sign/verify round-trip, unsigned fallback, deterministic head sort + order-independent anchor_root, `signed_core` isoformat. |
| [backend/tests/test_audit_log_pg.py](../backend/tests/test_audit_log_pg.py) | HTTP audit-log event JSONB serialization/storage. |
| [tests/test_small_variant_review_pg.py](../tests/test_small_variant_review_pg.py) | Small-variant review persistence and payload serialization. |

### Access control & security
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_access_control.py](../backend/tests/test_access_control.py) | Project-scoped RBAC: viewer/admin access, cross-project visibility. |
| [backend/tests/test_auth_rate_limit_pg.py](../backend/tests/test_auth_rate_limit_pg.py) | Failed-login throttling and reset. |
| [backend/tests/test_auth_swagger_token.py](../backend/tests/test_auth_swagger_token.py) | Swagger/bearer token authentication. |
| [backend/tests/test_config_security.py](../backend/tests/test_config_security.py) | Refuse-to-start on insecure default secrets outside dev. |
| [backend/tests/test_request_logging.py](../backend/tests/test_request_logging.py) | Request-logging sanitization, path/secret masking, db-update derivation. |

### Ingestion / storage / ClickHouse / files
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_clickhouse.py](../backend/tests/test_clickhouse.py) | ClickHouse client query/command/insert dispatch and recording. |
| [backend/tests/test_clickhouse_dataset_key.py](../backend/tests/test_clickhouse_dataset_key.py) | Dataset-key normalization and injection-safe handling. |
| [backend/tests/test_clickhouse_family_variants.py](../backend/tests/test_clickhouse_family_variants.py) | Small-variant query, genotype/phasing parsing, inheritance + compound-het. |
| [backend/tests/test_clickhouse_integrity.py](../backend/tests/test_clickhouse_integrity.py) | ClickHouse table-integrity / detached-parts checks. |
| [backend/tests/test_clickhouse_interval_tracks.py](../backend/tests/test_clickhouse_interval_tracks.py) | Interval-track presence detection and region filtering. |
| [backend/tests/test_clickhouse_variant_storage_ops.py](../backend/tests/test_clickhouse_variant_storage_ops.py) | Variant-assembly listing, table dedup, mutation status. |
| [backend/tests/test_object_storage.py](../backend/tests/test_object_storage.py) | S3 URI parsing and object-storage helpers. |
| [backend/tests/test_s3_import_and_cram.py](../backend/tests/test_s3_import_and_cram.py) | S3 source authorization; CRAM/BAM **access-before-serve** and sample resolution. |
| [backend/tests/test_raw_import_file_verify.py](../backend/tests/test_raw_import_file_verify.py) | File SHA-256 verification: verified / mismatch / missing / unverifiable. |
| [backend/tests/test_variant_upload_service.py](../backend/tests/test_variant_upload_service.py) | VCF/VEP parsing → ClickHouse ingestion; phased-block (PS) preservation. |
| [tests/test_variant_upload_service.py](../tests/test_variant_upload_service.py) | Variant-upload parsing/ingestion (top-level suite). |
| [tests/test_clickhouse_variant_storage.py](../tests/test_clickhouse_variant_storage.py) | Family-scoped variant counting and query building. |
| [tests/test_raw_import_files_pg.py](../tests/test_raw_import_files_pg.py) | Raw-import file-size limits and SHA-256 verification. |

### Gene / HPO / panel / Monarch / reference
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_gene_info_bulk_sources.py](../backend/tests/test_gene_info_bulk_sources.py) | Gene-reference bulk-source parsing; dbNSFP constraint metrics. |
| [backend/tests/test_gene_locus_primary_chromosome.py](../backend/tests/test_gene_locus_primary_chromosome.py) | Primary-chromosome / multi-contig gene-locus resolution. |
| [backend/tests/test_hpo_api.py](../backend/tests/test_hpo_api.py) | HPO router and family HPO-term attachment. |
| [backend/tests/test_hpo_service.py](../backend/tests/test_hpo_service.py) | HPO ontology parsing, closure computation, inline-HPO handling. |
| [backend/tests/test_monarch_ingest.py](../backend/tests/test_monarch_ingest.py) | Monarch gene-disease/phenotype association parsing. |
| [backend/tests/test_monarch_search_api.py](../backend/tests/test_monarch_search_api.py) | Monarch disease/phenotype search endpoint. |
| [backend/tests/test_monarch_semsim.py](../backend/tests/test_monarch_semsim.py) | Monarch semantic-similarity phenotype matching/normalization. |
| [tests/test_hpo_service.py](../tests/test_hpo_service.py) | HPO annotation import and session-state tracking. |
| [tests/test_gene_info_bulk_sources.py](../tests/test_gene_info_bulk_sources.py) | ClinGen validity parsing and gene-symbol grouping. |
| [tests/test_gene_info_jobs_pg.py](../tests/test_gene_info_jobs_pg.py) | Gene-reference background refresh job (queue/run/state). |
| [tests/test_reference_metadata_service.py](../tests/test_reference_metadata_service.py) | Reference metadata aggregation and transcript resolution. |
| [tests/test_reference_source_service.py](../tests/test_reference_source_service.py) | Reference import-source management and assembly metadata. |

### Variant prioritization & explorer
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_variant_prioritization.py](../backend/tests/test_variant_prioritization.py) | Exomiser-style scoring (pathogenicity, frequency, segregation, mode combinations). |
| [backend/tests/test_variant_ranking_cache.py](../backend/tests/test_variant_ranking_cache.py) | Ranking-cache invalidation keyed by family/filters. |
| [backend/tests/test_variant_explorer_service.py](../backend/tests/test_variant_explorer_service.py) | Cross-project variant aggregation, ranking, carrier pagination. |
| [backend/tests/test_variant_explorer_router.py](../backend/tests/test_variant_explorer_router.py) | Variant-explorer export column formatting. |
| [tests/test_variant_explorer_service.py](../tests/test_variant_explorer_service.py) | Variant-explorer scope resolution and global query (top-level suite). |

### Sample QC
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_sample_integrity_qc.py](../backend/tests/test_sample_integrity_qc.py) | Relatedness, paternity, sex inference, Mendelian consistency, QC aggregation (sample-swap/data-integrity). |
| [backend/tests/test_sample_integrity_service.py](../backend/tests/test_sample_integrity_service.py) | Family-scoped sample-integrity report generation. |
| [tests/test_family_structure_validation.py](../tests/test_family_structure_validation.py) | Pedigree-graph validation and parent-sex consistency. |

### Pedigree / family metadata / package import
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_family_metadata_api.py](../backend/tests/test_family_metadata_api.py) | Family-metadata API routes. |
| [backend/tests/test_family_metadata_context.py](../backend/tests/test_family_metadata_context.py) | Family-metadata context building from DB rows. |
| [backend/tests/test_family_member_batch_update_service.py](../backend/tests/test_family_member_batch_update_service.py) | Batch member updates with dirty-tracking. |
| [backend/tests/test_family_member_detail_service.py](../backend/tests/test_family_member_detail_service.py) | Member detail retrieval and impact analysis. |
| [backend/tests/test_family_package_import_pcf.py](../backend/tests/test_family_package_import_pcf.py) | PCF (array-CGH) dataset discovery and segment parsing. |
| [backend/tests/test_family_pedigree_generation.py](../backend/tests/test_family_pedigree_generation.py) | Pedigree file generation / LINKAGE output. |
| [backend/tests/test_family_service.py](../backend/tests/test_family_service.py) | Small-variant presence filters and family ROI payloads. |
| [backend/tests/test_family_structure_update_dirty.py](../backend/tests/test_family_structure_update_dirty.py) | Family-structure update with member dirty-tracking. |
| [backend/tests/test_manual_family_metadata.py](../backend/tests/test_manual_family_metadata.py) | Manual family creation and pedigree threading. |
| [backend/tests/test_families_export.py](../backend/tests/test_families_export.py) | Family export cell formatting (reviews/genotypes). |
| [tests/test_family_metadata_context.py](../tests/test_family_metadata_context.py) | Family-metadata context building (top-level suite). |
| [tests/test_family_package_import.py](../tests/test_family_package_import.py) | Package discovery, validation, manifest loading. |
| [tests/test_family_service.py](../tests/test_family_service.py) | Family ROI payload and presence filtering (top-level suite). |
| [tests/test_ped_service.py](../tests/test_ped_service.py) | Pedigree service parsing/standardization. |

### Integration / smoke
| Test file | Purpose |
| --- | --- |
| [backend/tests/integration/test_app_startup.py](../backend/tests/integration/test_app_startup.py) | Boots the app against real Postgres + ClickHouse (schema init, admin seed) and asserts it serves. |
| [backend/tests/integration/test_clickhouse_integrity.py](../backend/tests/integration/test_clickhouse_integrity.py) | Validates integrity-check SQL against a real ClickHouse server. |
| [backend/tests/integration/test_append_only_triggers.py](../backend/tests/integration/test_append_only_triggers.py) | Fires the append-only triggers on `audit_log_events`/`clinical_audit_events`/`report_signouts`: UPDATE/DELETE rejected; the FK→NULL unlink carve-out allowed (and nothing else); signed report frozen. |
| [backend/tests/integration/test_hash_chain_integration.py](../backend/tests/integration/test_hash_chain_integration.py) | End-to-end per-family hash chains (P1-4): real writers produce a chain `verify_*_chain` accepts; a privileged trigger-bypass UPDATE/DELETE is detected & localised; the FK→NULL carve-out does not break the chain. |
| [backend/tests/integration/test_app_role_privileges.py](../backend/tests/integration/test_app_role_privileges.py) | P1-3 privilege separation: the restricted `coga_app` role may INSERT/SELECT the append-only tables (and delete users — the FK cascade still nulls the audit FK) but is denied UPDATE/DELETE and DISABLE TRIGGER on them. |
| [backend/tests/integration/test_integrity_anchor_integration.py](../backend/tests/integration/test_integrity_anchor_integration.py) | Signed chain-head anchor end-to-end: a real signed anchor verifies; an owner-bypass re-chain (recomputed head row_hash) or truncation (deleted head) diverges from it; a tampered anchor signature is caught; anchors chain (prev_anchor_hash). |
| [backend/tests/integration/test_gene_search_indexes.py](../backend/tests/integration/test_gene_search_indexes.py) | P2-3: the gene-search expression indexes serve their queries — EXPLAIN with enable_seqscan=off forces the planner onto each index (autocomplete prefix LIKE, panel upper() IN, gene_info lower() lookup, candidate lower() OR), proving the index expression/opclass matches the predicate. |

### API / config / infra / other
| Test file | Purpose |
| --- | --- |
| [backend/tests/test_api_route_prefix.py](../backend/tests/test_api_route_prefix.py) | API route-prefix consistency via the OpenAPI schema. |
| [backend/tests/test_api_id_schemas.py](../backend/tests/test_api_id_schemas.py) | UUID/date/enum schema validation for API payloads. |
| [backend/tests/test_async_blocking_io.py](../backend/tests/test_async_blocking_io.py) | Concurrent manifest resolution, reference-cache, and blocking-IO offload. |
| [backend/tests/test_health_endpoint.py](../backend/tests/test_health_endpoint.py) | Health endpoint liveness without datastores. |
| [backend/tests/test_postgres_schema_loader.py](../backend/tests/test_postgres_schema_loader.py) | SQL splitting and dollar-quoted PL/pgSQL handling (migration loader). |
| [backend/tests/test_github_releases_service.py](../backend/tests/test_github_releases_service.py) | GitHub release summary/changelog formatting. |
| [backend/tests/test_ui_events.py](../backend/tests/test_ui_events.py) | UI-event path masking, label sanitization, batch insert. |
| [backend/tests/test_apcad_band_targets.py](../backend/tests/test_apcad_band_targets.py) | APCAD downsample budget allocation across BAF bands. |
| [backend/tests/test_admin_clickhouse_listing.py](../backend/tests/test_admin_clickhouse_listing.py) | Admin ClickHouse listing and variant-count aggregation. |
| [backend/tests/test_config.py](../backend/tests/test_config.py) | CORS-origins config parsing. |
| [backend/tests/test_small_variant_clinvar_frequency_rescue.py](../backend/tests/test_small_variant_clinvar_frequency_rescue.py) | ClinVar P/LP rescue overriding frequency thresholds. |
| [backend/tests/test_small_variant_review_payload.py](../backend/tests/test_small_variant_review_payload.py) | Review payload datetime serialization / bigint truncation. |
| [backend/tests/test_structural_panel_gene_match.py](../backend/tests/test_structural_panel_gene_match.py) | SV gene-overlap matching and panel-filter constraints. |
| [backend/tests/test_structural_variant_track_slim.py](../backend/tests/test_structural_variant_track_slim.py) | SV track slimming (annotations dropped in track mode). |
| [backend/tests/test_variant_annotation_parser.py](../backend/tests/test_variant_annotation_parser.py) | VCF annotation parsing incl. SpliceAI / scientific notation. |
| [tests/test_variant_annotation_parser.py](../tests/test_variant_annotation_parser.py) | VCF CSQ annotation header parsing (top-level suite). |
| [tests/test_admin_inventory.py](../tests/test_admin_inventory.py) | Data-inventory admin endpoint, assembly-scoped counting. |
| [tests/test_admin_service.py](../tests/test_admin_service.py) | Admin service listing and family-count aggregation. |
| [tests/test_backend_hotpath_cleanups.py](../tests/test_backend_hotpath_cleanups.py) | Hot-path cleanups: DDL memoization, HPO table-probe caching. |
| [tests/test_load_demo_quartet.py](../tests/test_load_demo_quartet.py) | Demo-bundle loading and family-definition manifest parsing. |

---

## Frontend tests

### `lib/` — pure logic
| Test file | Purpose |
| --- | --- |
| [frontend/src/__tests__/serverSecurityHeaders.test.ts](../frontend/src/__tests__/serverSecurityHeaders.test.ts) | SPA security response headers + enforcing CSP (IGV/S3/fonts-aware); HSTS opt-in. |
| [frontend/src/lib/__tests__/api.test.ts](../frontend/src/lib/__tests__/api.test.ts) | Auth-header attachment and error normalization. |
| [frontend/src/lib/__tests__/auth.test.ts](../frontend/src/lib/__tests__/auth.test.ts) | Session persistence; token/role/username storage; admin/auth checks. |
| [frontend/src/lib/__tests__/chromosomes.test.ts](../frontend/src/lib/__tests__/chromosomes.test.ts) | Natural chromosome ordering (numeric + X/Y/MT). |
| [frontend/src/lib/__tests__/cnvAcmg.test.ts](../frontend/src/lib/__tests__/cnvAcmg.test.ts) | CNV ACMG classification, scoring, criterion evaluation. |
| [frontend/src/lib/__tests__/embryoSegregation.test.ts](../frontend/src/lib/__tests__/embryoSegregation.test.ts) | Embryo classification at ROI and recombination inference. |
| [frontend/src/lib/__tests__/errorMessage.test.ts](../frontend/src/lib/__tests__/errorMessage.test.ts) | Error-message extraction and fallback formatting. |
| [frontend/src/lib/__tests__/familyMembers.test.ts](../frontend/src/lib/__tests__/familyMembers.test.ts) | Proband-first family-member ordering. |
| [frontend/src/lib/__tests__/genotypes.test.ts](../frontend/src/lib/__tests__/genotypes.test.ts) | Genotype formatting and alt-allele detection. |
| [frontend/src/lib/__tests__/haplotypeRisk.test.ts](../frontend/src/lib/__tests__/haplotypeRisk.test.ts) | Disease-haplotype inference + embryo risk states; donor/empty → uninformative. |
| [frontend/src/lib/__tests__/igvLoader.test.ts](../frontend/src/lib/__tests__/igvLoader.test.ts) | IGV library dynamic loading. |
| [frontend/src/lib/__tests__/proxyLocation.test.ts](../frontend/src/lib/__tests__/proxyLocation.test.ts) | Proxy URL rewriting to same-origin paths. |
| [frontend/src/lib/__tests__/queryClient.test.ts](../frontend/src/lib/__tests__/queryClient.test.ts) | React-Query client cache/refetch defaults. |
| [frontend/src/lib/__tests__/reference.test.tsx](../frontend/src/lib/__tests__/reference.test.tsx) | Family reference-data fetching hook. |
| [frontend/src/lib/__tests__/sampleFilterState.test.ts](../frontend/src/lib/__tests__/sampleFilterState.test.ts) | Genotype-selection parse/serialize and default filter state. |
| [frontend/src/lib/__tests__/settings.test.ts](../frontend/src/lib/__tests__/settings.test.ts) | UI window/threshold settings storage. |
| [frontend/src/lib/__tests__/storage.test.ts](../frontend/src/lib/__tests__/storage.test.ts) | localStorage fallback / session persistence. |
| [frontend/src/lib/__tests__/trackSampling.test.ts](../frontend/src/lib/__tests__/trackSampling.test.ts) | Adaptive track window / point-segment-variant limits. |
| [frontend/src/lib/acmg/__tests__/evaluate.test.ts](../frontend/src/lib/acmg/__tests__/evaluate.test.ts) | ACMG criterion auto-suggestion for small variants. |
| [frontend/src/lib/acmg/__tests__/evaluateMito.test.ts](../frontend/src/lib/acmg/__tests__/evaluateMito.test.ts) | Mitochondrial ACMG criterion evaluation. |
| [frontend/src/lib/acmg/__tests__/score.test.ts](../frontend/src/lib/acmg/__tests__/score.test.ts) | ACMG classification computation from criterion selections. |

### Visualization components
| Test file | Purpose |
| --- | --- |
| [frontend/src/components/__tests__/ApcadChart.test.tsx](../frontend/src/components/__tests__/ApcadChart.test.tsx) | APCAD chart rendering / canvas context. |
| [frontend/src/components/__tests__/CircosPlot.test.tsx](../frontend/src/components/__tests__/CircosPlot.test.tsx) | Circos plot rendering (bands, telomere/centromere geometry). |
| [frontend/src/components/__tests__/CnvTrack.test.tsx](../frontend/src/components/__tests__/CnvTrack.test.tsx) | CNV track rendering and query integration. |
| [frontend/src/components/__tests__/CoverageSegmentsChart.test.tsx](../frontend/src/components/__tests__/CoverageSegmentsChart.test.tsx) | Coverage-segments chart rendering. |
| [frontend/src/components/__tests__/DgvTrack.test.tsx](../frontend/src/components/__tests__/DgvTrack.test.tsx) | DGV background track rendering. |
| [frontend/src/components/__tests__/HaplotypePhasedTrack.test.tsx](../frontend/src/components/__tests__/HaplotypePhasedTrack.test.tsx) | Phased-haplotype track + raw-marker overlay rendering. |
| [frontend/src/components/__tests__/Histogram.test.tsx](../frontend/src/components/__tests__/Histogram.test.tsx) | Histogram rendering with large datasets. |
| [frontend/src/components/__tests__/IgvViewer.test.tsx](../frontend/src/components/__tests__/IgvViewer.test.tsx) | IGV browser init, genome search, track loading, cleanup. |
| [frontend/src/components/__tests__/Pedigree.test.tsx](../frontend/src/components/__tests__/Pedigree.test.tsx) | Pedigree diagram: affected/carrier status, per-sample QC ring. |
| [frontend/src/components/__tests__/RepeatExpansionTrack.test.tsx](../frontend/src/components/__tests__/RepeatExpansionTrack.test.tsx) | Repeat-expansion track rendering. |
| [frontend/src/components/__tests__/SmallVariantTrack.test.tsx](../frontend/src/components/__tests__/SmallVariantTrack.test.tsx) | Small-variant track rendering with query/API mocks. |
| [frontend/src/components/__tests__/VariantTrack.test.tsx](../frontend/src/components/__tests__/VariantTrack.test.tsx) | Base variant-track rendering. |
| [frontend/src/components/visualizations/__tests__/VizTooltip.test.tsx](../frontend/src/components/visualizations/__tests__/VizTooltip.test.tsx) | Floating tooltip portal rendering. |

### Shared UI components
| Test file | Purpose |
| --- | --- |
| [frontend/src/components/__tests__/Breadcrumbs.test.tsx](../frontend/src/components/__tests__/Breadcrumbs.test.tsx) | Breadcrumb navigation rendering with router context. |
| [frontend/src/components/__tests__/InfoTip.test.tsx](../frontend/src/components/__tests__/InfoTip.test.tsx) | Info tooltip show/hide on hover. |
| [frontend/src/components/__tests__/LoadingBar.test.tsx](../frontend/src/components/__tests__/LoadingBar.test.tsx) | Animated loading-status bar accessibility. |
| [frontend/src/components/__tests__/RequireAuth.test.tsx](../frontend/src/components/__tests__/RequireAuth.test.tsx) | Auth route-guard: unauthenticated → login (`?next=`). |
| [frontend/src/components/__tests__/RequireAdmin.test.tsx](../frontend/src/components/__tests__/RequireAdmin.test.tsx) | Admin route-guard: viewer → dashboard, admin/superuser → content. |
| [frontend/src/components/__tests__/SessionRedirect.test.tsx](../frontend/src/components/__tests__/SessionRedirect.test.tsx) | Authenticated-user redirect to dashboard target. |

### Family workspace pages & parts
| Test file | Purpose |
| --- | --- |
| [frontend/src/pages/families/__tests__/AcmgClassificationModal.test.tsx](../frontend/src/pages/families/__tests__/AcmgClassificationModal.test.tsx) | ACMG modal: criterion selection, server-recompute, payload emission. |
| [frontend/src/pages/families/__tests__/AcmgScaleBar.test.tsx](../frontend/src/pages/families/__tests__/AcmgScaleBar.test.tsx) | ACMG scale readout: class, signed points, VUS tier, BA1 override. |
| [frontend/src/pages/families/__tests__/CnvAcmgClassificationModal.test.tsx](../frontend/src/pages/families/__tests__/CnvAcmgClassificationModal.test.tsx) | CNV ACMG modal: kind toggle, overridable criteria, recompute→save. |
| [frontend/src/pages/families/__tests__/CnvScaleBar.test.tsx](../frontend/src/pages/families/__tests__/CnvScaleBar.test.tsx) | ClinGen CNV scale readout. |
| [frontend/src/pages/families/__tests__/FamiliesPage.test.tsx](../frontend/src/pages/families/__tests__/FamiliesPage.test.tsx) | Legacy families route → dashboard redirect. |
| [frontend/src/pages/families/__tests__/FamilyDetailPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyDetailPage.test.tsx) | Family detail page rendering and route/query integration. |
| [frontend/src/pages/families/__tests__/FamilyIgvPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyIgvPage.test.tsx) | IGV page with sample navigation/track loading. |
| [frontend/src/pages/families/__tests__/FamilyMitoDNAAnalysisPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyMitoDNAAnalysisPage.test.tsx) | mtDNA analysis page rendering and API integration. |
| [frontend/src/pages/families/__tests__/FamilyNiptPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyNiptPage.test.tsx) | NIPT dashboard (FF, category counts, funnel, coverage). |
| [frontend/src/pages/families/__tests__/FamilyNiptReportPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyNiptReportPage.test.tsx) | NIPT report generation/display. |
| [frontend/src/pages/families/__tests__/FamilyParaphasePage.test.tsx](../frontend/src/pages/families/__tests__/FamilyParaphasePage.test.tsx) | Paraphase page interaction and API calls. |
| [frontend/src/pages/families/__tests__/FamilyRepeatExpansionsPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyRepeatExpansionsPage.test.tsx) | Repeat-expansion page filtering/display. |
| [frontend/src/pages/families/__tests__/FamilyReportPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyReportPage.test.tsx) | Clinical report: provenance footer, drift badge, sign-out/amend, audit timeline. |
| [frontend/src/pages/families/__tests__/FamilyRoiMarkersPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyRoiMarkersPage.test.tsx) | ROI-markers page filtering/API. |
| [frontend/src/pages/families/__tests__/FamilySampleQcPage.test.tsx](../frontend/src/pages/families/__tests__/FamilySampleQcPage.test.tsx) | Sample-QC page rendering. |
| [frontend/src/pages/families/__tests__/FamilySmallVariantsPage.test.tsx](../frontend/src/pages/families/__tests__/FamilySmallVariantsPage.test.tsx) | Small-variants page: filtering, search, interactions, loading. |
| [frontend/src/pages/families/__tests__/FamilyStructuralVariantsPage.test.tsx](../frontend/src/pages/families/__tests__/FamilyStructuralVariantsPage.test.tsx) | Structural-variants page filtering/API. |
| [frontend/src/pages/families/__tests__/MonarchPhenotypeMatchPanel.test.tsx](../frontend/src/pages/families/__tests__/MonarchPhenotypeMatchPanel.test.tsx) | Monarch phenotype-match panel search/display. |
| [frontend/src/pages/families/__tests__/NiptClassificationBlock.test.tsx](../frontend/src/pages/families/__tests__/NiptClassificationBlock.test.tsx) | NIPT per-variant block: category/confidence/VAF/flags. |
| [frontend/src/pages/families/__tests__/SmallVariantCards.test.tsx](../frontend/src/pages/families/__tests__/SmallVariantCards.test.tsx) | Small-variant cards (transcript popup, effects). |
| [frontend/src/pages/families/__tests__/SmallVariantTable.test.tsx](../frontend/src/pages/families/__tests__/SmallVariantTable.test.tsx) | Small-variant table rendering and tooltips. |
| [frontend/src/pages/families/__tests__/SvSecondHitBadge.test.tsx](../frontend/src/pages/families/__tests__/SvSecondHitBadge.test.tsx) | SV second-hit (compound-het) badge. |
| [frontend/src/pages/families/__tests__/buildLiteraturePubmedHref.test.ts](../frontend/src/pages/families/__tests__/buildLiteraturePubmedHref.test.ts) | PubMed search-URL construction for variants. |
| [frontend/src/pages/families/__tests__/reportNarrative.test.ts](../frontend/src/pages/families/__tests__/reportNarrative.test.ts) | Narrative report text generation. |
| [frontend/src/pages/families/__tests__/smallVariantSearch.test.ts](../frontend/src/pages/families/__tests__/smallVariantSearch.test.ts) | Small-variant filters, presets, genotype state, search params. |
| [frontend/src/pages/families/__tests__/structuralVariantSearch.test.ts](../frontend/src/pages/families/__tests__/structuralVariantSearch.test.ts) | Structural-variant search state and filters. |

### Genome views
| Test file | Purpose |
| --- | --- |
| [frontend/src/pages/genome/__tests__/ChromosomeViewPage.test.tsx](../frontend/src/pages/genome/__tests__/ChromosomeViewPage.test.tsx) | Chromosome viewer routing, chrM normalization, workspace integration. |
| [frontend/src/pages/genome/__tests__/ChromosomeViewWorkspace.test.tsx](../frontend/src/pages/genome/__tests__/ChromosomeViewWorkspace.test.tsx) | Chromosome workspace with coverage/track integration. |
| [frontend/src/pages/genome/__tests__/CircosPlotPage.test.tsx](../frontend/src/pages/genome/__tests__/CircosPlotPage.test.tsx) | Circos page routing and sidebar. |
| [frontend/src/pages/genome/__tests__/CnvDetailsPage.test.tsx](../frontend/src/pages/genome/__tests__/CnvDetailsPage.test.tsx) | CNV detail page rendering. |
| [frontend/src/pages/genome/__tests__/GenomeOverviewPage.test.tsx](../frontend/src/pages/genome/__tests__/GenomeOverviewPage.test.tsx) | Genome-overview page with sidebar/workspace. |
| [frontend/src/pages/genome/__tests__/GenomeOverviewWorkspace.test.tsx](../frontend/src/pages/genome/__tests__/GenomeOverviewWorkspace.test.tsx) | Genome workspace with coverage/APCAD charts. |
| [frontend/src/pages/genome/__tests__/ViewerTrackBlock.test.tsx](../frontend/src/pages/genome/__tests__/ViewerTrackBlock.test.tsx) | Genome track-viewer mouse interaction/selection. |

### Auth / dashboard / intake
| Test file | Purpose |
| --- | --- |
| [frontend/src/pages/auth/__tests__/LoginPage.test.tsx](../frontend/src/pages/auth/__tests__/LoginPage.test.tsx) | Login submission, session auth, `next`-path validation. |
| [frontend/src/pages/dashboard/__tests__/Dashboard.test.tsx](../frontend/src/pages/dashboard/__tests__/Dashboard.test.tsx) | Dashboard family list and navigation. |
| [frontend/src/pages/dashboard/__tests__/FamilyBuilderPage.test.tsx](../frontend/src/pages/dashboard/__tests__/FamilyBuilderPage.test.tsx) | Family creation/editing with member form + API. |
| [frontend/src/pages/dashboard/__tests__/PackageImportPage.test.tsx](../frontend/src/pages/dashboard/__tests__/PackageImportPage.test.tsx) | Package-import workflow and upload handling. |
| [frontend/src/pages/uploads/__tests__/SampleUpload.test.tsx](../frontend/src/pages/uploads/__tests__/SampleUpload.test.tsx) | Sample-upload form and API integration. |

### Admin pages
| Test file | Purpose |
| --- | --- |
| [frontend/src/pages/admin/__tests__/AdminAuditLogsPage.test.tsx](../frontend/src/pages/admin/__tests__/AdminAuditLogsPage.test.tsx) | Audit-log viewing/filtering. |
| [frontend/src/pages/admin/__tests__/AdminClickhouseManagementPage.test.tsx](../frontend/src/pages/admin/__tests__/AdminClickhouseManagementPage.test.tsx) | ClickHouse management UI. |
| [frontend/src/pages/admin/__tests__/AdminFamilyStatusesPage.test.tsx](../frontend/src/pages/admin/__tests__/AdminFamilyStatusesPage.test.tsx) | Family-status management. |
| [frontend/src/pages/admin/__tests__/AdminPresetFiltersPage.test.tsx](../frontend/src/pages/admin/__tests__/AdminPresetFiltersPage.test.tsx) | Preset-filter CRUD. |
| [frontend/src/pages/admin/__tests__/AdminVariantTagsPage.test.tsx](../frontend/src/pages/admin/__tests__/AdminVariantTagsPage.test.tsx) | Variant-tag management. |
| [frontend/src/pages/admin/__tests__/DataManagementPage.test.tsx](../frontend/src/pages/admin/__tests__/DataManagementPage.test.tsx) | Data-management workflows and family embedding. |
| [frontend/src/pages/admin/__tests__/GeneReferenceAdminPage.test.tsx](../frontend/src/pages/admin/__tests__/GeneReferenceAdminPage.test.tsx) | Gene-reference data management. |
| [frontend/src/pages/admin/__tests__/MonarchDataAdminPage.test.tsx](../frontend/src/pages/admin/__tests__/MonarchDataAdminPage.test.tsx) | Monarch data sync. |

### Discovery / catalog / other pages
| Test file | Purpose |
| --- | --- |
| [frontend/src/pages/genes/__tests__/GeneInfoPage.test.tsx](../frontend/src/pages/genes/__tests__/GeneInfoPage.test.tsx) | Gene info page (transcripts, phenotype). |
| [frontend/src/pages/panels/__tests__/GenePanelDetailPage.test.tsx](../frontend/src/pages/panels/__tests__/GenePanelDetailPage.test.tsx) | Gene-panel detail (member filtering/editing). |
| [frontend/src/pages/panels/__tests__/GenePanelsPage.test.tsx](../frontend/src/pages/panels/__tests__/GenePanelsPage.test.tsx) | Gene-panels list (search/filter). |
| [frontend/src/pages/product/__tests__/NewFeaturesPage.test.tsx](../frontend/src/pages/product/__tests__/NewFeaturesPage.test.tsx) | New-features / releases page. |
| [frontend/src/pages/projects/__tests__/ProjectsPage.test.tsx](../frontend/src/pages/projects/__tests__/ProjectsPage.test.tsx) | Projects list (creation/filter). |
| [frontend/src/pages/reference/__tests__/ReferenceCatalogPage.test.tsx](../frontend/src/pages/reference/__tests__/ReferenceCatalogPage.test.tsx) | Reference-genome catalogue browsing. |
| [frontend/src/pages/settings/__tests__/SettingsPage.test.tsx](../frontend/src/pages/settings/__tests__/SettingsPage.test.tsx) | User settings/preferences. |
| [frontend/src/pages/docs/__tests__/ReferenceDocPage.test.tsx](../frontend/src/pages/docs/__tests__/ReferenceDocPage.test.tsx) | In-app reference doc page (anchored nav). |
| [frontend/src/pages/docs/__tests__/UserGuidePage.test.tsx](../frontend/src/pages/docs/__tests__/UserGuidePage.test.tsx) | In-app user-guide page (contents/workspace links). |

---

## Regulatory traceability

For the in-house IVD technical file, tests are traced **from requirements** in
[TF-09b — Requirements Traceability Matrix](regulatory/TF-09b-requirements-traceability-matrix.md)
(each `REQ-…` → implementation → verifying test → hazard) and the verification strategy is in
[TF-09 — V&V Plan](regulatory/TF-09-verification-validation.md). This document is the
complementary file→purpose index.

## Keeping this current

This catalogue is maintained by hand, but a **CI guard enforces it**: the `catalogue` job runs
[`scripts/check-test-catalogue.sh`](../scripts/check-test-catalogue.sh), which fails if any test
file in the tree is missing from this document — or if this document references a test file that
no longer exists. Run it locally before pushing:

```bash
./scripts/check-test-catalogue.sh
```

To regenerate the file list + per-file test counts when adding/removing tests:

```bash
# backend
for f in $(git ls-files 'tests/*.py' 'backend/tests/**/*.py' 'backend/tests/*.py' | grep -E 'test_.*\.py$' | sort); do
  printf '%s\t%s\n' "$(grep -cE '^\s*(async )?def test_' "$f")" "$f"; done
# frontend
for f in $(git ls-files 'frontend/src/**/*.test.ts' 'frontend/src/**/*.test.tsx' | sort); do
  printf '%s\t%s\n' "$(grep -cE '\b(it|test)\(' "$f")" "$f"; done
```

When a test file is added, add a row to the relevant section here and (if it verifies a
technical-file requirement) update [TF-09b](regulatory/TF-09b-requirements-traceability-matrix.md).
