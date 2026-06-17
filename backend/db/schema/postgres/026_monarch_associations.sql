-- Monarch Initiative gene -> disease associations.
--
-- Curated gene-disease relationships harvested from the Monarch Knowledge Graph
-- denormalized association TSVs (OMIM, ClinGen, Orphanet via the Biolink model).
-- Reference data keyed by HGNC, independent of assembly, so it lives in its own
-- table and is joined onto the gene profile by symbol at read time rather than
-- denormalized into every per-assembly `gene_info` row.
--
-- One row per (gene, disease). When a pair is asserted by multiple sources or
-- predicates, sources/predicates are aggregated and `predicate` holds the
-- strongest relationship. `causal` is true when any causal predicate is present.
-- See docs/monarch-integration.md.
CREATE TABLE IF NOT EXISTS monarch_gene_disease (
    hgnc_id         TEXT NOT NULL,
    gene_symbol     TEXT NOT NULL,
    mondo_id        TEXT NOT NULL,
    disease_label   TEXT,
    predicate       TEXT NOT NULL,
    predicates      JSONB NOT NULL DEFAULT '[]'::jsonb,
    sources         JSONB NOT NULL DEFAULT '[]'::jsonb,
    causal          BOOLEAN NOT NULL DEFAULT FALSE,
    release_version TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    PRIMARY KEY (hgnc_id, mondo_id)
);

CREATE INDEX IF NOT EXISTS idx_monarch_gene_disease_symbol
    ON monarch_gene_disease (upper(gene_symbol));

CREATE INDEX IF NOT EXISTS idx_monarch_gene_disease_mondo
    ON monarch_gene_disease (mondo_id);
