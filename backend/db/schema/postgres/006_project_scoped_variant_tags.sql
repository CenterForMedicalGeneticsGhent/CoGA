ALTER TABLE small_variant_tag_definitions
ADD COLUMN IF NOT EXISTS scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE small_variant_tag_definitions
DROP CONSTRAINT IF EXISTS small_variant_tag_definitions_scope_check;

ALTER TABLE small_variant_tag_definitions
ADD CONSTRAINT small_variant_tag_definitions_scope_check
CHECK (scope IN ('global', 'project'));

ALTER TABLE small_variant_tag_definitions
ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE CASCADE;

ALTER TABLE small_variant_tag_definitions
DROP CONSTRAINT IF EXISTS small_variant_tag_definitions_scope_project_check;

ALTER TABLE small_variant_tag_definitions
ADD CONSTRAINT small_variant_tag_definitions_scope_project_check
CHECK (
    (scope = 'global' AND project_id IS NULL)
    OR (scope = 'project' AND project_id IS NOT NULL)
);

-- NOTE (P0-1): a one-shot backfill `UPDATE small_variant_tag_definitions SET
-- scope='global', project_id=NULL WHERE ...` was removed here. init_postgres_schema()
-- replays every statement of every *.sql on every startup (no migration ledger), so
-- that unconditional UPDATE reset every legitimately-created scope='project' tag back
-- to global on each restart — recurring silent data loss. Fresh DBs need no backfill:
-- the `scope` column is added WITH DEFAULT 'global' and project_id defaults to NULL, so
-- any pre-existing rows are already global. Do not reintroduce a destructive data
-- mutation in this idempotent-on-every-boot schema file.
CREATE TABLE IF NOT EXISTS small_variant_tag_definition_project_links (
    tag_id UUID NOT NULL REFERENCES small_variant_tag_definitions(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (tag_id, project_id)
);
