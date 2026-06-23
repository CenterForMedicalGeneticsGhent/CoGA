-- Recurrent-artifact (panel-of-normals) list for monogenic NIPT, scoped per
-- assembly + assay/panel. Variants on this list are excluded from NIPT analysis
-- and counted in the filter funnel. `source` distinguishes manually curated
-- entries from any auto-seeded from internal cohort recurrence.

CREATE TABLE IF NOT EXISTS nipt_artifact_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assembly_id UUID NOT NULL REFERENCES assemblies(id) ON DELETE CASCADE,
    assay_key TEXT NOT NULL DEFAULT 'nipt_cfdna',
    variant_id TEXT NOT NULL,
    recurrence_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'curated' CHECK (source IN ('curated', 'auto')),
    label TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (assembly_id, assay_key, variant_id)
);

CREATE INDEX IF NOT EXISTS idx_nipt_artifacts_scope
    ON nipt_artifact_variants (assembly_id, assay_key);
