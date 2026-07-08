provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  name_prefix = "coga"

  # CMEK key applied uniformly to Cloud SQL, Compute disks, and GCS. Encryption is
  # mandatory (organization policy), so the key is always set — there is no on/off
  # toggle and no Google-managed-key fallback.
  cmek_key = var.cmek_key_self_link

  # Runtime service-account emails. The accounts themselves (and all their IAM role
  # grants + the project's API enablement) are provisioned in the CENTRAL infra repo,
  # not here — see terraform/main-repo-reference/. This config only *references* the
  # SAs, so the CoGA deploy pipeline needs no service-account-admin or project-IAM-admin
  # rights and therefore cannot grant itself privileges. Defaults follow the central
  # repo's naming convention; set the vars if it differs.
  backend_sa_email       = var.backend_service_account_email != "" ? var.backend_service_account_email : "${local.name_prefix}-backend-run@${var.project_id}.iam.gserviceaccount.com"
  frontend_sa_email      = var.frontend_service_account_email != "" ? var.frontend_service_account_email : "${local.name_prefix}-frontend-run@${var.project_id}.iam.gserviceaccount.com"
  clickhouse_vm_sa_email = var.clickhouse_vm_service_account_email != "" ? var.clickhouse_vm_service_account_email : "${local.name_prefix}-clickhouse-vm@${var.project_id}.iam.gserviceaccount.com"

  # Secret Manager secret ids (containers created in secrets.tf; versions added
  # out-of-band — see terraform/README.md).
  secret_ids = {
    secret_key          = "${local.name_prefix}-secret-key"
    integrity_anchor    = "${local.name_prefix}-integrity-anchor-key"
    admin_password      = "${local.name_prefix}-admin-password"
    postgres_password   = "${local.name_prefix}-postgres-password"
    clickhouse_password = "${local.name_prefix}-clickhouse-password"
  }
}
