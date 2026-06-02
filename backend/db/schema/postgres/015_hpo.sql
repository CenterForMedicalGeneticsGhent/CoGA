CREATE TABLE IF NOT EXISTS hpo_term (
    hpo_id TEXT PRIMARY KEY CHECK (hpo_id ~ '^HP:[0-9]{7}$'),
    label TEXT NOT NULL,
    definition TEXT,
    is_obsolete BOOLEAN NOT NULL DEFAULT FALSE,
    replaced_by TEXT,
    release_version TEXT,
    release_date DATE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_hpo_term_label_lower ON hpo_term (lower(label));

CREATE TABLE IF NOT EXISTS hpo_synonym (
    hpo_id TEXT NOT NULL REFERENCES hpo_term(hpo_id) ON DELETE CASCADE,
    synonym TEXT NOT NULL,
    PRIMARY KEY (hpo_id, synonym)
);

CREATE INDEX IF NOT EXISTS idx_hpo_synonym_lower ON hpo_synonym (lower(synonym));

CREATE TABLE IF NOT EXISTS hpo_edge (
    child_id TEXT NOT NULL REFERENCES hpo_term(hpo_id) ON DELETE CASCADE,
    parent_id TEXT NOT NULL REFERENCES hpo_term(hpo_id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'is_a',
    PRIMARY KEY (child_id, parent_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_hpo_edge_parent ON hpo_edge (parent_id);

CREATE TABLE IF NOT EXISTS hpo_closure (
    hpo_id TEXT NOT NULL REFERENCES hpo_term(hpo_id) ON DELETE CASCADE,
    ancestor_id TEXT NOT NULL REFERENCES hpo_term(hpo_id) ON DELETE CASCADE,
    distance INTEGER NOT NULL CHECK (distance >= 0),
    PRIMARY KEY (hpo_id, ancestor_id)
);

CREATE INDEX IF NOT EXISTS idx_hpo_closure_ancestor ON hpo_closure (ancestor_id);

CREATE TABLE IF NOT EXISTS individual_hpo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    sample_id UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    hpo_id TEXT NOT NULL REFERENCES hpo_term(hpo_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'unknown')),
    onset TEXT,
    evidence TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (family_id, sample_id, hpo_id, status)
);

CREATE INDEX IF NOT EXISTS idx_individual_hpo_family_sample ON individual_hpo (family_id, sample_id);
CREATE INDEX IF NOT EXISTS idx_individual_hpo_hpo_status ON individual_hpo (hpo_id, status);
