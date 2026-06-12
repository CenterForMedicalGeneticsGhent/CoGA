-- Background-job tracking for admin-triggered rebuilds of the clinical CNV
-- knowledgebase (runs the knowledgebase build script, then loads the result
-- into clinical_cnvs for the target assembly).
CREATE TABLE IF NOT EXISTS clinical_cnv_kb_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assembly_id UUID NOT NULL REFERENCES assemblies(id) ON DELETE CASCADE,
    assembly_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    skip_clinvar BOOLEAN NOT NULL DEFAULT false,
    requested_by TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    inserted INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    log TEXT
);

CREATE INDEX IF NOT EXISTS idx_clinical_cnv_kb_jobs_requested_at
    ON clinical_cnv_kb_jobs (requested_at DESC);

-- At most one queued/running rebuild at a time.
CREATE UNIQUE INDEX IF NOT EXISTS idx_clinical_cnv_kb_jobs_active
    ON clinical_cnv_kb_jobs ((status))
    WHERE status IN ('queued', 'running');
