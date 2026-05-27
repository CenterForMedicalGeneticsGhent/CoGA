CREATE TABLE IF NOT EXISTS segmental_duplications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assembly_id UUID NOT NULL REFERENCES assemblies(id) ON DELETE CASCADE,
    chr TEXT NOT NULL,
    start BIGINT NOT NULL,
    "end" BIGINT NOT NULL,
    label TEXT NOT NULL,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_segmental_duplications_assembly_region
    ON segmental_duplications (assembly_id, chr, start);
