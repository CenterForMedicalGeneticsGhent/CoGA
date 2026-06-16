-- Family workflow metadata: an admin-managed catalogue of family statuses plus
-- per-family status / assignment / reviewer references. The status catalogue
-- mirrors small_variant_tag_definitions (stable key + human label + colour).

CREATE TABLE IF NOT EXISTS family_statuses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT,
    color TEXT NOT NULL DEFAULT '#5b6b79',
    sort_order INTEGER NOT NULL DEFAULT 500,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- Seed the default status catalogue. ON CONFLICT keeps this idempotent and
-- preserves any admin edits to these rows across restarts.
INSERT INTO family_statuses (key, label, color, sort_order) VALUES
    ('solved', 'Solved', '#1f9d57', 10),
    ('strong_candidate', 'Strong candidate', '#3fae6b', 20),
    ('reviewed_no_candidate', 'Reviewed, no clear candidate', '#c08a2d', 30),
    ('closed', 'Closed, no longer under analysis', '#6b7280', 40),
    ('analysis_in_progress', 'Analysis in progress', '#2f6fb0', 50),
    ('data_ready', 'Data ready for analysis', '#3b82a6', 60),
    ('waiting_for_data', 'Waiting for data', '#b08415', 70),
    ('loading_failed', 'Loading failed', '#c61f2d', 80),
    ('no_data_expected', 'No data expected', '#9aa3ad', 90)
ON CONFLICT (key) DO NOTHING;

ALTER TABLE families
ADD COLUMN IF NOT EXISTS status_id UUID REFERENCES family_statuses(id) ON DELETE SET NULL;

ALTER TABLE families
ADD COLUMN IF NOT EXISTS assigned_to_id UUID REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE families
ADD COLUMN IF NOT EXISTS reviewed_by_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_families_status_id ON families (status_id);
CREATE INDEX IF NOT EXISTS idx_families_assigned_to_id ON families (assigned_to_id);
CREATE INDEX IF NOT EXISTS idx_families_reviewed_by_id ON families (reviewed_by_id);
