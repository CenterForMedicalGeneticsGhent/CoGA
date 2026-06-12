-- Structured detail fields for clinical CNV syndromes so curated OMIM and
-- DECIPHER references and a short clinical description can be ingested and
-- surfaced on the CNV details page. All fields are optional. The details page
-- falls back to derived links (OMIM search by name, DECIPHER region) when absent.
ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS omim_id TEXT;

ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS decipher_id TEXT;

ALTER TABLE clinical_cnvs
ADD COLUMN IF NOT EXISTS description TEXT;
