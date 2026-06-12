-- Additional curated detail columns for clinical CNVs, surfaced on the explorer
-- table and the details page and populated by the knowledgebase build
-- (cytoband, ISCA region id, Orphanet, OMIM title). All optional.
ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS cytoband TEXT;

ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS source_id TEXT;

ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS omim_title TEXT;

ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS orpha_id TEXT;

ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS orpha_name TEXT;
