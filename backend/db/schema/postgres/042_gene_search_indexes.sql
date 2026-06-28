-- P2-3: expression indexes for the gene autocomplete / panel-resolve / case-insensitive
-- lookups, which currently sequential-scan the 120k+-row genes/gene_info tables on every
-- keystroke and panel/variant resolve. Each index expression matches a query predicate
-- EXACTLY (and uses the operator class the predicate's operator needs) so the planner can
-- use it. Additive + idempotent; genes/gene_info are refreshed in bulk, read-heavy.

-- Autocomplete (gene_metadata_service.search_genes):
--   WHERE assembly_id IN (...) AND upper(hgnc_symbol) LIKE 'PREFIX%'
-- text_pattern_ops makes the prefix LIKE index-usable regardless of the DB collation.
CREATE INDEX IF NOT EXISTS idx_genes_assembly_symbol_prefix
    ON genes (assembly_id, upper(hgnc_symbol) text_pattern_ops);

-- Panel resolve (panel_metadata_service): WHERE upper(hgnc_symbol) IN (...) + DISTINCT ON /
-- ORDER BY upper(hgnc_symbol). This is equality, so it needs the DEFAULT opclass (NOT
-- text_pattern_ops, which only serves the pattern operators).
CREATE INDEX IF NOT EXISTS idx_genes_upper_symbol
    ON genes (upper(hgnc_symbol));

-- Candidate resolve (gene_metadata_service._get_genes_by_candidates):
--   lower(hgnc_symbol) IN (...) OR lower(gene_id) IN (...)
--   OR lower(COALESCE(extra->>'transcript_id','')) IN (...)
-- All three OR branches are indexed so the planner can BitmapOr instead of seq-scanning.
CREATE INDEX IF NOT EXISTS idx_genes_lower_symbol ON genes (lower(hgnc_symbol));
CREATE INDEX IF NOT EXISTS idx_genes_lower_gene_id ON genes (lower(gene_id));
CREATE INDEX IF NOT EXISTS idx_genes_lower_transcript_id
    ON genes (lower(COALESCE(extra->>'transcript_id', '')));

-- gene_info case-insensitive symbol lookup (gene_info_jobs_pg):
--   WHERE lower(hgnc_symbol) = lower(:symbol)
CREATE INDEX IF NOT EXISTS idx_gene_info_lower_symbol
    ON gene_info (lower(hgnc_symbol));
