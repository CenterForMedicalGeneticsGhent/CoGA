ALTER TABLE gene_panels
ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'local';

ALTER TABLE gene_panels
ADD COLUMN IF NOT EXISTS external_id TEXT;

ALTER TABLE gene_panels
ADD COLUMN IF NOT EXISTS external_version TEXT;

ALTER TABLE gene_panels
ADD COLUMN IF NOT EXISTS external_url TEXT;

ALTER TABLE gene_panels
ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ;

ALTER TABLE gene_panels
ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gene_panels_source_external
    ON gene_panels (source, external_id)
    WHERE external_id IS NOT NULL;
