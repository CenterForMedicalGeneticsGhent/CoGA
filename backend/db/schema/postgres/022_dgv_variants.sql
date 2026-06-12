-- Database of Genomic Variants (DGV) structural variants, per assembly. BED-like
-- intervals loaded from the DGV variants TSV and rendered as a Chromosome View
-- track (density when zoomed out, stacked thin lines when zoomed in). variant_class
-- is the normalized gain / loss / mixed / other bucket used for colour coding.
CREATE TABLE IF NOT EXISTS dgv_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assembly_id UUID NOT NULL REFERENCES assemblies(id) ON DELETE CASCADE,
    chr TEXT NOT NULL,
    start BIGINT NOT NULL,
    "end" BIGINT NOT NULL,
    accession TEXT,
    variant_type TEXT,
    variant_subtype TEXT,
    variant_class TEXT NOT NULL DEFAULT 'other',
    frequency DOUBLE PRECISION,
    observed_gains INTEGER,
    observed_losses INTEGER,
    sample_size INTEGER,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_dgv_variants_assembly_region
    ON dgv_variants (assembly_id, chr, start);
