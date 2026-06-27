# Runbook — flip the application to the restricted DB role (`coga_app`)

Migration `040_app_runtime_role_privileges.sql` creates a **restricted runtime role
`coga_app`** and revokes `UPDATE`/`DELETE`/`TRUNCATE` on the append-only tables
(`audit_log_events`, `clinical_audit_events`, `report_signouts`). It ships in
**fallback mode**: the role exists (`NOLOGIN`) but the application still connects as the
table **owner**, so nothing changes at runtime yet.

This runbook performs the **coordinated DSN flip** that makes the application connect as
`coga_app`. That is what actually closes P1-4's owner-bypass gap: as a non-owner the
runtime role cannot `ALTER TABLE … DISABLE TRIGGER`, cannot `SET session_replication_role`
(superuser-only), and cannot `UPDATE`/`DELETE` the append-only tables — so it can neither
edit/remove an audit row or signed report nor re-chain an interior edit.

> **Regulatory note (IVDR / TF-09b REQ-TRACE-008):** until this flip is done, the running
> application credential *is* the owner and the owner-bypass tampering remains undetectable
> by the hash chain. The flip + the deferred external chain-head anchor together close that
> gap. Treat this as a change-controlled deployment (CMGG SOP H11.1-OP5).

## Invariant: migrations stay as owner, the app runs as `coga_app`

| Connection | Role | Why |
| --- | --- | --- |
| Schema migrations / `init_postgres_schema` | **owner** (current `DATABASE_URL` role) | needs `CREATE`/`ALTER TABLE`, trigger management, `GRANT` |
| Application runtime | **`coga_app`** | least privilege; cannot bypass the append-only controls |

Do **not** make migrations run as `coga_app` — it deliberately cannot create or alter
tables or manage triggers.

## Steps

1. **Pick a secret.** Generate a strong password for `coga_app` and store it in the secret
   manager the deployment already uses (do **not** commit it). 
2. **Enable login** (run once, as owner/superuser):
   ```sql
   ALTER ROLE coga_app WITH LOGIN PASSWORD '<from-secret-manager>';
   ```
   (Leaving it `NOLOGIN` until now means no passwordless login ever existed.)
3. **Split the DSNs.**
   - Keep the existing owner DSN as a **migration-only** secret (used by the migration/CI
     step that runs `init_postgres_schema`).
   - Point the **application** `DATABASE_URL` at `coga_app`:
     `postgresql+asyncpg://coga_app:<secret>@<host>:<port>/<db>`.
4. **Connection pooler (PgBouncer / RDS Proxy), if any.** Configure the app's pool to
   authenticate as `coga_app`. Transaction-pooling mode is fine — the app connects
   *directly* as `coga_app` (no `SET ROLE`), so nothing leaks across pooled sessions.
5. **Deploy** the app with the new DSN. Run migrations first (as owner), then start the app
   (as `coga_app`).
6. **Verify** (see below). 
7. **Rollback** (if needed): repoint the application `DATABASE_URL` back to the owner role
   and redeploy. No schema change is involved, so rollback is immediate.

## Verification

- The app boots, reads, and writes normally (sign-out, classification, audit all work),
  and **account/family deletion still works** (the `ON DELETE SET NULL` cascades do not need
  the runtime role to hold `UPDATE` on the append-only tables).
- As `coga_app`, the forbidden operations are refused. Spot-check:
  ```sql
  SET ROLE coga_app;
  UPDATE clinical_audit_events SET summary = summary;          -- ERROR: permission denied
  DELETE FROM report_signouts;                                  -- ERROR: permission denied
  ALTER TABLE audit_log_events DISABLE TRIGGER USER;            -- ERROR: must be owner
  RESET ROLE;
  ```
- The automated proof is `backend/tests/integration/test_app_role_privileges.py`
  (CI `smoke` job), which asserts exactly these allow/deny outcomes plus the cascade.

## Future schema changes

Any **new append-only table** must repeat the `REVOKE UPDATE, DELETE, TRUNCATE … FROM
coga_app;` from migration 040 — the `ALTER DEFAULT PRIVILEGES` in 040 otherwise grants the
new table full CRUD to `coga_app`.
