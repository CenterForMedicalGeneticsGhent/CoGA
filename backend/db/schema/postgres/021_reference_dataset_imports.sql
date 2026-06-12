-- Lightweight per-(assembly, dataset) import tracking so the Reference Data UI
-- can show when each dataset was last updated, by whom, and how many rows were
-- loaded. Written from the single apply path (apply_reference_dataset_text), so
-- uploads, UCSC imports, and CNV-KB rebuilds are all recorded uniformly.
CREATE TABLE IF NOT EXISTS reference_dataset_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assembly_id UUID NOT NULL REFERENCES assemblies(id) ON DELETE CASCADE,
    dataset_type TEXT NOT NULL,
    inserted INTEGER NOT NULL DEFAULT 0,
    replaced BOOLEAN NOT NULL DEFAULT false,
    source TEXT,
    performed_by TEXT,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reference_dataset_imports_latest
    ON reference_dataset_imports (assembly_id, dataset_type, performed_at DESC);
