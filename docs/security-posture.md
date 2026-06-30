# Security & PHI posture

CoGA stores and serves real patient genomes (families under `data/`), so it is a
PHI system. This is a point-in-time posture review of access control, audit
logging, encryption, and the deployment path, plus the hardening landed
alongside it and the items that remain (mostly deployment/infrastructure, which
the application code cannot enforce on its own).

Legend: ✅ enforced in code · 🟡 partial / config-dependent · ⛔ not yet done
(deployment responsibility).

## 1. Authentication & RBAC

- ✅ **AuthN.** JWT bearer (HS256) with optional Azure AD; local JWT fallback is
  restricted to admins. See `backend/app/dependencies.py`
  (`get_current_user`, `get_current_admin_user`). Roles: `admin`/`superuser` vs
  `viewer` (`ADMIN_ROLES` in `metadata_service.py`).
- ✅ **AuthZ is project-scoped.** Every family/sample/variant endpoint resolves
  access through one checkpoint:
  `build_family_metadata_context` → `get_accessible_family_mapping` →
  `_ensure_user_can_access_metadata_projects` (and the sample equivalent). A
  non-admin may only reach families/samples whose project they belong to; admins
  bypass scoping. List endpoints filter at the SQL level
  (`list_family_records(metadata_project_ids=…)`), not by post-filtering.
- ✅ **Admin-gated mutations.** All destructive / structure-changing operations
  (member edits, ROI, project assignment, deletions, reference-data management)
  require `get_current_admin_user`.
- ✅ **PHI download scoping.** CRAM/BAM endpoints check family + sample access
  before issuing presigned URLs (`routers/cram.py`).
- ✅ **No default secrets in prod.** `Settings.validate_security_defaults`
  refuses to start outside dev/test if `SECRET_KEY` / `POSTGRES_PASSWORD` /
  `ADMIN_PASSWORD` are still placeholders. Passwords are bcrypt-hashed.

**IDOR review:** every endpoint taking a `family_id` / `sample_id` / `project_id`
routes through the scoping checkpoint; reference data (genes, assemblies, CNV
catalogue) is intentionally unscoped (public, non-PHI). No unscoped PHI endpoint
was found.

**Landed in this change:** RBAC depth tests in
`backend/tests/test_access_control.py` covering the previously-untested
cross-user / multi-project scenarios — a viewer is denied a family in a project
they are not in, granted one that shares a project, denied with no projects, and
an admin bypasses scoping. These lock in the access boundary against regression.

## 2. Access / audit logging

- ✅ **Who-accessed-what-when trail.** Request/response middleware
  (`middleware/request_logging.py`) records every authenticated request to
  `audit_log_events` (actor id/email/role, method, path, status, timestamp,
  client IP) via an async queue worker. Failed logins are tracked separately.
- ✅ **PII minimisation.** Query strings are reduced to keys by default
  (`AUDIT_LOG_QUERY_STRING_MODE=keys`); secret-like body fields are masked.
- ✅ **Append-only (new).** `029_audit_log_immutable.sql` adds a trigger that
  blocks `DELETE` and `UPDATE` on `audit_log_events`, with a single carve-out for
  the `ON DELETE SET NULL` user-unlink cascade (column-agnostic jsonb diff), so
  account removal still works while the denormalised `user_email`/`user_role`
  preserve the actor. Verified against live Postgres: insert ok, update/delete
  blocked, user-deletion cascade still nulls `user_id`.
- ✅ **Durable pipeline (new — TF-13 S-5).** A full async queue no longer silently
  drops (`services/event_pipeline.py`): it applies backpressure for up to
  `AUDIT_LOG_BACKPRESSURE_TIMEOUT_SECONDS` and then writes the event synchronously,
  the worker retries failed batch writes (`AUDIT_LOG_MAX_WRITE_ATTEMPTS`), and any
  event that still cannot be persisted is logged at ERROR with its full (already
  sanitised) payload and counted (`dropped_event_count`) for alerting — never lost
  without a trace. The default bound is raised to `AUDIT_LOG_QUEUE_SIZE=10000`;
  `AUDIT_LOG_DROP_ALLOWED=true` restores the old drop-on-full behaviour for low
  overhead and is **refused outside development**.

**Remaining (deployment):**
- ⛔ **Byte-level S3 downloads are not backend-audited.** The backend logs
  *issuance* of a presigned URL but the browser fetches bytes from S3 directly.
  Enable **S3 server access logging / CloudTrail data events** to capture the
  actual object reads.
- 🟡 Request bodies log clinical payloads (only secret-like keys are masked).
  Consider PHI-field masking if bodies are retained long-term.

## 3. Encryption

- ✅ **In transit (app edge).** Presigned S3 URLs are HTTPS; production is
  expected to terminate TLS at the proxy/ingress.
- ✅ **Secrets at rest in DB.** Passwords bcrypt-hashed.
- 🟡 **In transit to datastores (TLS — S-2).** The app now supports TLS to both
  stores: set `POSTGRES_SSLMODE` (e.g. `require`/`verify-full`, passed to asyncpg)
  and `CLICKHOUSE_SECURE=true` (HTTPS; use `CLICKHOUSE_HTTP_PORT=8443`,
  `CLICKHOUSE_VERIFY=true`). Defaults stay plain for local/dev. **Operational
  action:** terminate TLS on the datastores and set these in production.
- ⛔ **At rest (databases).** `docker-compose.yml` runs Postgres/ClickHouse on
  plain Docker volumes with no encryption. For production PHI: use encrypted
  storage (cloud-managed Postgres/ClickHouse with encryption at rest, or
  full-disk/LUKS-encrypted volumes).
- ⛔ **S3 at rest.** The app only *reads* from S3 (no application-side `PutObject`),
  so SSE is a bucket-level responsibility: set a **default bucket encryption**
  policy (SSE-KMS preferred) and a bucket policy that **denies unencrypted
  uploads and non-TLS access** (`aws:SecureTransport=false`).

## 4. S3 / deployment path & PHI scoping

There is **no Terraform/IaC in the repository** yet. When the deployment is
codified, keep PHI scoped with these guardrails:

- **Bucket:** private, `BlockPublicAccess` on all four flags; default SSE-KMS;
  versioning + lifecycle; bucket policy enforcing TLS and encryption.
- **IAM least privilege:** the app role needs only `s3:GetObject`
  (+ `s3:ListBucket`) on the PHI prefix — it does not upload. Scope by prefix; do
  not grant `s3:*`.
- **Network:** prefer a VPC endpoint for S3; keep databases on private subnets.
- **Presigned URLs** (`S3_PRESIGN_EXPIRY_SECONDS`, default 1h) are bearer tokens —
  anyone with the link can fetch within the TTL. Keep the TTL short; rely on the
  per-object scope and the access checks that precede issuance.
- **Secrets:** move DB/ClickHouse passwords out of compose `environment:` into
  Docker secrets or a managed secret store for production; rotate `SECRET_KEY`.
- **Observability:** enable CloudTrail (data events on the PHI bucket) and S3
  access logging — this is also what closes the byte-level audit gap in §2.

## 5. CI enforcement of the gates

Two workflows enforce the gates on every PR and push to `main`:

- **`ci.yml`** — `backend` (`pytest`), `frontend` (`tsc` + `eslint` + `vitest`),
  `smoke` + `e2e` + `e2e-playwright` (real Postgres + ClickHouse), `sbom`
  (CycloneDX), and `catalogue` (test-overview in sync).
- **`security.yml`** — `deps` (blocking `pip-audit --require-hashes` + production
  `npm audit`), `secret-scan` (the gitleaks **binary**, full-history — the licensed
  `gitleaks-action` is not usable under the org), and `codeql` (Python + JS/TS SAST,
  per-PR diff baseline).

All ten checks are **required status checks** on `main` with **strict**
(up-to-date-before-merge) enforcement, so a failing test, a known-vulnerable or
unpinned dependency, a committed secret, or a newly-introduced code-scanning alert
blocks merge (**closes S-6**). Every suppression is recorded in
[SECURITY-AUDIT-ALLOWLIST.md](../SECURITY-AUDIT-ALLOWLIST.md).

## Summary

The application-layer posture is solid and was independently re-audited in 2026-06
(multi-agent review of authz/IDOR, auth, injection, SSRF/upload): consistent
project-scoped RBAC with **no exploitable cross-project IDOR**, a durable
append-only audit trail, authenticated reference endpoints, per-IP signup
throttling, input-size / decompression / path-traversal hardening, PyJWT-based
tokens, and a refuse-to-start guard against default secrets. The supply-chain and
code-scanning gates are required in CI — **S-5 (audit durability), S-6 (required
checks) and S-7 (dependency pinning) are closed**.

The remaining open items are deployment-level and live in the infrastructure
layer, not the application: encryption at rest + TLS for the datastores
(**S-1/S-2**), secrets management (**S-3**), CloudTrail/S3 access logging for
byte-level download audit (**S-4**), and S3 bucket policy / least-privilege IAM /
network posture (**S-8**). See §3–§4 here and [TF-13 §3](regulatory/TF-13-cybersecurity.md).
