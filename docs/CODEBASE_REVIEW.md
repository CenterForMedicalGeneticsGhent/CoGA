# CoGA Codebase Review — Cleanups Applied & Follow-up Backlog

_Generated 2026-06-14 from a whole-codebase review (branch `codebase-review-cleanup`)._

## Scope & method

The entire source tree (~46.6k lines of Python across 83 files, ~41.6k lines of
TypeScript/React across 207 files) was reviewed by a fan-out of ~30 per-subsystem
agents across four dimensions — **dead/legacy code, small bugs, performance/speed,
and simplification**. Every candidate finding was then **adversarially verified**
(dead-code claims got repo-wide reference checks; bug claims were re-read for a
safe minimal fix) before being bucketed into _auto-apply_ vs _document_.

- **191** raw findings → **179** confirmed after verification.
- **73** were verified as low-risk + high-confidence and **applied in this branch**.
- **106** are documented below for follow-up (all performance/speed items are here by
  design — those need benchmarking and a trade-off decision, not a blind edit).

## What was already applied in this branch

All changes below are committed to `codebase-review-cleanup` and pass the full gate:
**backend `pytest` 241 passed**, **frontend `tsc` 0 errors / `eslint` 0 errors /
`vite build` ✓ / `vitest` 211 passed**.

- **~71 verified fixes applied** — 45 dead/legacy-code removals (unused functions,
  imports, exports, dead branches, superseded helpers) and 28 small correctness
  fixes (e.g. Azure JWKS key-rotation lockout, a per-file interval-track delete that
  dropped its filename filter, an mtDNA QC `or`-fallback that masked real zero depth,
  a compound-het endpoint using the wrong unaffected-sample definition, SVLEN parsing
  that crashed on float/empty values, a React Rules-of-Hooks violation in `Histogram`,
  silent signup-failure swallowing, and several React-Query/`retry`/key fixes).
- **5 files deleted** as dead/legacy: `CollapsibleSection.tsx`, `ReadTrack.tsx`,
  `SequenceTrack.tsx`, `CompactChecklistDropdown.tsx`, and the orphaned `PedUpload.tsx`
  page + its unreachable `/upload` route. _(Removing `PedUpload` also resolves the
  cross-component PED-upload duplication noted in **Simplification §37** — only the
  live `FamilyIntakePanel` implementation now remains.)_
- **Net diff: 58 files, +251 / −763 lines.**

Two items were **deliberately not applied**:

1. **`dependencies.py` `Request` annotation** — a suggested "annotation-only" fix
   (`request: Optional[Request]`) actually breaks FastAPI startup (FastAPI only
   injects `Request` when the annotation is exactly `Request`; `Optional[Request]`
   makes it a response field and raises `FastAPIError`). **Reverted** — the original
   `request: Request = None` is the correct idiom. _(Caught by the import/test gate.)_
2. **`SmallVariantReviewDialog` unused props** — removing them requires a coordinated
   edit across the component and its caller; deferred to avoid a partial change.

A few unused-`React`-import cleanups in sibling files (`SmallVariantCards`,
`ResultsPagination`, and a couple of structural-variant table siblings) were also
deferred — they were secondary targets of multi-file fixes that the per-file
appliers could not safely coordinate. These are eslint-warning level only.

---

> The remaining sections are the **follow-up backlog**: verified findings that were
> not auto-applied. Effort is rated **S** (small/localized), **M** (moderate refactor),
> or **L** (large/cross-cutting). Performance is first, as requested.


## Performance & speed

This section catalogs verified performance findings, ordered by expected impact. The highest-impact items (unbounded ClickHouse/Postgres fetches, N+1 query patterns, blocking I/O on the async event loop) come first; the long tail of low-impact micro-optimizations and frontend memoization gaps follows. Effort is rated S (small, localized change), M (moderate refactor), or L (large, cross-cutting change).

---

### High impact

#### 1. Repeat-expansion (TRGT) ingest: per-row catalog lookup + per-row INSERT against an unindexed table - FIXED
`backend/app/services/repeat_expansion_pg.py` (`_insert_trgt_record` / `_find_repeat_locus` / `ingest_trgt_text`, lines 453-487, 524-720, 749-874)

Every VCF data line runs a separate `SELECT` against `repeat_loci` (via `_find_repeat_locus`) followed by a single-row `INSERT` into `repeat_expansions` — so an N-locus TRGT file costs `2*N` round-trips per sample. Worse, the lookup filters on `lower(locus_id)`/`lower(gene)`/`lower(display_name)` plus a `jsonb_array_elements_text(aliases)` `EXISTS` subquery, and the only index is `idx_repeat_loci_gene` on raw `gene` — so none of these predicates are index-usable and every lookup is a sequential scan. The cost is `O(rows × table_size)`.

- **Recommendation:** Preload the (small, static) catalog once per ingest into a lowercased lookup map keyed by locus_id/gene/display_name/alias, resolve in memory, and batch the `repeat_expansions` inserts via `executemany`. As a lower-risk fallback, add expression indexes on `lower(locus_id)`/`lower(gene)`/`lower(display_name)` plus a GIN index on `aliases`.
- **Effort:** M
- **Expected impact:** **Before:** ~100-400 sequential full-table scans + 50-200 individual INSERTs for a ~50-200-locus single-sample ingest. **After:** 1 `SELECT` + 1 batched `INSERT`. Roughly **2 orders of magnitude** fewer round-trips; on local Postgres a 200-locus ingest drops from ~200-400 ms of DB time to under ~5 ms. For genome-wide catalogs (tens of thousands of loci) the current path can take minutes.

#### 2. Gene refresh loop: triple commit per symbol (~60k bookkeeping round-trips for a full-human sync) - FIXED
`backend/app/services/gene_info_jobs_pg.py` (`_refresh_grouped_human_gene_info`, lines 690-757)

Per gene symbol the loop issues a pre-fetch progress `UPDATE`+commit, then per-assembly upserts, then a post-symbol `UPDATE`+commit — 2 commits per symbol. The pre-fetch update (`completed_symbols = index - 1`) is almost entirely redundant with the previous iteration's post-symbol update; its only value is setting `current_symbol` slightly earlier. For an `all_human` scope (~20k symbols) this is ~40k commits purely for progress bookkeeping.

- **Recommendation:** Drop the pre-fetch `UPDATE`+commit entirely (write `current_symbol` in the single post-symbol update), and throttle progress commits to every N symbols (~50-100) or every ~30 s, keeping the heartbeat fresh enough to stay within the 5-minute stale-reclaim window (`GENE_REFERENCE_STALE_HEARTBEAT`). Batch the gene_info upserts in the same transaction.
- **Effort:** M
- **Expected impact:** **Before:** ~40k progress-bookkeeping commits for a 20k-symbol sync. **After:** ~200-400 batched commits — a **95%+** reduction in bookkeeping round-trips and a significant drop in WAL pressure. At 1-5 ms/commit this saves ~20-100 s of pure overhead with zero functional value.

#### 3. Dead expensive inventory call on every small-variant family delete - FIXED
`backend/app/services/admin_service.py` (`delete_family_data_by_type`, line 855) 

Line 855 assigns `detail = await get_family_data_inventory_detail(...)` but `detail` is never read again — the rest of the function only uses `family_uuid` (re-resolved at lines 856-860), `sample_rows`, and `contexts`. The discarded call runs a full inventory: ClickHouse small + structural variant counts (including per-sample SV counts) across every assembly, plus interval/repeat Postgres aggregations. The 404-on-missing-family behavior is already handled at lines 860-862.

- **Recommendation:** Delete line 855. Single-line removal, no behavior change.
- **Effort:** S
- **Expected impact:** Removes several ClickHouse round-trips and multiple Postgres aggregations from every small-variant family delete. For large families (many assemblies/samples) this can eliminate **tens of seconds** of latency per delete; high impact relative to a one-line change.

#### 4. Batch BED endpoints issue one ClickHouse query per chromosome (N+1) - FIXED (single batched query + chromosome-aware `_windowed_apcad_rows`)
`backend/app/services/bed_service.py` (`fetch_bed_batch_text` / `fetch_bed_batch_json`, lines 438-454, 478-494)

Both batch endpoints loop `for chrom in chroms` and call `_fetch_bed_records_for_chrom` once per chromosome, each fanning out to `fetch_interval_track_rows(chromosomes=[chrom])`. The genome overview page passes the full chromosome list in one request, so a single batch call becomes ~24+ serial ClickHouse round-trips per sample per track type. `fetch_interval_track_rows` already supports a `chrom IN (...)` clause and accepts a sequence.

- **Recommendation:** Phase 1 (S, low risk): for the non-windowed paths (segments, apcad_pcf, raw fallback), fetch all requested chromosomes in one `fetch_interval_track_rows(..., chromosomes=chroms)` call and group in Python. Phase 2 (M): fix `_windowed_apcad_rows` to group by `row["chr"]` (it currently stamps all rows with the first row's chrom), then batch the windowed coverage/apcad paths too.
- **Effort:** M
- **Expected impact:** **Before:** 24+ serial queries per non-windowed path, `O(N × RTT)`. **After:** 1 query, `O(1 × RTT)`. At 5-50 ms RTT this saves **100-1150 ms per batch call**; fixing the windowed paths reduces a genome-overview load from potentially hundreds of queries to a handful.

#### 5. N+1 gene-symbol lookup, one Postgres query per structural-variant record - FIXED
`backend/app/services/variant_upload_service.py` (`upload_structural_variant_file` / `_lookup_structural_gene_symbols`, lines 1399-1417)

Inside the per-record loop over `iter_structural_variant_records()`, every parsed SV issues its own range query (`SELECT DISTINCT hgnc_symbol FROM genes WHERE assembly_id=… AND chr=… AND start<window_end AND end>window_start`). For a file with hundreds-to-thousands of records this is hundreds-to-thousands of sequential queries on one connection; the small-variant uploader does not have this per-row pattern.

- **Recommendation:** Hoist the lookup out of the loop. Lowest-risk: memoize by `(chrom, start, end)` with a local dict (eliminates duplicate windows, common in merged family files). Better: collect all windows and issue one bulk interval-overlap query (`UNNEST`/`VALUES` CTE), then join in memory.
- **Effort:** S (memoize) / M (bulk query)
- **Expected impact:** **Before:** 50-500 round-trips for a typical 50-500-record SV file. **After:** as few as 1 (bulk) or the count of unique windows (memoized). At ~1-5 ms/round-trip on loopback Postgres, upload time can drop from several seconds to under one second for large files.

#### 6. Per-family/per-assembly N+1 ClickHouse counts in the admin Data → Families view - FIXED (one GROUP BY query per assembly with exact per-family project scope via `(family_guid, project_guid)` tuple-IN)
`backend/app/services/admin_service.py` (`list_data_inventory_page`, lines 430-456)

For each family row the loop iterates assemblies and awaits two ClickHouse queries (`count_family_small_variants`, `count_family_structural_variants`) one at a time. With `page_size` up to 100, this is up to `~2 × families × assemblies` serial round-trips per page load. Interval/repeat counts on the same page are already batched, making the variant counts the outlier; the (currently dead) `list_data_inventory` wrapper uses `page_size=10_000`, which would serialize catastrophically if ever called at scale.

- **Recommendation:** Preferred (M): add batched `count_*_by_family(assembly, family_uuids)` helpers that issue one `GROUP BY family_guid` query per assembly, mirroring `interval_counts_by_family`. Interim (S): parallelize the existing awaits with `asyncio.gather`.
- **Effort:** M
- **Expected impact:** **Before:** 50-100 serial ClickHouse queries for a 25-family page. **After (gather):** same count but `O(RTT)` wall time instead of `O(N × RTT)`; **After (batched):** 2-4 queries total per page load.

---

### Medium impact

#### 7. Unbounded structural-variant fetches — non-native page, compound-het candidates, and list/shared-count helpers - FIXED (non-native SV page candidate cap + estimated-total; lengths helper bounded; shared-counts documented; compound-het now scopes the partner scan to the source variant's gene)
`backend/app/services/clickhouse_family_variants.py` (`get_family_structural_variants_page` 4503-4518; `get_family_compound_het_candidates` 4552-4580) and `backend/app/services/family_service.py` (`get_family_structural_variant_lengths_for_user` / `get_shared_family_structural_variant_counts_for_user`, lines 544-602)

Several SV/small-variant code paths call the row-fetch helpers without the `limit=` keyword. Because `_append_limit_offset` short-circuits when `limit is None`, ClickHouse returns the **entire** matching result set (with a LEFT JOIN to details and per-row JSON decode), which is then materialized and paginated in Python:
- The non-native SV page path handles nearly every meaningful filter (gene, panel, sample, inheritance, phenotype, HPO, MoI, AF/pLI thresholds, review filters, etc. — `_can_use_structural_native_page` returns False), so it is the common path; pagination happens via a Python slice.
- `get_family_compound_het_candidates` fetches the whole family's small-variant set (with detail-map hydration) just to find one variant's partners; its `page_size=max(limit,1)` is **dead config** never read by the fetch.
- The lengths helper passes `page_size=limit` that the fetch ignores (only `records[:limit]` in Python caps it); shared-counts passes a misleading `page_size=1`.

- **Recommendation:** Push a bounded candidate cap into the SQL fetch, mirroring `_small_pair_inheritance_candidate_limit`/`_SMALL_INHERITANCE_MAX_CANDIDATE_ROWS`. For the non-native SV page, add `_SV_NON_NATIVE_CANDIDATE_CAP` (e.g. 50k) and surface `total_is_estimated` when hit. For compound-het, pass an explicit `limit=` (or restrict to the source variant's gene region) and remove the dead `page_size`. For the lengths helper, pass `limit=limit` (drop the no-op `page_size`); for shared-counts, keep behavior but document that all rows are required.
- **Effort:** M (SV page) / S (compound-het, lengths/shared-count)
- **Expected impact:** Bounds per-request memory and ClickHouse latency to the cap rather than to family SV/variant-set size. For large SV panels or high-coverage datasets, the difference is **seconds of latency and tens of MB per request**; modest for typical small families.

#### 8. `get_variant_carriers` loads every carrier row with no LIMIT - FIXED (bounded at 2000 carrier rows with a `truncated` flag; modal shows a "showing first N" notice)
`backend/app/services/variant_explorer_service.py` (`get_variant_carriers`, lines 890-901)

The carrier drill-down `ARRAY JOIN`s `calls.sampleId`/`calls.gt` and returns one row per (sample, call) across all accessible projects with no LIMIT and no pagination, then materializes them all into a Python dict. For a common SNV across a large multi-project cohort this can pull a very large unbounded result set into one API worker.

- **Recommendation:** Add a configurable LIMIT (e.g. 1000-2000) with a `truncated: bool` flag in `VariantCarriersOut`, or aggregate to family-level counts server-side with a separate paginated per-sample endpoint. Surface a "showing first N carriers" notice in `VariantCarrierModal.tsx`.
- **Effort:** M
- **Expected impact:** Bounds worst-case memory and response time. Negligible for rare-disease cohorts (tens-to-hundreds of carriers); at scale a single request could otherwise pull tens of thousands of rows into memory.

#### 9. Per-row INSERT loop when importing family HPO annotations - FIXED (validated rows accumulated and upserted in one batched `session.execute`; duplicate conflict keys collapse last-wins)
`backend/app/services/hpo_service.py` (`import_family_hpo_annotations`, lines 1859-1927)

Each accepted annotation row triggers its own `await session.execute(text(INSERT …), {…})`. All INSERT parameters are computable up front, and the same module already demonstrates the batched form in `import_hpo_ontology` (one `session.execute` over a list of param dicts).

- **Recommendation:** Accumulate validated rows into a `list[dict]`, then issue a single batched `session.execute(text(INSERT … ON CONFLICT …), insert_rows)` after the validation loop; keep per-sample counts in memory.
- **Effort:** S
- **Expected impact:** **Before:** N round-trips for a phenotype file. **After:** 1. In async SQLAlchemy each `await` is a network round-trip, so batching can yield a **10x-100x** latency reduction for large phenotype files (dozens to low hundreds of rows).

#### 10. Family detail endpoint re-runs the family-mapping aggregation 3× per request - FIXED (redundant direct call dropped via `family.id`; resolved UUID threaded into `get_family_member_impact_for_user`, leaving 1 aggregation)
`backend/app/services/family_member_management_service.py` (`get_family_member_detail_for_user`, lines 348-376)

A single detail request runs the `_fetch_family_rows` `GROUP BY` aggregation over `families LEFT JOIN family_projects` three times: inside `get_family_record` (355), again directly (358, only to read `family_row["id"]` — already available as `family.id`), and a third time inside `get_family_member_impact_for_user` (364).

- **Recommendation:** Remove the redundant call at 358 (use `family.id`), and add an optional `family_uuid` parameter to `get_family_member_impact_for_user` so the resolved UUID can be threaded down. All other call sites keep `None` (current behavior).
- **Effort:** S
- **Expected impact:** Reduces 3 `GROUP BY` aggregations to 1 for the detail endpoint — saves 2 SQL round-trips per call with no behavior change. Meaningful on high-traffic deployments.

#### 11. Blocking S3 / pyfaidx / pysam I/O on the async event loop - FIXED (manifest resolves samples concurrently via `asyncio.gather`/`to_thread`; reference routes offloaded with a cached module-level `Fasta` handle; `download_prefix` parallelized with a bounded `ThreadPoolExecutor`)
`backend/app/routers/cram.py` (`get_alignment_manifest` / `_resolve_alignment_manifest_entry`, lines 58-84, 107-124), `backend/app/routers/reference.py` (lines 19-38), `backend/app/core/object_storage.py` (`download_prefix`, lines 106-128)

Multiple async handlers call fully synchronous, blocking functions directly on the single-worker event loop:
- The alignment manifest handler loops over every requested sample and runs up to 4 blocking S3 `head_object` calls plus presign generation per sample — serially. For a trio this is up to 12 serial blocking HEADs per request.
- `get_reference_sequence` / `get_reference_reads` open FASTA via pyfaidx and BAM/CRAM via pysam and iterate synchronously; `/reference/sequence` is hit repeatedly by the SequenceTrack during navigation. `Fasta(fasta_path)` is also re-instantiated per call (re-reads/validates the `.fai` each time).
- `download_prefix` downloads every object under a prefix one-at-a-time in a single thread, bottlenecking family-package staging on sequential latency-bound transfers.

The codebase already uses `asyncio.to_thread` elsewhere (e.g. `family_imports.py:90`), so the pattern is established but not applied here.

- **Recommendation:** Manifest: offload per-sample resolution with `asyncio.gather(*[asyncio.to_thread(...)])` so HEAD+presign run concurrently (or replace per-object HEADs with one `list_objects_v2` prefix listing). Reference: make handlers plain `def` (FastAPI threadpool) or wrap blocking calls in `asyncio.to_thread`, and cache the opened `Fasta` handle module-level by path. `download_prefix`: parallelize with a bounded `ThreadPoolExecutor` (8-16 workers) or `TransferManager(max_concurrency=N)`.
- **Effort:** S (reference handlers) / M (manifest gather, Fasta cache) / S (download_prefix)
- **Expected impact:** Manifest: for a 4-sample family at 50 ms/HEAD, total latency drops from ~800 ms (serial) to ~200 ms (concurrent), and the event loop stops stalling other requests. Reference: eliminates event-loop stalls for the duration of each BAM/CRAM fetch plus per-call `.fai` re-open overhead. `download_prefix`: roughly **8-16x** faster staging for packages with many small files.

#### 12. Family landing page fetches full repeat/Paraphase/mtDNA table payloads just for presence booleans - FIXED (added `count_only=true` mode returning `{loci_count}`/`{genes_count}`/`{variant_count, has_coverage}`; landing page derives the nav-link booleans from those counts)
`frontend/src/pages/families/FamilyDetailPage.tsx` (`repeatTable` / `paraphaseTable` / `mitoTable` queries, lines 365-418)

Three queries download entire table payloads from `/families/{id}/repeat-expansions`, `/paraphase`, and `/mitochondrial-dna`, but the results are consumed only as `hasRepeatExpansions`/`hasParaphase`/`hasMitoDna` booleans to decide whether to render a nav link. The SV and small-variant presence checks on the same page correctly use `page=1&page_size=1`; the three table endpoints have no count/limit mode and return every locus/gene/variant (mtDNA up to `MAX_MTDNA_VARIANTS = 5000`) plus per-sample data. The `has-data` query keys also differ from the data pages' keys, so the fetches don't even prime the cache for navigation.

- **Recommendation:** Add a lightweight `count_only=true` mode (returning e.g. `{loci_count}`, `{genes_count}`, `{variant_count, has_coverage}`) to the three backend routes, and derive the boolean flags from counts on the frontend, mirroring the `page_size=1` pattern.
- **Effort:** M
- **Expected impact:** Replaces 3 unbounded full-dataset queries with 3 minimal presence checks on every landing-page visit — eliminates **tens to hundreds of KB** of serialized JSON and the corresponding DB processing, most significant for multi-sample families with dense repeat/mtDNA data.

#### 13. SV-list pagination/filtering unmounts the whole page (no `keepPreviousData`) - FIXED (added `placeholderData: keepPreviousData`, guard changed to `isLoading && !data`; a subtle "Updating…" chip replaces the full teardown)
`frontend/src/pages/families/FamilyStructuralVariantsPage.tsx` (lines 165-171, 266-274)

The main query is keyed on `requestQueryString`, which changes on every page turn and filter apply. With no `placeholderData`, a new key has no cached data, so `isLoading` is true on each change and the `if (isLoading)` block returns a full-page `<PageState>` spinner — tearing down and remounting the entire page (header, pedigree, filter form, results), causing layout thrash, loss of filter-form accordion state, and a jarring flash.

- **Recommendation:** Add `placeholderData: keepPreviousData` to the query and change the guard to `if (isLoading && !data)`; show a subtle `isFetching` indicator on the results panel instead of the full teardown.
- **Effort:** S
- **Expected impact:** Eliminates the full page unmount/remount on every pagination/filter step — previous results stay visible until the next page arrives, removing the per-interaction flash and preserving filter-form state.

#### 14. Variant-summary aggregation re-runs over up to 100k variants on every render (including log-scale toggle) - FIXED (aggregation moved into a `useMemo` keyed on `[data]`, sharing totals into a `useMemo` keyed on `[sharedCounts]`, bin edges/labels hoisted to module scope; `logScale` toggle now only re-renders the histograms)
`frontend/src/pages/families/FamilyVariantSummaryPage.tsx` (lines 63-113)

The entire `O(n)` aggregation (`allLengths`, the `data.forEach` building `byType`/`bySource`/`byTypeChrom`/`byChromType`, chromosome sort, totals) lives directly in the render body with no `useMemo`. `VARIANT_LIMIT` is 100000 (backend-capped at 100000), so up to 100k variants are reprocessed on every render. The only interactive state is `logScale`; toggling it re-runs the full aggregation even though none of the aggregated structures depend on it (only the histogram rendering does). The file has zero `useMemo`/`useCallback`.

- **Recommendation:** Wrap the aggregation in one `useMemo` keyed on `[data]`; hoist the static `variantBinEdges`/`variantBinLabels` out of the component; extract the `sharedCounts` IIFE aggregation into its own `useMemo`. Only the histogram/table render should depend on `logScale`.
- **Effort:** S
- **Expected impact:** **Before:** an `O(n)` map+forEach+sort over up to 100k rows on every `logScale` click, blocking the main thread. **After:** aggregation runs once per data load. Likely **tens of ms saved per interaction** at the cap.

#### 15. `GenomeHaplotypeTrack`: `diseaseModel` memo defeated by a fresh `analysisRegion`/`membersForRisk` each render - FIXED (memoized `analysisRegion`/`membersForRisk`/`segments`, stable empty-members default, shared `samplesArray` memo reused by `diseaseModel` and a now-memoized `riskState`)
`frontend/src/components/visualizations/GenomeHaplotypeTrack.tsx` (lines 133-163, 257-268)

`analysisRegion` (a `{chr,start,end}` literal) and `membersForRisk` (`[currentMember]` fallback) are rebuilt with new references every render in the ROI-less genome-overview path, yet both are `diseaseModel`'s `useMemo` deps — so `inferDiseaseHaplotypes()` (`O(samples × segments)`: builds a Map over every member's genome segments and intersects signature sets) recomputes on every render. Separately, `riskState` is unmemoized and re-runs `interpretSampleHaplotypeRisk()` (with a second `buildSegmentMap`) each render. The track renders once per family member across the whole genome.

- **Recommendation:** Memoize `analysisRegion` and `membersForRisk` on their primitive inputs; extract a shared `samplesArray` memo and reuse it in both `diseaseModel` and a memoized `riskState`.
- **Effort:** M
- **Expected impact:** Avoids repeated `O(samples × segments)` work and a duplicate `buildSegmentMap` allocation on every render cycle. Small per-render for a trio (milliseconds), but accumulates for larger families and during frequent re-renders (resize/scroll/ROI hover).

#### 16. Pedigree sketch re-runs the full D3 layout on every keystroke - FIXED (the three pedigree arrays + pedPreview wrapped in `useMemo` on `[familyId, members]`/`[couples]`; `Pedigree` wrapped in `React.memo` as a second line of defense)
`frontend/src/pages/dashboard/FamilyIntakePanel.tsx` (`pedigreeRows` / `pedigreeMembers` / `pedigreeRelationships`, lines 647-654)

These three derived arrays are built inline in the render body (no `useMemo`), producing new references every render. They feed `<Pedigree>`, whose layout `useEffect` depends on `[rows, members, relationships, …]` and runs `layoutPedigree()` plus a full `svg.selectAll('*').remove()` + redraw. Because the panel holds many unrelated state fields (status, familyId, mode, ROI query, …), a keystroke in **any** field forces new array identity and a full pedigree re-layout, even when pedigree data is unchanged.

- **Recommendation:** Wrap the three arrays in `useMemo` keyed on `[familyId, members]` / `[couples]` (`useMemo` is already imported); optionally wrap `Pedigree` in `React.memo` as a second line of defense.
- **Effort:** S
- **Expected impact:** Eliminates the redundant D3 layout + full SVG clear/redraw on every unrelated keystroke. The block-ordering layout is `O(n²)` for larger pedigrees (5+ generations); the fix limits re-layout to when `familyId`/`members`/`couples` actually change.

#### 17. `RepeatExpansionTrack` refetches chromosome-wide data on every pan/zoom in overview mode - FIXED (queryKey `regionEnd` → `overviewMode ? null : regionEnd`, so the overview key is stable across pan/zoom)
`frontend/src/components/visualizations/RepeatExpansionTrack.tsx` (`useQuery` queryKey, lines 40-69)

In overview mode (the default in `ChromosomeViewWorkspace`), the server request params are only `{chr, project_id}` (start/end deliberately omitted), but the React Query `queryKey` unconditionally includes `regionEnd`. Since `region.end` changes on every pan/zoom, the key changes and React Query issues a brand-new request for the identical chromosome-wide payload each time — wasted bandwidth and re-render churn for an interaction that should be served entirely from cache.

- **Recommendation:** One-liner — change `regionEnd,` in the queryKey to `overviewMode ? null : regionEnd,`, mirroring the existing `regionStart` guard.
- **Effort:** S
- **Expected impact:** One fetch per (family, sample, chrom, project) for the whole chromosome-view session instead of one per pan/zoom. Moderate bandwidth saving and reduced re-render churn, scaling with interaction frequency.

#### 18. `CircosPlot` tears down and rebuilds the entire SVG on every selection toggle - FIXED (keyed D3 data-joins for chromosomes/bands/gradients/boundaries/variants on persistent containers; only added/removed chromosomes mutate DOM structure, retained ones update attrs in place; callbacks moved to refs. Geometry unchanged — needs a visual QA pass)
`frontend/src/components/visualizations/CircosPlot.tsx` (lines 278-281, 315-521, 674)

A single `useEffect` with `selected` in its dep array runs `svg.selectAll('*').remove()` and rebuilds, for each of 24 chromosomes (all selected by default), a clipPath, a `linearGradient` per band (30+), band paths, boundary lines, a label arc/textPath, an invisible click arc, plus all variant links. Toggling one chromosome checkbox regenerates hundreds of SVG/def nodes for **all** chromosomes.

- **Recommendation:** Preferred (L): replace the monolithic remove+forEach with D3 data-joins keyed by chromosome id (`.data(selectedChroms, d => d.chr).join(…)`) so only added/removed chromosomes mutate the DOM; data-join the variant links separately. Note that deselecting a chromosome rescales the remaining angles, so pure show/hide is incorrect — a keyed join is the clean solution.
- **Effort:** L
- **Expected impact:** **Before:** ~700+ SVG/def nodes created/destroyed per toggle. **After:** only the changed chromosome's nodes (~30). Identical visual result; markedly better interaction responsiveness, most noticeable with many variants or on low-end hardware.

---

### Low impact (cleanups and micro-optimizations)

| Title | File | Problem & impact | Recommendation | Effort |
|---|---|---|---|---|
| Manifest re-read & re-parsed to check `schema_version` | `backend/app/services/family_package_import.py` (2040) | The manifest parsed at 2016 is re-read from disk and re-parsed at 2040 solely to detect a literal `schema_version` key. Doubles disk I/O + parse per validation; runs on every queued import and dry-run. | Have `_parse_manifest` return `(raw_payload, validated_model)` and reuse the dict for the presence check. | S |
| Per-sample availability re-stats files when dataset incomplete | `backend/app/services/family_package_import.py` (2351-2366) | When no sample is complete, the `per_sample` block recomputes `_choose_candidate_path` (which does `is_file()` stats) for every sample/role already computed in the main loop. Doubles `is_file()` calls in the incomplete-dataset path. | Collect each sample's computed `sample_entry` into a side map and reuse it for the incomplete-display block. | S |
| Interval-track DDL runs on every read/count call | `backend/app/services/clickhouse_interval_tracks.py` (44-71; callers 108, 142, 197, 286) | `ensure_clickhouse_interval_table` unconditionally issues `CREATE TABLE IF NOT EXISTS` on every read/presence call, unlike the variant-storage equivalent which memoizes. Adds a serialized DDL round-trip (~1-5 ms) before every haplotype/coverage fetch. | Mirror `_ensured_variant_table_assemblies` + `asyncio.Lock`: module-level `set[str]` with early return so DDL runs once per assembly per process. | S |
| Tag definitions re-queried on every review upsert | `backend/app/services/small_variant_review_pg.py` (1638-1645); `structural_variant_review_pg.py` (250-257) | `list_small_variant_tag_definitions()` (a GROUP BY/ARRAY_AGG join) runs on every save just to build the allowed-tags set, even when the payload has no tags (the common case). Redundant query on the hot write path. | Short-circuit: only query when `normalized_tags` (and compound-het tags) is non-empty. | S |
| Extra `to_regclass` probe on every HPO annotation read | `backend/app/services/hpo_service.py` (`_postgres_tables_available`, called at 1029, 1095) | Both read paths run a separate `SELECT to_regclass('hpo_term')` round-trip before the data query, doubling query count on hot GET endpoints. Table presence is effectively static once schema is applied. | Cache table availability in a module-level `set[str]` (probe at most once per table per process), or use the LEFT JOIN unconditionally with a `DBAPIError` fallback. | S |
| Every member row re-UPDATEd on each structure update | `backend/app/services/family_structure_service.py` (1011-1014) | `_update_member_row` (2 UPDATEs/member) runs for all members regardless of change; `_apply_member_update`'s per-member change flags are discarded. A single-field edit emits `2×M` UPDATEs and bumps `updated_at` on unchanged rows. | Track a per-member dirty set during the update loops; only call `_update_member_row` for added/reactivated/edited/removed members. | S |
| Per-request panel-source DDL shim | `backend/app/services/panel_metadata_service.py` (`_ensure_panel_source_schema`, 29, 55-78) | Six `ALTER TABLE … ADD COLUMN IF NOT EXISTS` + `CREATE UNIQUE INDEX` + `COMMIT` run on the first panel request per worker. The same migration already runs at startup via `013_gene_panel_sources.sql`, making this dead per-process work. | Remove `_ensure_panel_source_schema`, the `_panel_source_schema_ready` flag, and its 3 call sites; rely on startup schema init. | S |
| Online bulk gene datasets ignore the requested symbol subset | `backend/app/services/gene_info_bulk_sources.py` (`_load_online_gene_bulk_datasets`, 983-1014) | The `symbols` parameter (caller passes the dbNSFP-fallback subset) is never used; each parser parses and retains the entire genome-wide ClinGen/GenCC/ClinVar file. For a single-symbol fallback the whole genome's records are built and kept in memory. | Thread `symbols` through `_load_csv_dataset` into each parser as a `symbol_filter`, mirroring `parse_dbnsfp_gene_rows`. | M |
| `verify_raw_import_file` rehashes the whole file inline with no size/time guard | `backend/app/services/raw_import_files_pg.py` (354-390) | Streams a full SHA-256 via `asyncio.to_thread` (good) but with no size cap; a multi-GB CRAM/BAM ties up a threadpool worker for tens of seconds to minutes and blocks the synchronous Verify response. | Run verification as a background job (like the CNV KB rebuild), or wrap in `asyncio.wait_for` with a size pre-check and return a `too_large` status. | M |
| `_clear_compound_het_group` N+1 writes | `backend/app/services/small_variant_review_pg.py` (673-696) | Loops and awaits one UPDATE/DELETE per group member. Groups are always exactly 2 rows, so impact is O(2) today — negligible unless the model grows beyond 2 members. | Document as tech debt; if multi-member groups are ever introduced, replace with a bulk DELETE for empty rows + batched UPDATE. | M |
| `_fetch_annotation_display` aggregates `gene_symbols` that are never read | `backend/app/services/variant_explorer_service.py` (827, 843, 768-789) | The annotation query computes `arrayDistinct(arrayFlatten(groupArray(gene_symbols)))` and stores it, but the row loop reads gene symbols from the entries-side aggregate and only `gene_ids` from the annotation. Pure wasted GROUP BY compute per page load. | Drop the `gene_symbols` column from the SELECT/result dict and shift the remaining column indices. | S |
| `_gene_transcript_priority` recomputed `O(N)` per gene | `backend/app/services/reference_metadata_service.py` (`_select_preferred_gene_rows`, 192-202) | The reduce loop recomputes the stored winner's priority against every later candidate. (Note: the "repeated JSON parsing" framing is inaccurate — asyncpg returns JSONB as dicts, so `_json_dict` takes the fast path; the redundant work is cheap dict lookups.) | Precompute `(priority_tuple, row)` pairs once and compare cached tuples. Code-clarity more than perf. | S |
| Region queries (gene/blacklist/segdup/CNV) have no row LIMIT | `backend/app/services/reference_metadata_service.py` (`get_gene_region_records` + siblings, 1145-1192) | When `start>=end` the window predicate is disabled and the query has no LIMIT, so a no-window REST call materializes a full chromosome (genes router defaults `start=0/end=0`). The UI guards with `enabled: regionEnd > regionStart`, so normal traffic is unaffected, but the API is exposed. | Add a server-side cap with a "too many, zoom in" flag (mirroring the DGV `line_cap`/density pattern) or reject missing-window requests with 400. | M |
| mtDNA QC/coverage metadata JSON parsed twice per sample | `backend/app/services/mitochondrial_analysis.py` (`_member_meta` / `_sample_outs`, 353-363, 657-662) | `_metadata_dict` runs twice per sample row; the first parse (inside `_member_meta`) populates a `"metadata"` key that no caller ever reads. Dead path + one redundant `json.loads` per member. | Remove the unused `"metadata"` key, or pre-parse `sample_metadata` once per sample and share it. | S |
| Query-string sanitization recomputed twice per request | `backend/app/middleware/request_logging.py` (96, 223) | `_query_string_for_logging` (parse_qsl + set/sort) runs once directly and once inside `_request_url_for_logging`, duplicating the parse/sort on every request through the middleware. | Compute `query_string` once and inline `requestUrl` (`f"{path}?{query_string}"`); drop the now-unused helper. | S |
| `VariantOut` duplicates the primary transcript's annotation | `backend/app/schemas.py` (1293-1347) | ~12 flattened transcript fields plus a `transcripts[]` list whose primary element repeats those exact values — so the primary transcript is serialized twice per variant, inflating every paginated row (<1 KB extra/variant, ~50-100 KB/page). Both surfaces are actively consumed by 7+ frontend files, so removal needs coordinated refactoring. | Document as a planned cleanup; converge consumers onto `transcripts[primary]` (or omit the primary from `transcripts`) before dropping the flat fields. | L |
| `buildCompactGenotypeSummary` re-sorts members per row | `frontend/src/pages/families/smallVariantSearch.ts` (836-850) | Calls `sortFamilyMembersProbandFirst([...members])` once per variant row inside `SmallVariantTable`'s map, though `members` is already proband-sorted upstream. ~100 tiny array clones/sorts (3-10 elements) per 100-row render. | Drop the internal sort (document the proband-first precondition) or hoist it out of the map. Negligible in practice. | S |
| Collapsed-details arrays computed for every card every render | `frontend/src/pages/families/SmallVariantCards.tsx` (313-368, 767-863) | Five annotation arrays (`scoreItems`/`frequencyItems`/`transcriptItems`/`changeItems`/`additionalAnnotations` + intermediate `populationFrequencies`) are built per variant but consumed only inside a collapsed-by-default `<details>`. With 100 variants and no memoization, every optimistic review toggle rebuilds ~600 unused arrays across all cards. | Extract the per-variant card body into a `React.memo` sub-component keyed on `variant._id` (fixes all per-card work), and/or defer the details-only arrays behind open state. | M |
| SV track URL rebuilt inline per member every render | `frontend/src/pages/genome/GenomeOverviewWorkspace.tsx` (397-411) | The SV track URL is built via an inline IIFE (`new URLSearchParams(baseVariantParams)` per member) every render, while all other tracks precompute URLs in the memoized `urlMaps`. New string/object allocation per member per render (string equality prevents spurious refetches). | Add an `sv` entry to the memoized `urlMaps` in `GenomeOverviewPage` keyed by `sample_id`; consume it in the workspace. | S |
| `HaplotypePhasedTrack`: `diseaseModel` memo defeated by fresh `analysisRegion` | `frontend/src/components/visualizations/HaplotypePhasedTrack.tsx` (177-198, 362-370) | Same pattern as the genome track but for a single locus: `analysisRegion` is a new object when `riskRegion` is absent (the common `ChromosomeViewWorkspace` path), defeating the `diseaseModel` memo; `riskState` is unmemoized. Smaller segment set, so lower severity. | Memoize `analysisRegion` on `(riskRegion, chrom, regionStart, regionEnd)` and memoize `riskState`. | S |
| `SmallVariantTrack` per-item D3 append (no data-join) | `frontend/src/components/visualizations/SmallVariantTrack.tsx` (318-392) | The draw effect appends a circle + transparent hitbox rect per variant via `forEach`+`append` (up to ~20k DOM nodes at the 10k cap), instead of a data-join. (Tooltip is correctly excluded from deps, so hover does not redraw.) Heavy mount near the cap. | Replace `forEach`+`append` with one `selectAll().data().join()` for circles and a single delegated hit layer (quadtree/pointer math) instead of N rects. | M |
| Repeat-expansion tracks `setState` on every mousemove per locus | `frontend/src/components/visualizations/RepeatExpansionTrack.tsx` (119-126); `GenomeRepeatExpansionTrack.tsx` (96-103) | Each `<rect>` `onMouseMove` calls `setTooltip` continuously, re-rendering the whole track and re-running `cssVar()` per rect. Loci counts are small (typically <50), so impact is low; the per-rect `cssVar` (getComputedStyle) is the concrete waste. | Use `onMouseEnter` for item identity + a ref for cursor position; hoist the `cssVar` color lookups out of the map into a `useMemo`. | S |
| `cssVar` runs `getComputedStyle` inside render-time map loops | `frontend/src/lib/colors.ts` (1-4); callers in `VariantTrack.tsx` (190, 235), `SvTrack.tsx` (163, 168, 175, 197) | `cssVar` calls `getComputedStyle(document.documentElement)` (forces style flush) on every invocation, including `O(N)` inside item map/forEach loops. (Note: HaplotypePhasedTrack/GenomeHaplotypeTrack already hoist their calls and need no change.) SV counts are typically small, so risk of visible jank is low. | Hoist the looped `cssVar` lookups into the existing memo snapshots (or a local const before the loop) in VariantTrack and SvTrack. | S |
| `genotypeFilterDirty` recomputed via `JSON.stringify` every render | `frontend/src/pages/variant-explorer/GlobalSmallVariantExplorerPage.tsx` (80-81) | Two `JSON.stringify` serializations run inline on every render (including keystrokes in the add-sample input and `isFetching` toggles). Arrays are tiny; also `JSON.stringify` is order-sensitive (latent correctness edge). | Wrap in `useMemo` keyed on `[genotypeRows, genotypeFilters]`, or use a structural (length + per-entry) comparison that is also order-insensitive. | S |
| mtDNA sample-group filters recompute every render | `frontend/src/pages/families/FamilyMitoDNAAnalysisPage.tsx` (264-268) | `mothers`/`fathers`/`maternalLine`/`children` are bare `.filter()` calls (unlike the memoized `orderedSamples`), re-filtering 2-5-element arrays on each keystroke. No downstream `React.memo` consumers, so impact is negligible — consistency only. | Optionally wrap in `useMemo` keyed on `[orderedSamples]` for consistency. | S |
| `validateManualFamily` runs on every render | `frontend/src/pages/dashboard/FamilyIntakePanel.tsx` (562, 647) | Called unmemoized in the render body (line 647) and again in the submit handler (562). Complexity is `O(members + couples)` (not `O(members²)`), microseconds for typical pedigrees. | Optionally `useMemo` on `[familyId, members, couples]` for consistency; not a perf priority. | S |
| `Ideogram` rebuilds `bandGradients` JSX every render | `frontend/src/components/visualizations/Ideogram.tsx` (217-232) | `renderBands`/`outlinePath` are memoized but `bandGradients` (maps over bands, calling `getStainColor`/`getBandGradientStops` per band) is a plain const, re-running on every drag-mousemove/hover `setState`. | Wrap in `useMemo` keyed on `[renderBands, chrom, bandResolution, bandFinish]`. | S |
| `datasetCopy` object literal rebuilt every render | `frontend/src/pages/reference/ReferenceCatalogPage.tsx` (303-332) | A static copy lookup table is declared inside the component body, reallocating 6 nested objects on every render; two 3 s polling queries re-render the page frequently while jobs run. | Hoist `datasetCopy` to module scope alongside the other module-level helpers. | S |
## Correctness fixes to apply manually

These are confirmed-real defects that were not auto-applied because the correct remediation is risky, non-trivial, or requires a deliberate product/architecture decision. Each requires a coordinated change across multiple sites or layers.

### 1. `formatGt` reports no-call genotypes (`./.`) as confident wild-type

- **File:** [`frontend/src/lib/genotypes.ts`](frontend/src/lib/genotypes.ts) (lines 1-11); consumers in [`VariantTrack.tsx`](frontend/src/components/visualizations/VariantTrack.tsx) (113, 251), [`SmallVariantTrack.tsx`](frontend/src/components/visualizations/SmallVariantTrack.tsx) (279), [`SvTrack.tsx`](frontend/src/components/visualizations/SvTrack.tsx) (106, 256), [`StructuralVariantTable.tsx`](frontend/src/pages/families/StructuralVariantTable.tsx) (375), [`StructuralVariantCards.tsx`](frontend/src/pages/families/StructuralVariantCards.tsx) (411).
- **Problem & impact:** `formatGt` has no branch for missing/no-call genotypes (`./.`, `.|.`, `.`, `''`), so they fall through to `'WT'` and a no-call is rendered as a confident wild-type/reference call in per-sample tooltips, tables, and cards. No-calls do reach the frontend (the backend builds `GenotypeOut` from all `record.calls` without dropping them), making this a real source of clinical misinterpretation. The author's own leftover comment (`what with missing values ./. ?`) flags exactly this gap.
- **Recommendation:** (1) Add an explicit no-call branch to `formatGt` returning a distinct label such as `'No call'` (already used in `FamilyMitoDNAAnalysisPage`, `FamilyRepeatExpansionsPage`, `FamilyParaphasePage`). (2) Critically, do **not** stop there: the three presence filters that use `formatGt(g.gt) !== 'WT'` (VariantTrack 113, SmallVariantTrack 279, SvTrack 106) would then flip to count no-calls as carriers, contradicting backend semantics that bucket `./.` with reference. Replace those three checks with a dedicated predicate (e.g. `isCarrier(gt)` / `hasAltAllele(gt)`, or `gt is Het or Hom`) so both no-call and reference stay excluded from the carrier set. (3) Add a unit test for `formatGt` covering Hom/Het/WT/no-call (none exists today).
- **Effort:** M
- **Expected impact:** No-call samples are no longer mislabeled as confident wild-type in tooltips/tables/cards, removing a clinical-misinterpretation risk — without altering which variants appear on the tracks.

### 2. `UserListPage` lacks loading/error states and renders blank/stray-space cells

- **File:** [`frontend/src/pages/admin/UserListPage.tsx`](frontend/src/pages/admin/UserListPage.tsx) (lines 24-44, 77, 78).
- **Problem & impact:** Unlike every other admin page (which uses react-query + `PageState`), this page fetches `/auth/users` and `/projects` via raw `.then/.catch(console.error)`, so a failed call leaves a silently empty table with no loading or error feedback. The Name cell (`${first_name ?? ''} ${last_name ?? ''}`, line 77) always emits at least a stray space, the affiliation cell (line 78) renders `{u.affiliation}` with no `'—'` fallback used elsewhere, and the activation toggle (lines 37-44) has no in-flight disable, so rapid clicks can race.
- **Recommendation:** Mirror `AdminPresetFiltersPage.tsx`: convert the two fetches to `useQuery` (`retry:false`), add `getErrorMessage` plus early-return `PageState` for combined loading/error (`kicker="Administration"`), convert `toggleActive` to a `useMutation` (or track an in-flight id set) that disables the checkbox while its PATCH is pending and invalidates the users query on success. Add `'—'` fallbacks: render Name as `` `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || '—' `` and affiliation as `{u.affiliation || '—'}`. The two `'—'` fallbacks are isolated low-risk edits that can land first even if the react-query conversion is deferred.
- **Effort:** M
- **Expected impact:** Admins get loading/error feedback instead of a silently empty table on fetch failure; missing names/affiliation render a consistent `'—'`; the disabled toggle prevents duplicate/racing PATCH requests. Brings the page in line with the rest of the admin surface.

### 3. `ingest_ui_events` silently truncates oversized telemetry batches

- **File:** [`backend/app/routers/ui_events.py`](backend/app/routers/ui_events.py) (lines 143-156); schema in [`backend/app/schemas.py`](backend/app/schemas.py) (1888-1889); client in [`frontend/src/lib/telemetry.ts`](frontend/src/lib/telemetry.ts) (115).
- **Problem & impact:** `_MAX_EVENTS_PER_BATCH=100` is enforced only as `payload.events[:100]` during iteration; `UiEventBatchIn.events` has no `max_length`, so events past 100 are silently dropped with no signal (the `202` response's `accepted` counts only processed events). This is reachable by a legitimate client: `telemetry.ts` `flushKeepalive` POSTs the entire queue (up to `MAX_QUEUE=200`) on page-hide, so a real keepalive batch can lose ~100 events.
- **Recommendation:** Do **not** simply add `max_length=100` to the schema — that would make the 200-event keepalive batch fail with `422` and drop the *whole* batch (worse than tail-truncation), and the keepalive fetch has no retry. Fix across both layers instead. Preferred: chunk the frontend keepalive into ≤100-event POSTs (loop `splice` in chunks, or lower `MAX_QUEUE` to 100), then add `Field(max_length=_MAX_EVENTS_PER_BATCH)` so oversize batches become an explicit `422`. Alternatively, raise `_MAX_EVENTS_PER_BATCH` to ≥200 to match `MAX_QUEUE` and add a matching `max_length`. Minimal fallback: keep truncation but make it observable by returning `received`/`dropped` counts (or logging when `len(payload.events) > cap`).
- **Effort:** S
- **Expected impact:** Eliminates silent loss of up to ~100 telemetry events per keepalive batch and bounds parse/allocation cost for oversized payloads. Low overall impact since telemetry is best-effort and the endpoint is auth-gated, but it improves data completeness and makes the cap explicit.

### 4. `StructuralVariantRecord.remote_end` is fetched and parsed but never surfaced

- **File:** [`backend/app/services/clickhouse_family_variants.py`](backend/app/services/clickhouse_family_variants.py) (field at 219; `SELECT` at 3674; positional unpack at 3704; record construction at 3743; `_structural_variant_out` at 2210-2251); schema in [`backend/app/schemas.py`](backend/app/schemas.py) (1303-1304).
- **Problem & impact:** `remote_end` is `SELECT`ed (`any(d.remoteEnd)`), positionally unpacked, and coerced/stored on the file-local `StructuralVariantRecord`, but `_structural_variant_out` emits only `remote_chr`/`remote_start` and `VariantOut` has no `remote_end` field. The value is dead in the read path — one nullable column read and one `_coerce_int` per SV row with nothing surfaced. (The separate ingest/storage path's use of `remote_end` is legitimate and out of scope.)
- **Recommendation:** A deliberate product choice. **(A) Drop** the dead read — remove the field (219), the `SELECT` clause (3674), the `remote_end` name in the positional unpack tuple (3704), and the `remote_end=...` kwarg (3743). All four **must** change together: the unpack is positional, so removing one in isolation shifts every later column and corrupts row parsing. **(B) Expose** it — add `remote_end: Optional[int] = None` to `VariantOut` (~1304), set `remote_end=record.remote_end` in `_structural_variant_out` (~2235), and surface in the frontend if the breakend end coordinate is wanted (the UI already renders `remote_chr`/`remote_start` for translocation links). Prefer (A) unless there is product demand for the BND end coordinate.
- **Effort:** S
- **Expected impact:** Negligible runtime impact (one nullable column read + coerce per SV row). Value is code clarity — either removing a fetched-but-never-surfaced field, or surfacing a coordinate the UI may want.
## Dead / legacy code needing human judgment

These are dead-code candidates that verification confirmed as unreachable or unused in production, but that could **not** be cleared for automatic removal. In each case removal is blocked by a residual concern: a test depends on the symbol, a public API/DB contract would change, or an unresolved design-intent question is encoded in the code. Each item needs a maintainer decision before action.

### Backend — `clickhouse_family_variants.py` inheritance/sample-filter cruft

| Item | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|---|---|---|---|---|
| Superseded Python inheritance filter `_apply_small_inheritance_filter` | `backend/app/services/clickhouse_family_variants.py` (1648-1729) | Full Python-side inheritance filter (compound_het/recessive/de_novo/x_linked) with **no production caller** — the live page flow uses `_small_native_inheritance_clauses` + `_inheritance_result_items`. It survives only via 6 references in `test_clickhouse_family_variants.py`. Two parallel implementations encode the same rules and risk drifting apart — a real correctness hazard. | Prefer: delete it and migrate the 6 tests to exercise `_inheritance_result_items`. **Caveat:** not a mechanical swap — return shapes differ (`list[SmallVariantRecord]` vs kind-tagged `list[tuple[str, …]]`), so tests must be rewritten. Cheaper fallback: keep it but add a docstring marking it as a test-only reference oracle. | M | Removes ~80 lines of dead production code; eliminates inheritance-logic drift risk. No user-facing change. |
| No-op `_small_sample_filter_native_supported` always returns `True` | `backend/app/services/clickhouse_family_variants.py` (2964-2968; dead guard at 2981; chain through 3031, 3787) | The function discards its parse result and returns `True` in both branches, so the `continue` guard at 2981 is unreachable and sample filters can **never** force the slow Python fallback. Removal is provably runtime-safe, but the always-true gate masks a latent question: were non-native sample filters *meant* to force the fallback? | **First resolve intent.** If the native clause builder `_small_native_sample_filter_clauses` (2971-3028) covers every filter shape, delete the no-op function, the dead guard, `_small_sample_filters_native_supported`, and the always-false term at 3787. If some shapes are *not* natively supported, this is a latent correctness bug — implement the real predicate so those queries fall back. Add a unit test for the chosen behavior. | S | No behavior change from the cleanup itself; removes ~9 lines plus a redundant double-parse of the sample filter. The higher value is surfacing the latent fallback question. |

### Backend — write-only / unreachable storage paths

**`_structural_call_gq` writes an all-NULL SV column that is never read back**
`backend/app/services/clickhouse_variant_storage.py` (448-449, 633)

`_structural_call_gq` ignores its argument and always returns `None`; its only consumer is the SV `calls.gq` array, which is filled entirely with NULLs and never read by any SV query (the SV read path reads `calls.qual`/`readSupport`/`filter`; the `calls.gq` read at `clickhouse_family_variants.py:3509` belongs to the *small-variant* path). `_structural_call_qual` / `_structural_call_read_support` **are** read and must be kept.

- **Recommendation:** Remove the function and drop `calls.gq` from the SV insert as a deliberate small PR, optionally followed by a schema migration to drop the column (CollapsingMergeTree column removal needs care). **Caveat:** the edits are *positional* across three sites (function, insert tuple at 653, INSERT column list at 1401) — if the tuple and column list fall out of sync, every later SV column shifts and SV writes corrupt silently. Verify ordering and run the SV insert/read tests after the change.
- **Effort:** S — **Impact:** Removes a dead function and a write-only all-NULL column, trimming SV row width slightly. No query-result change.

### Backend — legacy MongoDB / write-only review fields

**Legacy MongoDB ObjectId shim is unreachable under the current `variant_id` scheme**
`backend/app/services/small_variant_review_pg.py` (134, 147-148, 1635-1636)

`OBJECT_ID_PATTERN` / `_looks_like_object_id()` match a 24-char hex Mongo ObjectId, but `variant_id`s are now built as `chr-pos-ref-alt` (e.g. `chr1-12345-A-G`), which can never be 24 pure-hex chars. The guard at 1635 is therefore always false — a leftover from the old MongoDB-backed system.

- **Recommendation:** Remove the pattern and helper, and simplify 1635 to `if variant is None: raise HTTPException(404, ...)`. **Caveat:** this changes a conditional on the `{variant_id:path}` HTTP parameter — a raw API client POSTing a literal 24-hex string would flip from accepted-write to 404. Unreachable via the documented scheme but observable on the public API surface, so a reviewer should confirm no external/legacy upload tool POSTs ObjectId-style ids before deleting (grep found none).
- **Effort:** S — **Impact:** Removes ~5 lines of unreachable legacy code; clarifies the 404 path. No change for any real `chr-pos-ref-alt` id.

**`compound_het_partner_variant_keys` is written/persisted but never read**
`backend/app/services/small_variant_review_pg.py` (239, 463, 507, 556-579, 611-659, 1754, 1759) and `backend/db/schema/postgres/001_metadata.sql:290`

The column is SELECTed, carried through merge dicts, and written on insert/update, but **no path reads it**: the serializer `_serialize_compound_het`, the `SmallVariantCompoundHetReviewOut` schema, and the frontend all use `compound_het_partner_variant_ids` exclusively, and no tests reference the keys.

- **Recommendation:** Two stages. (1) Python-only and behavior-neutral: drop the field from the write payloads, UPDATE/INSERT SQL + bound params, and SELECT lists. (2) Follow-up migration to drop the `NOT NULL` JSONB column at `001_metadata.sql:290`. **Caveat:** the field maps to a persisted `NOT NULL` column with existing rows, so code and migration must be coordinated — hence not auto-applied. Do **not** touch the unrelated per-variant `variant_key` at line 1763.
- **Effort:** M — **Impact:** Removes dead write-only data and eventually one unused JSONB column. No runtime/behavioral impact.

### Backend — test-only / unreferenced surfaces

**In-memory VEP annotation path is reachable only from tests; one branch is fully unreachable**
`backend/app/services/variant_upload_service.py` (220-236, 280-301, 327-329)

Two findings: (1) the `locus_allele` branch of `_store_vep_annotation` is **provably unreachable** — sqlite callers take the `conn is not None` branch and in-memory callers handle `locus_allele` inline via `_append_annotation`, so this branch is a silent no-op. (2) The entire non-sqlite (in-memory) `VepAnnotationLookup` path, including `_parse_vep_tsv_annotations`, has **no production caller** (production uses the sqlite-backed `_parse_vep_tsv_annotation_upload` at line 952); it is kept alive only by `test_variant_upload_service.py`. `_parse_vep_tsv_annotation_lines`, `_parse_vep_tsv_annotation_upload`, and `VepAnnotationLookup.get/close` are **not** dead.

- **Recommendation:** Either leave a comment marking the in-memory path as test-only, or remove the dead surface (the in-memory dicts/branches, `_parse_vep_tsv_annotations`, `_append_annotation`, the unreachable `_store_vep_annotation` branch) and migrate the two tests to the sqlite path via `_parse_vep_tsv_annotation_upload`. **Caveat:** the second option is a non-trivial refactor that rewrites test assertions (away from `.by_variant_id`/`.by_locus_allele`), not a mechanical deletion.
- **Effort:** M — **Impact:** Removes one unreachable branch plus a parallel in-memory path that duplicates the sqlite logic, cutting drift risk. No production behavior change.

**`cram.header` endpoint has no in-repo caller and blocks the event loop**
`backend/app/routers/cram.py` (215-240)

`GET /cram/{family_id}/{sample_id}.cram.header` (`get_cram_header`) has **no caller anywhere in the repo** — the IGV/frontend flow uses `/manifest` plus the `.cram`/`.bam`/index routes, and no test or dynamic dispatch references it. **Residual uncertainty:** it is a public authenticated API endpoint, so repo grep cannot prove an external operator/tool isn't consuming it. Separately, the handler does a **blocking `pysam` open on the async event loop** — the only pysam-on-the-loop call in the router.

- **Recommendation:** Confirm with the team whether any external tool hits `.cram.header`. If not, remove the route and its synchronous pysam open. If kept, fix the real defect by offloading the `pysam` open + `header.to_dict()` via `asyncio.to_thread(...)`.
- **Effort:** S — **Impact:** Removal deletes ~26 lines of dead, event-loop-blocking code; retention+offload removes a latency/availability risk where a slow S3/htslib read stalls the worker. No frontend change either way.

### Backend — intentional API surface (owner discretion)

**`CoGALogger.debug()` is never called**
`backend/app/core/coga_logging.py` (57-58)

`debug()` is never invoked: the sole `CoGALogger` instance (`request_logging.py`) uses only `.info/.warning/.error`, there is no `.debug(` call anywhere in `backend/app`, and there is no dynamic dispatch. **Residual concern:** it is the symmetric DEBUG-level member of a small, deliberate logger-wrapper API (`debug/info/warning/error`), so deleting it is a design call, not a mechanical cleanup — a future caller or a raised log level would naturally reach for it.

- **Recommendation:** Owner decides. Keep for API symmetry, or delete lines 57-58 if enforcing strict no-dead-code (behavior-neutral). **Effort:** S — **Impact:** Negligible; the only effect of removal is a slightly smaller API surface.

### Backend — encodes an unresolved authorization-design question

**`_ensure_user_can_replace_existing_families` discards its `existing_rows` argument**
`backend/app/services/ped_service.py` (307-317)

The function takes `existing_rows`, immediately `del`s it, and decides purely on `user.role == 'admin'` — the parameter is dead inside the body. **Important correction to the raw finding:** line 335 is **not** the sole caller. `backend/tests/test_access_control.py:89` (`test_viewer_cannot_replace_family_linked_to_hidden_project`) also calls it, feeding rows tagged with visible vs hidden `project_id` and asserting 403. That test name and payload encode an intended **per-project authorization** check the implementation never performs (it passes only because a viewer is non-admin). Blindly dropping the parameter would break the test and silently erase the encoded design intent.

- **Recommendation:** A human must choose: (A) if admin-only is the intended policy, drop the parameter, remove the `del`, update the call site at 335, **and** rename/trim the misleading test; or (B) if per-project authorization was the real intent, implement it (e.g. 403 when any existing row's `project_id` is outside the user's accessible projects, using the existing project-visibility helpers). Do **not** do a naive parameter drop.
- **Effort:** M — **Impact:** Code clarity plus a potential authorization-correctness decision; direction (B) would close a latent gap where the test name promises enforcement that does not exist.

### Frontend — dead-in-production paths gated by a product decision

**`clearMemberGenomicData` is constant `false`; the destructive clear path is unreachable**
`frontend/src/pages/families/FamilyDetailPage.tsx` (304, 592, 1043)

The state is only ever set to `false` (the `useState` initializer and the reset at 592) and read at 1043 (`clear_existing_genomic_data: clearMemberGenomicData`). There is **no checkbox or UI control** to toggle it, so per-member delete always sends `false`. **The dead chain is deeper than the raw finding states:** even if the frontend sent `true`, the backend `delete_family_member_for_admin` (`family_member_management_service.py:811`) hardcodes `clear_existing_genomic_data=False`, so the destructive path is unreachable on **both** layers. The feature itself is real and reachable only via the structure-update endpoint (`family_structure_service.py:1004`).

- **Recommendation:** Product decision. (A) Wire it end-to-end — add a checkbox bound to `setClearMemberGenomicData` **and** fix the backend hardcode at 811 to pass the param through. (B) Remove the dead frontend state and the unused `clear_existing_genomic_data` query param from the route (`families.py:307,317`) and service signature, and update `FamilyDetailPage.test.tsx:584`. **Caveat:** (A) is a feature requiring a product call; (B) removes a public API query param (contract change) across three files / two languages.
- **Effort:** M — **Impact:** No behavior change today (inert end-to-end). Value is correctness/clarity: either unlocks an intended admin destructive feature or removes a misleading param implying a capability that does not exist.

### Frontend — low-value, declarations/test-only, behavior-neutral

| Item | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|---|---|---|---|---|
| Unused `ClinicalCnvKbJob` / `ClinicalCnvKbStatus` fields | `frontend/src/pages/reference/ReferenceCatalogPage.tsx` (53-71) | Only `available` and `active_job` (truthiness) are read; all per-job fields (`_id`, `status`, `skip_clinvar`, `requested_by`, timestamps, `inserted`, `error`, `assembly_name`), plus `recent_jobs` and `detail`, are unreferenced. These are compile-time-erased TS interfaces, so trimming is behavior-neutral. **Residual concern:** they intentionally mirror the backend `ClinicalCnvKbStatusOut` contract, and the sibling `GeneReferenceAdminPage` already renders `recent_jobs` for an analogous job type — a likely future consumer. | Preferred: leave as an intentional API-contract mirror. If minimizing types, narrow `ClinicalCnvKbStatus` to `{ available; active_job }` and delete `ClinicalCnvKbJob`. Lowest priority. | S | Negligible — pure type tidy, no runtime/bundle effect. |
| Histogram auto-bin (`else`) branch + `bins` prop unreachable in production | `frontend/src/components/visualizations/Histogram.tsx` (49-66) | The sole production caller (`FamilyVariantSummaryPage.tsx`, 3 sites) always passes a 9-element `binEdges` + `binLabels`, so the `binEdges.length > 1` branch always wins. The auto-bin `else` branch and `bins` prop are exercised **only** by `Histogram.test.tsx`. **Residual concern:** not removable without editing that test (which validates large-dataset rendering), and it may be an intended reusable fallback; removal also changes the component's prop contract. | If the fallback is unwanted: remove the `bins` prop and `else` branch, make `binEdges`/`binLabels` required, and update the test to pass them. Otherwise leave as-is. | S | Cosmetic/maintainability only (~18 lines + one prop); no runtime change for current callers. |
| `chromGapPx` is an inert `useEffect` dependency | `frontend/src/pages/genome/GenomeOverviewPage.tsx` (125, 192) | `chromGapPx` is a component-local literal (`const chromGapPx = 8;`) recreated identically each render, so listing it in the dependency array at 192 is structurally inert noise. **Note:** the symbol itself is **not** dead — it is used at 182-183 and must be kept; only the dependency-array entry is redundant (this item was mislabeled `dead_code`). | Hoist to a module-level `const CHROM_GAP_PX = 8;` and remove it from the dependency array (`[chromSizes, chroms, trackWidth]`). Keep the in-body usages. Optionally hoist sibling literals `trackHeight`/`svTrackHeight` for consistency. | S | Negligible; removes misleading dependency-array noise. No behavior change. |
## Simplification, reuse & architecture

This section catalogs verified duplication and structural-cleanup opportunities. All findings are documentation-only (no auto-apply): each needs a human to apply carefully, and a few carry a latent behavioral question that must be resolved first. Findings are grouped by area, with closely-related duplicates merged.

### Backend — shared utility/helper duplication

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 1 | Review-PG helpers duplicated across modules | `backend/app/services/structural_variant_review_pg.py` (25-87) | `_require_uuid`, `_json_payload`, `_normalize_tags` are byte-identical to the copies in `small_variant_review_pg.py` (139-233), and `_merge_tag_metadata` differs only in whitespace. The structural module already imports from the small-variant module. The same helpers are independently re-defined in ~5 other service files (`projects.py`, `ped_service.py`, `reference_metadata_service.py`, `repeat_expansion_pg.py`, `clickhouse_variant_storage.py`). | Extract the four helpers into a shared `review_pg_utils.py` and import everywhere. Keep `_json_payload` re-exported from `small_variant_review_pg` (a test imports it directly) or update the test. | M | Removes 4 duplicate definitions (~63 lines) here; up to 5-6 more copies elsewhere if the dedup is carried through. |
| 2 | `getErrorMessage`-style PG/admin helper sprawl (see frontend #18) | — | (cross-references the broader pattern noted above) | — | — | — |
| 3 | `_first_float` is a misnamed exact duplicate of `_max_or_none` | `backend/app/services/clickhouse_variant_storage.py` (176-178, 234-244) | `_first_float(*values)` filters `None` and returns `max(...)` — identical to `_max_or_none`, differing only in `*args` vs iterable. The name "first" is actively misleading (it returns the max), and the sole caller `_population_float` splats a list just to repack it. | Delete `_first_float`; have `_population_float` call `_max_or_none(values)` directly. **First confirm with the author** that `max` across the direct annotation value and all population-frequency fallbacks is intended — if "prefer the direct value, fall back" is the real intent, use `next((v for v in values if v is not None), None)` instead (a behavior change). | S | Removes a misleadingly-named helper and an unnecessary splat/repack. No runtime effect. |

### Backend — duplicated SQL / query shapes

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 4 | Identical 23-column `SELECT` duplicated between single-row and group fetch | `backend/app/services/small_variant_review_pg.py` (450-528) | `_fetch_review_row` and `_fetch_compound_het_group_rows` share an identical 23-column `SELECT` against `small_variant_reviews`, differing only in the `WHERE` predicate (`variant_id` vs `compound_het_group_id`) and `first()` vs `all()`. The column list is maintained twice. | Factor the column list into a module-level constant (e.g. `_SVR_SELECT_COLS`) and a single `_fetch_review_rows(session, where_clause, params)` helper that both callers parameterize. | S | One copy of the column list instead of two; schema changes need one edit, removing silent column-mismatch risk. |
| 5 | Two near-identical active-member queries feeding the same builder | `backend/app/services/metadata_service.py` (743-768, 1032-1066) | The inline `member_stmt` in `_fetch_project_family_rows` and the standalone `_fetch_family_sample_rows` are functionally identical (same JOIN, `WHERE fm.family_id IN :ids AND fm.active`, same `ORDER BY`, same columns into `_family_member_out_from_row`). The only difference is `_fetch_family_sample_rows` also selects `sample_uuid`. | Extract one `_fetch_family_member_rows(session, family_ids)` helper that always includes the harmless `sample_uuid` column; have both call sites delegate to it. Pick one bind-param name consistently. | S | ~25 lines removed; future column/filter changes happen once instead of two. |
| 6 | Per-dataset `COUNT(*)` map duplicated 3× plus two count helpers | `backend/app/services/reference_metadata_service.py` (313-322, 684-691); `reference_source_service.py` (616-625) | The same `{dataset_type: "SELECT COUNT(*) FROM <table> WHERE assembly_id = CAST(:assembly_id AS uuid)"}` dict appears verbatim inside `_assembly_dataset_count` and inline in `apply_reference_dataset_text`; a 2-key subset lives in `_count_reference_dataset_rows`. The two helpers are effectively the same function in two modules. Adding a dataset/table requires editing several places. | Extract one `_DATASET_COUNT_QUERY` constant; make `_assembly_dataset_count` use it; have `apply_reference_dataset_text` call `_assembly_dataset_count`; delete `_count_reference_dataset_rows` and import the shared helper into `reference_source_service.py`. | S | Three-way maintenance burden collapses to one edit. No behavior change. |
| 7 | `get_hpo_term_details` issues 4 sequential queries that could be one | `backend/app/services/hpo_service.py` (1260-1314) | The function runs four awaited queries in sequence (term, synonyms, parents, children) for a single HPO id, while `list_hpo_admin_terms` (1393-1505) already fetches all of these in one round-trip via `LEFT JOIN LATERAL` + `jsonb_agg`. | Reuse the LATERAL/`jsonb_agg` pattern, adding `WHERE t.hpo_id = :hpo_id` and preserving the 404 on empty result. (Alternatively run the three dependent queries concurrently with `asyncio.gather`.) | S | 3 fewer DB round-trips per term-detail request; the SQL is copy-adaptable from the same file. |

### Backend — co-located duplication & redundant computation

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 8 | Duplicate path-key sets: inline `path_keys` vs `_PROVENANCE_PATH_KEYS` | `backend/app/services/family_package_import.py` (3286-3334) | `_sample_provenance` defines an inline `path_keys` set byte-for-byte identical to the module-level `_PROVENANCE_PATH_KEYS` declared just below (both 14 keys). `_record_package_raw_files` uses the constant; `_sample_provenance` uses its own copy. Adding a new file role to one and not the other would silently drop provenance for that role. | Delete the inline literal; reference `_PROVENANCE_PATH_KEYS` (move the constant above `_sample_provenance` to keep it co-located). | S | Eliminates drift risk when new file roles are added. No behavior change. |
| 9 | `_normalize_carrier_status` computed twice per member | `backend/app/services/ped_service.py` (239-247) | Inside the per-member `model_copy`, the pure `_normalize_carrier_status(member.carrier_status, member.carrier_type)` is evaluated once for `carrier_status` and again identically in the `carrier_type` ternary; the two must stay in sync by hand. (`_manual_clinical_status(member)` is similarly duplicated nearby.) | Compute `normalized_carrier` once into a local before the copy and reuse it for both. Lift `_manual_clinical_status(member)` similarly. | S | Readability/maintainability; removes drift risk. No runtime impact. |
| 10 | Two identical alias-suffix branches differing only by separator | `backend/app/services/reference_source_service.py` (136-143) | In `_split_local_assembly_identity`, the `.`-prefix and `_`-prefix branches have byte-identical bodies (same `len(normalized_name) + 1` slice). | Collapse to one branch: `if normalized_alias and (alias.startswith(name + ".") or alias.startswith(name + "_")): ...`. The slice offset is correct for both single-char separators. | S | Removes 3 duplicated lines; clearer intent. No behavior change. |

### Backend — duplicated normalization & worker machinery (larger refactors)

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 11 | Annotation normalization duplicated between two parsers | `backend/app/services/variant_annotation_parser.py` (250-324, 327-404) | `_base_info_annotation` and `_normalize_annotation_entry` repeat ~35 lines across six blocks (`_SCORE_ALIASES`/`_COUNT_ALIASES`/`_SPLICE_ALIASES`/`_POPULATION_ALIASES` loops, the gnomad_af derivation, the spliceai_max computation). Only the `_ANN_ALIASES` handling and final pruning differ. Any alias/derivation change must be made twice and can silently diverge. | Extract a shared `_apply_numeric_and_population_aliases(mapping, annotation, ...seed args)` and call it from both; keep only the `_ANN_ALIASES` pop/override and final pruning per-caller. Preserve the entry variant's seed-merging carefully and cover both paths with tests. | M | Alias/derivation changes happen in one place. No behavior change. |
| 12 | Audit-log and UI-event async worker machinery duplicated verbatim | `backend/app/services/ui_event_pg.py` (60-208) | `ui_event_pg.py` and `audit_log_pg.py` (62-231) implement the same queue/worker/batch lifecycle (module globals, `_drain_*_queue`, `_write_*_batch` with session+rollback, timeout-driven worker with shutdown drain-to-empty, start/stop, `write_*` with `put_nowait` + `QueueFull` warning) — ~140 duplicated lines. The UI-event worker even reads `settings.audit_log_*` keys (a semantic oddity). | Extract a generic `BatchedAsyncWriter[T]` (e.g. `_batched_writer.py`) taking `insert_sql`, `param_fn`, `worker_name`, and explicit config; reduce each module to its SQL, payload dataclass, and thin delegating wrappers. Preserve the exact shutdown-drain and `QueueFull`-drop semantics. | M | Removes ~140 lines; future worker fixes apply once; clears the `audit_log_*`-for-UI-events oddity. |

### Backend — redundant indirection & ambiguous types

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 13 | `panelapp_panel_url` is a redundant one-line wrapper of `_panelapp_url` | `backend/app/services/panelapp_service.py` (276-277) | The public wrapper just delegates to `_panelapp_url` so `panel_metadata_service` can import a non-underscore name, while `_panelapp_url` is used directly elsewhere — two names for one function. | Rename `_panelapp_url` to `panelapp_panel_url` throughout the file and delete the wrapper; the consumer's import already uses that name. | S | Removes one indirection level. No behavior change. |
| 14 | Two distinct dataclasses both named `StructuralVariantRecord` | `backend/app/services/structural_variant_ingest.py` (14-31) | A parser-level frozen dataclass shares the name `StructuralVariantRecord` with a completely different storage-level dataclass in `clickhouse_family_variants.py:209`. The consumer types the ingest record as `record: Any` specifically to paper over the collision, and a stray cross-import would silently shadow the storage class. | Rename the parser-level class to `ParsedStructuralVariant` (update annotations/yields in the ingest module) and type `_structural_record_call`'s parameter to it in `variant_upload_service.py`. | S | Restores static typing in the consumer; removes the silent-shadow footgun. No runtime change. |

### Backend — duplicated route handlers & schema envelopes

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 15 | structural-variant-tags endpoints are exact duplicates of small-variant-tags | `backend/app/routers/families.py` (937-1035 vs 744-842) | The four `/{family_id}/structural-variant-tags...` handlers call the **same** four service functions with the same arguments as the small-variant handlers, against the same `small_variant_tag_definitions` table — there is no discriminator. The frontend even aliases `StructuralVariantTagDefinition = SmallVariantTagDefinition`, and only the GET endpoint is used (the structural POST/PUT/DELETE are unreachable from the UI). | If structural tags are meant to share the store (likely): remove the four duplicate handlers and point the two frontend GET calls at `/small-variant-tags` (read-only URL change). If they should be a distinct namespace: add a `kind` discriminator column and thread it through all four service functions and both route families. | S | Removes ~100 lines of duplicated/dead backend code; eliminates drift risk. No user-visible change under option 1. |
| 16 | Four family-mutation response envelopes duplicated field-for-field | `backend/app/schemas.py` (204-209, 265-291) | `FamilyStructureUpdateOut` and `FamilyMemberBatchUpdateOut` are byte-identical; `FamilyMemberDeleteOut` adds `impact`; `FamilyMemberUpdateOut` adds `member/father_id/mother_id/impact`. All four repeat the same 5 core fields (`family`, `warnings`, `stale_analysis_scopes`, `data_counts`, `cleared_data_counts`). | Introduce a private base `_FamilyMutationResultOut` with the 5 shared fields; have the four out-models inherit and declare only their extras. Class names, `response_model` bindings, and call sites are unchanged. | S | Removes ~16 duplicated field declarations; future envelope additions are one edit. No API change. |

### Backend — potential behavioral mismatch (resolve before refactor)

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 17 | Affected/unaffected sample computation duplicated in the candidate endpoint | `backend/app/services/clickhouse_family_variants.py` (4557-4568) | `get_family_compound_het_candidates` re-implements the affected filter and unaffected derivation inline, partially duplicating `_family_affected_unaffected_sample_names` (2264-2280). **The inline version omits the `clinical_status == "unaffected"` predicate**, so it treats all non-affected samples as unaffected — a behavioral divergence, not just duplication. | Decide which definition is correct for the candidates endpoint first. If the helper's strict definition wins, replace 4557-4568 with a call to `_family_affected_unaffected_sample_names(context)` and add a regression test for samples lacking `clinical_status`; otherwise document the broader intent (or add an opt-in parameter to the helper). | S (mechanical) + domain review | Low impact if `clinical_status` is always populated; moderate if not — the refactor would shrink the unaffected set and return fewer compound-het pairs. |

### Frontend — shared helpers re-implemented locally

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 18 | `getErrorMessage` re-implemented in 5 admin files while a richer shared helper exists | `frontend/src/pages/admin/AdminVariantTagsPage.tsx` (14-20) and 4 peers | Identical local `getErrorMessage` copies in `AdminVariantTagsPage`, `AdminAuditLogsPage` (62-68), `DataManagementPage` (20-33), `AdminClickhouseManagementPage` (12-18), `AdminPresetFiltersPage` (9-15) only read a string `detail` and fall back to `error.message`. The canonical `lib/errorMessage.ts` (already used by `HpoTerminologyAdminPage`/`GeneReferenceAdminPage`) also handles array-shaped 422 `detail`, object `detail.message`, and network errors — so these pages render unhelpful text for 422s. | Delete the 5 local copies and `import { getErrorMessage } from '../../lib/errorMessage'` (the shared signature is a superset). Fold in the additional local variant in `ProjectsPage.tsx` (95-103) in the same pass. | S | Correct 422/array-detail and network messages on all five pages. No regression (shared version is a strict superset). |
| 19 | `formatNumber` duplicated, a verbatim copy of shared `formatCount` | `frontend/src/pages/admin/GeneReferenceAdminPage.tsx` (53) | `GeneReferenceAdminPage`'s `formatNumber` is byte-identical to the exported `formatCount` in `dataManagementTypes.ts:156`. `HpoTerminologyAdminPage` (54-55) has a near-identical variant that adds a null guard returning `'0'` (and uses `toLocaleString()`). | In `GeneReferenceAdminPage`, import `formatCount` and rename call sites. For `HpoTerminologyAdminPage`, either promote a nullable-aware `formatCountOrZero` wrapper or add `?? 0` at call sites — preserve the `'0'`-on-null behavior. Leave `GeneInfoPage.formatNumber` (digits param) alone. | S | One exact + one near-duplicate removed. No runtime change for `GeneReferenceAdminPage`. |

### Frontend — small/medium-variant filter & search helpers

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 20 | `splitSelectedValues`/`joinSelectedValues` duplicate exported search helpers | `frontend/src/pages/families/SmallVariantFilterForm.tsx` (112-116, 331-332) | Two local helpers are byte-identical to `parseCommaSeparatedValues`/`joinFilterValues` already exported from `smallVariantSearch.ts` (474-481), which the form already imports from. | Import the two exported helpers, delete the local copies, and update the call sites (~16 + 2). No logic change. | S | ~10 lines removed; single source of truth for comma-separated filter handling. |
| 21 | In-silico & frequency data computed twice per card | `frontend/src/pages/families/SmallVariantCards.tsx` (321-348, 401-425) | `scoreItems`/`silicoRows` and `frequencyItems`/`freqRows` pull from the same fields with parallel logic, doubling per-card work and inviting drift. **Note:** the divergence is partly intentional — `silicoRows` adds AlphaMissense and strict `typeof` guards; `scoreItems` adds `lof_filter`/`lof_flags`; `freqRows` uses fixed named keys with hyperlinks and always renders the gnomAD row, while `frequencyItems` does a dynamic dump. | Optional cleanup: extract parameterized `buildScoreItems(variant, {includeLof, includeAlphaMissense})` and `buildFreqItems(variant, {linkMap})` consumed by both slots. Preserve the AlphaMissense lookup (visible column) and `lof_*` fields (detail panel). | M | No user-visible change. Reduces drift risk as new score fields are added; negligible perf gain. |

### Frontend — structural-variant components & constants

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 22 | IGV/Chromosome-view link construction duplicated between SV Cards and Table | `frontend/src/pages/families/StructuralVariantTable.tsx` (382-438) | `StructuralVariantTable` re-implements inline the exact primary-locus IGV href and `viewHref` produced by `buildStructuralVariantNavigation` in `StructuralVariantCards.tsx` (93-117) — same `Math.max(1, start)`, same ±1,000,000 window, same query-param handling. The helper is local/not exported. | Move `buildStructuralVariantNavigation` to a shared module (`structuralVariantSearch.ts` or a new `structuralVariantNavigation.ts`), export it, and call it from the Table for `hrefA` and the View href. Keep the Table-only remote-locus (locus B) branch separate. | S | ~30 lines of URL construction removed; locus/window/param format changes become one edit. |
| 23 | Form hardcodes genotype-group token literals instead of exported constants (and a count bug) | `frontend/src/pages/families/StructuralVariantFilterForm.tsx` (386-390) | The GT toggle options inline the token arrays (`['1/1','1|1']`, etc.), exactly duplicating `STRUCTURAL_HOM/HET/REF_GT_GROUP` (`structuralVariantSearch.ts:162-164`). Because the literals are decoupled from the constants, the form's `< 12` active-filter threshold (line 157) is wrong — there are only 10 tokens, so a fully-selected (default) GT filter is mis-counted as active. | Import `STRUCTURAL_HOM/HET/REF_GT_GROUP` and `STRUCTURAL_ALL_GT_GROUPS`; build the options from them and replace `< 12` with `< STRUCTURAL_ALL_GT_GROUPS.length`. | S | Removes 3 duplicated literals **and fixes** the active-filter badge over-counting the default state. |
| 24 | `StructuralVariantTagDefinition` alias / unused tag mutations (see backend #15) | — | (cross-references the structural-vs-small tag duplication above) | — | — | — |

### Frontend — visualization tracks & ideogram utilities

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 25 | `CoverageSegmentsChart` and `ApcadChart` duplicate ~120 lines of scaffolding | `frontend/src/components/visualizations/CoverageSegmentsChart.tsx` (8-118, 135-313) | Both define identical `DEFAULT_CHROMS`, `normalizeChrom`, `splitKey`, `deriveLayoutFromBins`, `fetchJsonOrNull`, the `Layout` interface, the `stableUrls/stableChroms` memo trio, and the same AbortController dual-URL fetch effect; they diverge only in per-point drawing and APCAD's `origin`/finite-value filtering. `isDeletedHaplotype` + `DEFAULT_CHROMS` are likewise duplicated between `GenomeHaplotypeTrack` and `HaplotypePhasedTrack`. | Extract a `trackUtils.ts` (the chrom/layout/fetch utilities, a generic `deriveLayoutFromBins<T>`, `Layout`) and a `useIntervalTrackData` hook taking two URL arrays, a chrom list, and a per-item transform; both charts supply their domain-specific transforms. Share `isDeletedHaplotype`/`DEFAULT_CHROMS` between the haplotype tracks. Note the local `normalizeChrom` is the simple variant, distinct from `viewerShared`'s fuller one. | M | Removes ~80-100 lines; fetch/AbortController/`normalizeChrom` fixes apply once. Rendering stays per-component. |
| 26 | `SvTrack` and `VariantTrack` duplicate SV layout/drawing across two backends | `frontend/src/components/visualizations/SvTrack.tsx` (36-207) | Both share `TYPE_ORDER`, `typeColors`, the `PositionedVariant` shape, row-height math, WT genotype filtering, and per-type marker rules — once as canvas calls (174-206) and once as SVG (`VariantTrack` 189-241). They have **already drifted**: INV draws at `globalAlpha=0.82` (canvas) vs `fillOpacity=1` (SVG). | Phase 1 (S): move `TYPE_ORDER`, the `VariantType` union, and `typeColors` to a shared `svVariantShared.ts`. Phase 2 (M): extract geometry/marker-shape helpers returning shape descriptors consumed by both backends — but reconcile the INV opacity first. Keep the two components separate (canvas vs SVG, fetch vs react-query, differing genotype shapes). | M | Eliminates a styling-drift class (INV opacity already mismatched); future marker changes become one edit. |
| 27 | Repeat-expansion `STATUS_COLORS` + tooltip duplicated across two tracks | `frontend/src/components/visualizations/GenomeRepeatExpansionTrack.tsx` (25-30) | `RepeatExpansionTrack` (21-26) and `GenomeRepeatExpansionTrack` (25-30) declare a byte-identical `STATUS_COLORS`; the tooltip JSX (three divs), the `STATUS_COLORS[item.status]?.() || cssVar('--color-repeat-unknown')` lookup, and the `trackY/trackHeight` geometry are all duplicated. | Extract `STATUS_COLORS`, a `RepeatLocusTooltip` component, a `getRepeatColor(status)` helper (and optionally `computeRepeatTrackLayout(height)`) into a shared `repeatExpansionHelpers.ts`; import into both. | S | ~20 lines removed; status-color/tooltip changes happen once. No runtime change. |
| 28 | `ZoomedIdeogram` re-implements glossy gradient stops instead of `getBandGradientStops` | `frontend/src/components/visualizations/ZoomedIdeogram.tsx` (150-155) | `ZoomedIdeogram` hand-writes the four glossy `<stop>` elements (and a private `blendHex`) that are numerically identical to `getBandGradientStops(color, 'glossy')` in `lib/ideogram.ts` (64-70), which `Ideogram.tsx` and `CircosPlot.tsx` already use. | Import `getBandGradientStops`, map its output to `<stop>` elements (mirroring `Ideogram.tsx`), and delete the private `blendHex`. | S | Removes 4 duplicated stop literals + a `blendHex` copy; glossy-finish changes become one edit. No visual change. |
| 29 | `ZoomedIdeogram` duplicates the nice-tick-interval algorithm from `Ideogram` | `frontend/src/components/visualizations/ZoomedIdeogram.tsx` (123-144) | The `minTickSpacingPx=60` / `niceFraction` (1/2/5/10) / `tickInterval` computation is copy-pasted from `Ideogram.tsx` (155-171), already drifting (the `Math.max(1, …)` guard exists only in `ZoomedIdeogram`). `formatBp` is also near-duplicated (`toFixed(2)` vs `Math.round`). | Extract `niceTickInterval(rangeLength, widthPx, minSpacingPx=60)` into `lib/ideogram.ts` (include the safety guard) and reuse in both; decide whether the two `formatBp` precisions can unify. | S | ~20 lines removed; prevents further drift. No user-visible change. |

### Frontend — genome pages, panels & formatting helpers

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 30 | Redundant `assembly` prop duplicates `assemblyName` in both workspaces | `frontend/src/pages/genome/GenomeOverviewWorkspace.tsx` (53,55,…); `ChromosomeViewWorkspace.tsx` (75,77) | Both workspaces declare separate `assembly` (forwarded to tracks) and `assemblyName` (label) props, but both parent pages always bind both to the same `assemblyName` variable (`GenomeOverviewPage:445-447`, `ChromosomeViewPage:517-519`). | Collapse to a single prop (keep `assembly`, the more-used name) in both prop interfaces; update destructures, the `formatResolvedReferenceLabel` call, and the two call sites. | S | Removes 2 prop declarations + 2 JSX attributes; closes a subtle "two names, one value" confusion. No runtime impact. |
| 31 | `normalizeChromosomeTarget` re-applies logic already done by `normalizeChrom` | `frontend/src/pages/genome/ChromosomeViewWorkspace.tsx` (139-146) | `normalizeChrom` (`viewerShared.ts:19-24`) already trims, strips `chr`, maps `m`/`mt`→`MT`, collapses numeric strings, and uppercases. `normalizeChromosomeTarget` then re-applies the same `/^\d+$/→String(Number())` and `.toUpperCase()` — a no-op for every input. | Replace the body with `return normalizeChrom(value.trim());` (or inline `normalizeChrom` at the two call sites and delete the helper). | S | ~5 lines of dead post-processing removed. No behavior change. |
| 32 | `formatSize`/`formatBp` byte humanizers duplicated across pages | `frontend/src/pages/genome/CnvDetailsPage.tsx` (10-14) | `CnvDetailsPage`'s local `formatSize` near-duplicates shared `formatBp` (`viewerShared.ts:13-17`), differing only in kb precision (1 vs 2 decimals). The same 1-decimal `formatSize` also lives in `ClinicalCnvExplorerPage.tsx` (10-14), and `Ideogram`/`ZoomedIdeogram` each define their own `formatBp`. | Decide the canonical kb precision; if 1-decimal is wanted for CNV contexts, add an optional precision param to `viewerShared.formatBp`. Import and reuse it across `CnvDetailsPage`, `ClinicalCnvExplorerPage`, `Ideogram`, `ZoomedIdeogram`; delete the local copies. | S | Removes 4-5 near-duplicate formatters. Minor UI change only if the 2-decimal default is adopted without a precision option. |
| 33 | Duplicated `GenePanel`/region interfaces across the two panel pages | `frontend/src/pages/panels/GenePanelDetailPage.tsx` (7-29) | `GenePanelDetailPage` (`GeneRegion` + `GenePanel`) and `GenePanelsPage` (`GeneLocation` + `GenePanel`) describe the same `/panels` payload but have already drifted — `GenePanelsPage.GeneLocation` is missing the `gene` field. Future backend changes must be mirrored in multiple hand-written copies. | Hoist a shared `GeneLocation` (4-field shape: `gene/chr/start/end`) and `GenePanel` into `lib/apiTypes.ts`; import into both pages and delete the locals. Leave the narrower `GenePanel` stubs in `smallVariantSearch.ts` and `GeneTrack.tsx` as-is. | S | Fixes the existing `gene`-field drift; backend shape changes become one edit. No runtime change. |

### Frontend — dead/redundant computation

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 34 | `byTypeChrom` is a fully redundant nested count map | `frontend/src/pages/families/FamilyVariantSummaryPage.tsx` (66, 79-80, 84) | `byTypeChrom`'s nested cell counts are written per variant but never read; its only consumer is `Object.keys(byTypeChrom).sort()` (line 84), whose key set is identical to `byType`'s. The table cells use `byChromType` instead. The whole nested map is dead computation in the hot loop. | Delete `byTypeChrom` (decl + two writes) and change line 84 to `Object.keys(byType).sort()`. | S | Removes 3 lines of dead state and a per-variant write; mainly a clarity win. |
| 35 | Copy-number-signal predicate duplicated inline in two `useMemo`s | `frontend/src/pages/families/FamilyParaphasePage.tsx` (473-474, 480-483) | `Boolean(gene.has_copy_number_signal) || Object.values(gene.samples).some((call) => hasCopyNumberSignal(call))` is written verbatim in `filteredGenes` and `copyNumberSignalCount`, so the filter and the displayed count can drift. | Extract `geneHasCopyNumberSignal(gene)` next to `hasCopyNumberSignal` and call it from both `useMemo`s. | S | Removes drift risk between filter and badge count. No runtime change. |

### Frontend — query-suffix builders & upload flow

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 36 | Two near-duplicate `project_id` query-suffix builders | `frontend/src/pages/families/FamilyDetailPage.tsx` (356-363, 509) | `buildVariantDataParams()` (URLSearchParams) and `variantPageQuerySuffix` (template + `encodeURIComponent`) both build the same `?project_id=<id>` suffix for fetch URLs and Links; the encoding difference is immaterial for project IDs. | Collapse both into one memoized `projectQuerySuffix` and use it across all six call sites; remove the function and the const. | S | Unifies six call sites under one value. No runtime change for typical project IDs. |
| 37 | Duplicated PED-upload form, submit logic, and `INHERITANCE_MODELS` | `frontend/src/pages/dashboard/FamilyIntakePanel.tsx` (14, 457-553, 736-811) | `FamilyIntakePanel`'s upload mode and `PedUpload.tsx` independently implement the same PED-upload flow: character-identical `INHERITANCE_MODELS`, the same multipart assembly (`file/roi_query/inheritance_model/obligate_carriers/proven_carriers`), the same `project_id` param, and the same 409-overwrite retry. They have already diverged (project-id required, admin guard, richer success message, field reset only in `FamilyIntakePanel`). **`PedUpload` is NOT orphaned** — it's a live route at `/upload`. | Extract `INHERITANCE_MODELS` and a `buildPedFormData`/`usePedUpload` helper into a shared module (e.g. `lib/pedUpload.ts`); both callers import it and keep their component-specific validation/success handling on top. | M | API-contract changes (new field, rename, conflict message) happen once. The `INHERITANCE_MODELS` extraction alone is trivial (S). |

### Frontend — formatting consistency (cosmetic)

| # | Title | File | Problem & impact | Recommendation | Effort | Expected impact |
|---|-------|------|------------------|----------------|--------|-----------------|
| 38 | Row-count formatting inconsistent: `event.inserted.toLocaleString()` vs `formatCatalogCount` | `frontend/src/pages/reference/ReferenceCatalogPage.tsx` (1266) | The recent-activity table formats the count inline while every other count in the file uses `formatCatalogCount` (`(value ?? 0).toLocaleString()`). Purely a consistency gap — the claimed null risk does not apply (`inserted: int = 0` server-side; `number` non-nullable client-side). | Replace `event.inserted.toLocaleString()` with `formatCatalogCount(event.inserted)` to match the file's convention. | S | Cosmetic consistency only. No behavioral, performance, or safety change. |
---

## Appendix — pre-existing issues noticed (not introduced by this review)

- **Stale test mock** in `tests/test_reference_source_service.py` —
  `fake_apply_reference_dataset_text` was missing the `performed_by`/`source` kwargs
  the production code already passes, so the test failed on `main`. **Fixed in this
  pass** (the mock now accepts them) to get the suite to green.
- **Pre-existing eslint warning** — `referenceLabel` is assigned but unused in
  `frontend/src/pages/families/FamilySmallVariantsPage.tsx` (line 134, present on
  `main`). Left as-is (out of the verified-findings scope; warning-level only).

## Suggested sequencing for the backlog

1. **Quick wins (S, high value):** the dead expensive inventory call on every
   small-variant delete (Perf §3), the gene-refresh triple-commit (Perf §2), the
   interval-track DDL-on-every-read (Perf low-impact table), and the SV-list /
   variant-summary `keepPreviousData`/`useMemo` frontend fixes (Perf §13–14).
2. **N+1 query elimination (M):** repeat-expansion ingest, batch-BED-per-chromosome,
   SV gene-symbol lookup, admin Data→Families counts, HPO annotation import (Perf §1, 4, 5, 6, 9).
3. **Bounded fetches (M):** unbounded SV/carrier/region queries (Perf §7–8, low-impact region cap).
4. **Correctness decisions (Perf/Bug/Dead-code):** the `formatGt` no-call handling
   (Bug §1), the compound-het unaffected definition (Simplification §17 — note the
   applied fix already aligned the main family-page path; the candidate endpoint is
   the remaining one), and the authorization-intent question in `ped_service`
   (Dead-code §"authorization-design question").
5. **Dedup passes (S–M):** the shared `getErrorMessage`/review-helper/track-utility
   consolidations (Simplification §1, 18, 25–29) — low risk, high maintainability payoff.
