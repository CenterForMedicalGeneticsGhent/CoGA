-- P1-4: per-family tamper-evidence hash chain on report_signouts.
--
-- Each signed report already carries content_hash (the SHA-256 of its canonical
-- snapshot). row_hash chains that content_hash + the immutable identity across a
-- family's sign-out versions, so deleting or reordering a signed version becomes
-- detectable (content tampering is separately caught by re-verifying content_hash
-- against the snapshot on read). Additive columns; not blocked by the BEFORE UPDATE
-- trigger; pre-chain rows keep NULL hashes (verifier treats the first non-null
-- row_hash as the chain origin). No backfill here.
ALTER TABLE report_signouts ADD COLUMN IF NOT EXISTS row_hash  TEXT;
ALTER TABLE report_signouts ADD COLUMN IF NOT EXISTS prev_hash TEXT;

-- The chain is partitioned on the IMMUTABLE family_identifier (not family_id, which the
-- ON DELETE SET NULL cascade nulls) so a deleted family's signed history stays
-- verifiable. Index it for the per-sign-out chain-head read and the verifier walk.
CREATE INDEX IF NOT EXISTS idx_report_signouts_chain
    ON report_signouts (family_identifier, version DESC);
