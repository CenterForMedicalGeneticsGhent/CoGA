-- P2-3: expression indexes for the gene autocomplete / panel & region resolve /
-- case-insensitive + constraint lookups, which currently sequential-scan the 120k+-row
-- genes/gene_info tables on every keystroke, panel/region resolve and per-variant-batch
-- gene-constraint enrichment. Each index's EXPRESSION and OPERATOR CLASS match a query
-- predicate exactly (text_pattern_ops ONLY serves the prefix LIKE; the default opclass
-- serves =/IN). Additive + idempotent; genes/gene_info are bulk-refreshed, read-heavy.

-- Autocomplete (gene_metadata_service.search_genes):
--   WHERE assembly_id IN (...) AND upper(hgnc_symbol) LIKE 'PREFIX%'
CREATE INDEX IF NOT EXISTS idx_genes_assembly_symbol_prefix
    ON genes (assembly_id, upper(hgnc_symbol) text_pattern_ops);

-- upper(hgnc_symbol) = / IN — panel resolve (panel_metadata_service) and the gene/region
-- resolvers (clickhouse_family_variants._resolve_*, nipt_service) which OR it with gene_id.
CREATE INDEX IF NOT EXISTS idx_genes_upper_symbol ON genes (upper(hgnc_symbol));
-- The OTHER branch of those resolvers: WHERE (upper(hgnc_symbol) IN .. OR upper(gene_id) IN ..)
-- — both OR branches must be indexed for the planner to BitmapOr instead of seq-scanning.
CREATE INDEX IF NOT EXISTS idx_genes_upper_gene_id ON genes (upper(gene_id));

-- Candidate resolve (gene_metadata_service._get_genes_by_candidates), the case-insensitive
-- single-symbol lookup (gene_info_jobs_pg, FROM genes), and the gene-resolve in
-- family_service / family_package_import (lower(hgnc_symbol)=/lower(gene_id)=): all over
-- lower(hgnc_symbol)/lower(gene_id)/lower(COALESCE(extra->>'transcript_id','')). All three
-- branches indexed so the planner can BitmapOr instead of seq-scanning.
CREATE INDEX IF NOT EXISTS idx_genes_lower_symbol ON genes (lower(hgnc_symbol));
CREATE INDEX IF NOT EXISTS idx_genes_lower_gene_id ON genes (lower(gene_id));
CREATE INDEX IF NOT EXISTS idx_genes_lower_transcript_id
    ON genes (lower(COALESCE(extra->>'transcript_id', '')));

-- gene_info constraint enrichment (clickhouse_family_variants._fetch_gene_constraint_*):
--   WHERE (upper(hgnc_symbol) IN (...) OR gene_id IN (...))  — note upper(), not lower();
-- both OR branches indexed. (The case-insensitive single-symbol lookup is on genes, not
-- gene_info, so gene_info needs upper(hgnc_symbol) here, not lower.)
CREATE INDEX IF NOT EXISTS idx_gene_info_upper_symbol ON gene_info (upper(hgnc_symbol));
CREATE INDEX IF NOT EXISTS idx_gene_info_gene_id ON gene_info (gene_id);
