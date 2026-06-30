# CoGA — Terraform (Google Cloud)

Infrastructure-as-code for deploying CoGA to GCP. Derived from the first-draft
`add/tf-deploy-scripts` branch and reworked to boot cleanly and meet the
deployment-level security items tracked in
[TF-13 §3](../docs/regulatory/TF-13-cybersecurity.md) and
[security-posture.md §3–4](../docs/security-posture.md).

## Architecture

```text
                         Internet
                            │  HTTPS (managed cert, app_domain)
                  ┌─────────▼──────────┐
                  │  External HTTPS LB │   /api/*  → backend
                  │  (path routing)    │   /*      → frontend
                  └────┬──────────┬────┘
        serverless NEG │          │ serverless NEG
              ┌────────▼───┐  ┌───▼─────────┐
              │ backend    │  │ frontend    │   Cloud Run (ingress: internal-LB)
              │ Cloud Run  │  │ Cloud Run   │
              └─────┬──────┘  └─────────────┘
        VPC connector│ (PRIVATE_RANGES_ONLY)
          ┌──────────┼───────────────┐
          │          │               │
   ┌──────▼─────┐ ┌──▼───────────┐  Secret Manager (secret_key_ref)
   │ Cloud SQL  │ │ ClickHouse   │  GCS: phi + refdata buckets (CMEK)
   │ Postgres16 │ │ COS VM + disk│  Cloud NAT (VM egress), PGA (Google APIs)
   │ private IP │ │ private IP   │
   └────────────┘ └──────────────┘
```

- **Same-origin by design**: the LB routes `/api/*` to the backend and everything
  else to the frontend, so there is no CORS hop and the backend is never reachable
  on its public `run.app` URL (`ingress = INTERNAL_LOAD_BALANCER`).
- **Backend workers**: `min_instance_count = 1` + always-allocated CPU keeps the
  in-process workers alive; job claims use `FOR UPDATE SKIP LOCKED`, so scaling past
  one instance is safe.
- **ClickHouse** has no managed GCP equivalent → a Container-Optimized OS VM with a
  dedicated, snapshot-backed CMEK data disk. Its password is read from Secret
  Manager at boot, never placed in instance metadata or state.

## Prerequisites (provisioned outside this config)

1. **Two/three projects** (or one): the CoGA runtime project, the shared Artifact
   Registry project, and a KMS project. Adjust to your landing zone.
2. **A KMS crypto key** (`cmek_key_self_link`) in the same region as the resources.
3. **A GCS state bucket** — private, versioned, CMEK, tight IAM. It holds the Cloud
   SQL user password in plaintext (see "Secrets" below).
4. **Workload Identity Federation** for GitHub Actions + the service accounts named
   in [`.github/workflows/build.yml`](../.github/workflows/build.yml)
   (`reg-*-gh-actions`, `reg-*-cb-runner`, `coga-*-gh-actions`).
5. **Artifact Registry repo** (the workflow uses `gen-ghreg-shared-gbl`).
6. **DNS** control for `app_domain`.

GitHub repo secrets used by CI: `GCP_REGISTRY_PROJECT_ID`,
`GCP_CLOUDBUILD_STAGING_BUCKET`, `GCP_WIF_PROVIDER`, `GCP_COGA_PROJECT_ID`,
`GCP_COGA_TF_STATE_BUCKET`, `GCP_COGA_CMEK_KEY_SELF_LINK`; repo var
`GCP_REGION_SHORT`.

## Secrets (bootstrap before first apply)

Terraform creates the secret **containers**; the **values** are added out-of-band so
app secrets never pass through Terraform variables. Because the Cloud SQL user and
the Cloud Run revisions resolve `latest` at apply time, do a one-time bootstrap:

```bash
PROJECT=my-coga-project
cd terraform

# 1. Create just the secret containers first.
tofu apply -target='google_secret_manager_secret.app' \
  -var="project_id=$PROJECT" -var="cmek_key_self_link=..." \
  -var="backend_image=placeholder" -var="frontend_image=placeholder"

# 2. Add a version to each (use strong, generated values).
printf '%s' "$SECRET_KEY"  | gcloud secrets versions add coga-secret-key           --data-file=- --project "$PROJECT"
printf '%s' "$ANCHOR_KEY"  | gcloud secrets versions add coga-integrity-anchor-key --data-file=- --project "$PROJECT"
printf '%s' "$ADMIN_PW"    | gcloud secrets versions add coga-admin-password       --data-file=- --project "$PROJECT"
printf '%s' "$PG_PW"       | gcloud secrets versions add coga-postgres-password    --data-file=- --project "$PROJECT"
printf '%s' "$CH_PW"       | gcloud secrets versions add coga-clickhouse-password  --data-file=- --project "$PROJECT"
```

- `SECRET_KEY` and `INTEGRITY_ANCHOR_SIGNING_KEY` must be **distinct**.
- The backend refuses to start in production with placeholder secrets, so these must
  be real before the first full apply ([config.py](../backend/app/core/config.py)).

## Deploy

CI ([`.github/workflows/build.yml`](../.github/workflows/build.yml)) does it end to
end on push to `main`: builds both images from the **repo-root context** (so
`APP_VERSION`/`GIT_SHA` are baked in and `scripts/` is included), then
`terraform init/plan/apply`. PRs run `terraform fmt -check` + `validate` only — no
apply.

Manual:

```bash
cd terraform
tofu init -backend-config="bucket=<state-bucket>" -backend-config="prefix=coga/dev"
tofu apply -var="project_id=..." -var="cmek_key_self_link=..." \
           -var="backend_image=..." -var="frontend_image=..."
```

After apply, point an A record for `app_domain` at the `load_balancer_ip` output;
the Google-managed cert provisions once DNS resolves (can take ~15–60 min).

## How this maps to the security items

| Item | Status in this config |
|---|---|
| S-1 encryption at rest | CMEK on Cloud SQL, both disks, and both buckets (`enable_cmek`) |
| S-2 TLS to datastores | Postgres: Cloud SQL Python Connector (mTLS + verify-full-grade) over private IP, `ssl_mode=ENCRYPTED_ONLY`. ClickHouse: HTTPS on 8443 with a private CA; backend verifies (`CLICKHOUSE_CA_CERT` + `SERVER_HOST_NAME`) |
| S-3 secrets management | Secret Manager + `secret_key_ref`; VM reads its password at boot |
| S-4 byte-level PHI audit | GCS Data Access audit logs enabled |
| S-8 network posture | Private IPs, no public DB ingress, least-privilege SAs, NAT/PGA |
| P1-13 backups | Cloud SQL PITR + retained backups; daily ClickHouse disk snapshots |

## Object storage backend

The app supports a native **GCS** backend (`backend/app/core/object_storage.py`):
IGV alignments are served as IAM-signed (keyless `SignBlob`) URLs and family-package
imports stage from `gs://`. It is wired but **off by default** (`var.storage_backend
= "local"`); `GCS_BUCKET` is always pointed at the `phi` bucket, so activation is a
single change:

1. Upload family data to the `phi` bucket (`<family_id>/<file>` layout).
2. Set `storage_backend = "gcs"` and apply.

The backend SA has `objectViewer` on the `phi` bucket + `serviceAccountTokenCreator`
on itself, and the IAM Credentials API is enabled — all required for signed URLs.

## Known residuals / deferred (follow-ups)

- **ClickHouse cert rotation.** The server cert is long-lived (10y) and fetched at
  boot; re-issuing it (or rotating the CA) requires restarting the VM to refetch.
- **ClickHouse graceful shutdown.** Best-effort `docker stop -t 90` on VM shutdown +
  `MIGRATE` on maintenance. For a guaranteed 5-min flush window, move ClickHouse to a
  GKE StatefulSet with `terminationGracePeriodSeconds = 300`.
- **State holds the SQL user password.** The Cloud SQL user password is read from
  Secret Manager into state; keep the state bucket private + CMEK. App secrets are
  *not* in state (referenced by `secret_key_ref`).
- **Cloud Armor / WAF** and **IVDR change control** (TF-18 + DPIA update adding
  Google as sub-processor, TF-13/TF-15 IFU) are out of scope here.
