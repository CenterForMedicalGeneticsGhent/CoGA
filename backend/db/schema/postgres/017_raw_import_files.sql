-- Raw import file provenance: tracks every source file used to import data for a
-- family or one of its samples. Supports download, file-size display, and
-- SHA-256 integrity verification from the Admin -> Data -> Families page.
CREATE TABLE IF NOT EXISTS raw_import_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    sample_id UUID REFERENCES samples(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('family', 'individual')),
    dataset TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL DEFAULT '',
    storage_path TEXT NOT NULL,
    managed BOOLEAN NOT NULL DEFAULT FALSE,
    file_size BIGINT,
    sha256 TEXT,
    source TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_raw_import_files_family
    ON raw_import_files (family_id, scope);

CREATE INDEX IF NOT EXISTS idx_raw_import_files_sample
    ON raw_import_files (sample_id);

-- A given physical file is recorded once per (family, sample, storage path).
-- Re-imports refresh the existing row instead of accumulating duplicates.
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_import_files_identity
    ON raw_import_files (
        family_id,
        COALESCE(sample_id, '00000000-0000-0000-0000-000000000000'::uuid),
        storage_path
    );
