-- Semi-automatic ACMG/AMP classification for small variants.
--
-- `acmg` stores the full per-criterion selection blob (criteria, applied
-- strengths, evidence, accepted flags) so a classification is reproducible and
-- auditable. `acmg_point_total` and `acmg_class` are the server-recomputed
-- Tavtigian/ClinGen point total and class key (acmg_class_1..5), denormalized
-- for filtering and summaries.
ALTER TABLE small_variant_reviews
    ADD COLUMN IF NOT EXISTS acmg JSONB,
    ADD COLUMN IF NOT EXISTS acmg_point_total INTEGER,
    ADD COLUMN IF NOT EXISTS acmg_class TEXT;
