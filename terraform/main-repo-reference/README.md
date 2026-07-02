# Central-infra-repo prerequisites for CoGA

`coga-prerequisites.tf.example` is a ready-to-lift template. Copy it into the central
repo, drop the `.example` suffix, wire the two variables, and apply it **before** the
CoGA repo's `terraform apply`.

## What must exist before CoGA applies

1. **Enabled APIs** on the CoGA project (see the `google_project_service` block).
2. **Three runtime service accounts** with these exact account ids (so the emails the
   CoGA config derives by default line up):
   - `coga-backend-run`
   - `coga-frontend-run`
   - `coga-clickhouse-vm`

   If you use different names, pass the resulting emails into the CoGA config via
   `backend_service_account_email`, `frontend_service_account_email`,
   `clickhouse_vm_service_account_email`.
3. **Project-level IAM role grants** to those SAs (least privilege — see the template).
4. **CMEK key grants**: the Cloud SQL, Compute, and Cloud Storage service agents each
   need `roles/cloudkms.cryptoKeyEncrypterDecrypter` on the CMEK key. (The key itself is
   already managed centrally.)
5. **Project-wide GCS Data Access audit logging** (S-4: byte-level PHI download audit).

## What stays in the CoGA repo (intentionally)

- **Resource-level IAM** on the secrets and buckets the CoGA config creates
  (`secretmanager.secretAccessor`, `storage.objectViewer/objectUser`). Granting IAM on
  your own secret/bucket cannot escalate to project-level roles, and moving it here
  would deadlock (this repo can't grant access to a secret/bucket the CoGA repo hasn't
  created yet). The CoGA pipeline therefore needs `setIamPolicy` only on its *own*
  secrets and buckets — never at project scope.

## Ordering / hand-off contract

```
central repo apply  →  APIs on, SAs exist, project+KMS IAM granted, audit config set
        │
        ▼
CoGA repo apply     →  creates VPC, DBs, Cloud Run, LB, secrets/buckets (+ their
                       resource-level IAM), referencing the SAs by email
```
