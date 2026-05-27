ALTER TABLE family_members
DROP CONSTRAINT IF EXISTS family_members_role_check;

ALTER TABLE family_members
ADD CONSTRAINT family_members_role_check
CHECK (role IN ('proband', 'father', 'mother', 'sibling', 'embryo', 'relative'));
