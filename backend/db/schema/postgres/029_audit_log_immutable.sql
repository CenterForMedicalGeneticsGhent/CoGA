-- Make the access audit trail append-only at the database level so the record
-- of who-accessed-what-when cannot be quietly altered or erased -- a baseline
-- expectation for a PHI system. The application only ever INSERTs here, so this
-- does not affect normal operation.
--
-- DELETE is blocked outright. UPDATE is blocked too, with one carve-out: the
-- `user_id` foreign key is `ON DELETE SET NULL`, so deleting a user account
-- triggers a cascade UPDATE that nulls `user_id` on their audit rows. We allow
-- exactly that nulling (and nothing else) so account removal still works; the
-- denormalised user_email / user_role columns preserve the actor's identity.

CREATE OR REPLACE FUNCTION audit_log_events_block_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_log_events is append-only; DELETE is not permitted';
    END IF;
    -- UPDATE: permit only the ON DELETE SET NULL user unlink (user_id -> NULL,
    -- every other column unchanged). Compare the rest of the row column-agnostically
    -- so new columns stay protected automatically.
    IF NEW.user_id IS NOT NULL
        OR (to_jsonb(NEW) - 'user_id') IS DISTINCT FROM (to_jsonb(OLD) - 'user_id') THEN
        RAISE EXCEPTION 'audit_log_events is append-only; UPDATE is not permitted';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_events_immutable ON audit_log_events;
CREATE TRIGGER audit_log_events_immutable
    BEFORE UPDATE OR DELETE ON audit_log_events
    FOR EACH ROW EXECUTE FUNCTION audit_log_events_block_mutation();
