-- Semi-automatic ClinGen 2019 CNV classification for structural variants.
--
-- `cnv_acmg` stores the full per-criterion selection blob (kind, evidence codes,
-- chosen points, accepted flags, evidence text) so a classification is
-- reproducible and auditable. `cnv_point_total` and `cnv_class` are the
-- server-recomputed ClinGen point total and class key (cnv_class_1..5),
-- denormalized for filtering and summaries.
ALTER TABLE structural_variant_reviews
    ADD COLUMN IF NOT EXISTS cnv_acmg JSONB,
    ADD COLUMN IF NOT EXISTS cnv_point_total DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cnv_class TEXT;
