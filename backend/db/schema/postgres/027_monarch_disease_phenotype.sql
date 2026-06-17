-- Monarch Initiative disease -> phenotype (HPO) associations.
--
-- Expected phenotypes for a disease, harvested from the Monarch Knowledge Graph
-- denormalized disease_phenotype association TSV (HPOA via OMIM/Orphanet, Biolink
-- `has_phenotype`). Pairs onto Phase 1's gene -> disease table (shared MONDO key)
-- to drive expected-vs-observed phenotype comparison on the gene profile.
--
-- One row per (disease, phenotype). When a pair is asserted by multiple sources the
-- sources are aggregated. `negated` marks an explicitly excluded phenotype (the
-- disease specifically does NOT present it); when a pair is asserted both ways the
-- present assertion wins. See docs/monarch-integration.md.
CREATE TABLE IF NOT EXISTS monarch_disease_phenotype (
    mondo_id        TEXT NOT NULL,
    disease_label   TEXT,
    hpo_id          TEXT NOT NULL,
    phenotype_label TEXT,
    negated         BOOLEAN NOT NULL DEFAULT FALSE,
    sources         JSONB NOT NULL DEFAULT '[]'::jsonb,
    release_version TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    PRIMARY KEY (mondo_id, hpo_id)
);

CREATE INDEX IF NOT EXISTS idx_monarch_disease_phenotype_hpo
    ON monarch_disease_phenotype (hpo_id);
