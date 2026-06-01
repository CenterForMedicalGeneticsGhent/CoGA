ALTER TABLE family_members
ADD COLUMN IF NOT EXISTS clinical_status TEXT NOT NULL DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS carrier_status TEXT NOT NULL DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS carrier_type TEXT,
ADD COLUMN IF NOT EXISTS carrier_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now());

ALTER TABLE family_members
DROP CONSTRAINT IF EXISTS family_members_clinical_status_check;

ALTER TABLE family_members
ADD CONSTRAINT family_members_clinical_status_check
CHECK (clinical_status IN ('unknown', 'unaffected', 'affected'));

ALTER TABLE family_members
DROP CONSTRAINT IF EXISTS family_members_carrier_status_check;

ALTER TABLE family_members
ADD CONSTRAINT family_members_carrier_status_check
CHECK (carrier_status IN ('unknown', 'not_carrier', 'carrier'));

ALTER TABLE family_members
DROP CONSTRAINT IF EXISTS family_members_carrier_type_check;

ALTER TABLE family_members
ADD CONSTRAINT family_members_carrier_type_check
CHECK (carrier_type IN ('obligate', 'proven', 'reported', 'inferred'));

CREATE INDEX IF NOT EXISTS idx_family_members_status
    ON family_members (family_id, clinical_status, carrier_status)
    WHERE active;

CREATE TABLE IF NOT EXISTS family_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('parent_child', 'couple')),
    sample_id_a UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    sample_id_b UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    role_a TEXT,
    role_b TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CHECK (sample_id_a <> sample_id_b)
);

CREATE INDEX IF NOT EXISTS idx_family_relationships_family_type
    ON family_relationships (family_id, relationship_type)
    WHERE active;

CREATE INDEX IF NOT EXISTS idx_family_relationships_sample_a
    ON family_relationships (sample_id_a)
    WHERE active;

CREATE INDEX IF NOT EXISTS idx_family_relationships_sample_b
    ON family_relationships (sample_id_b)
    WHERE active;

CREATE TABLE IF NOT EXISTS family_structure_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    structure_hash TEXT NOT NULL,
    snapshot JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (family_id, version)
);

ALTER TABLE family_structure_versions
ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_family_structure_versions_family
    ON family_structure_versions (family_id, version DESC);
