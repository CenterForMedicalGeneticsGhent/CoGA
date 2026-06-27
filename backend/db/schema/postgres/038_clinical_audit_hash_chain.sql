-- P1-4: per-family tamper-evidence hash chain on clinical_audit_events.
--
-- row_hash binds each row's immutable content to the previous row's hash (per
-- family), so deleting/reordering/editing a row becomes detectable. Additive
-- columns only: ALTER ADD COLUMN is DDL and is NOT blocked by the row-level
-- BEFORE UPDATE trigger; once written, row_hash/prev_hash are themselves immutable
-- (the trigger's column-agnostic comparison covers them). Historical rows keep NULL
-- hashes — the verifier treats the first non-null row_hash as the chain origin; no
-- backfill is done here (backfill is a privileged, trigger-bypassing maintenance op).
ALTER TABLE clinical_audit_events ADD COLUMN IF NOT EXISTS row_hash  TEXT;
ALTER TABLE clinical_audit_events ADD COLUMN IF NOT EXISTS prev_hash TEXT;

-- The chain is partitioned + ordered on the IMMUTABLE family_identifier (not family_id,
-- which the ON DELETE SET NULL cascade nulls). Index it to keep the per-write chain-head
-- read and the verifier walk cheap.
CREATE INDEX IF NOT EXISTS idx_clinical_audit_events_chain
    ON clinical_audit_events (family_identifier, created_at DESC, id DESC);
