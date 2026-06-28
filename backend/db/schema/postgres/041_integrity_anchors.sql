-- P1-4 follow-up: external SIGNED CHAIN-HEAD ANCHOR.
--
-- The per-family hash chains (038/039) detect tampering by anyone who cannot recompute
-- them, but an OWNER who DISABLEs the trigger can re-chain an interior edit (recompute
-- row_hash/prev_hash for it and every successor) into a self-consistent chain, and can
-- truncate a chain to zero rows — both pass verify_*_chain. This table periodically
-- records every chain's HEAD (per family, per table) and SIGNS the snapshot with an
-- Ed25519 key the database role does not hold, so re-chaining or truncation SINCE a
-- retained signed anchor becomes detectable by a verifier that does not trust the DB.
--
-- One row = one whole-system anchor (all families, both tables, captured atomically).
-- Append-only (like 032/033). The chain of anchors (prev_anchor_hash/anchor_hash) makes
-- deletion/replacement of an INTERIOR anchor detectable; deletion of the TAIL anchors is
-- only caught by an out-of-band retained copy (the deferred export seam). See
-- services/integrity_anchor_service.py for the honest trust boundary.

CREATE TABLE IF NOT EXISTS integrity_anchors (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anchor_seq       BIGINT NOT NULL UNIQUE,             -- total order over anchors (clock-independent)
    created_at       TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    prev_anchor_hash TEXT,                               -- anchor_hash of anchor_seq-1 (NULL = genesis)
    anchor_root      TEXT NOT NULL,                      -- sha256 over the canonical sorted heads
    anchor_hash      TEXT NOT NULL,                      -- chain_row_hash(prev_anchor_hash, signed_core)
    heads            JSONB NOT NULL,                     -- sorted [{family_identifier, table, height, head_row_hash}]
    chain_count      INTEGER NOT NULL,                   -- len(heads)
    key_id           TEXT NOT NULL,                      -- signing key id (or 'unsigned')
    algo             TEXT NOT NULL DEFAULT 'ed25519',    -- signature algorithm ('ed25519' | 'unsigned')
    public_key       TEXT,                               -- base64 raw Ed25519 public key (auditor reference)
    signature        TEXT                                -- base64 Ed25519 signature over canonical_json(signed_core)
);

CREATE INDEX IF NOT EXISTS idx_integrity_anchors_seq ON integrity_anchors (anchor_seq DESC);

-- Append-only: a signed anchor must never change. No FK carve-out (no nullable FKs), so
-- ANY update or delete is rejected.
CREATE OR REPLACE FUNCTION integrity_anchors_block_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'integrity_anchors is append-only; DELETE is not permitted';
    END IF;
    RAISE EXCEPTION 'integrity_anchors is append-only; UPDATE is not permitted';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS integrity_anchors_immutable ON integrity_anchors;
CREATE TRIGGER integrity_anchors_immutable
    BEFORE UPDATE OR DELETE ON integrity_anchors
    FOR EACH ROW EXECUTE FUNCTION integrity_anchors_block_mutation();

-- Restricted runtime role (040): the app appends + reads anchors but must not rewrite or
-- remove them (the explicit REVOKE every new append-only table must repeat — 040's note).
GRANT SELECT, INSERT ON integrity_anchors TO coga_app;
REVOKE UPDATE, DELETE, TRUNCATE ON integrity_anchors FROM coga_app;
