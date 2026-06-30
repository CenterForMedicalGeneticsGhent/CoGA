provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "this" {}

# GCS service agent — granted CMEK encrypt/decrypt below so buckets can use the key.
data "google_storage_project_service_account" "gcs" {}

locals {
  name_prefix = "coga"

  # CMEK key applied uniformly to Cloud SQL, Compute disks, and GCS when enabled.
  cmek_key = var.enable_cmek ? var.cmek_key_self_link : null

  # Well-known Google service-agent identities that need access to the CMEK key.
  sql_service_agent     = "service-${data.google_project.this.number}@gcp-sa-cloud-sql.iam.gserviceaccount.com"
  compute_service_agent = "service-${data.google_project.this.number}@compute-system.iam.gserviceaccount.com"

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

# Enable the APIs the deployment depends on. Idempotent; left enabled on destroy.
resource "google_project_service" "services" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    # Keyless V4 signed URLs for the GCS storage backend (SignBlob).
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "certificatemanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

# Validate CMEK configuration early with a clear message.
resource "terraform_data" "cmek_guard" {
  count = var.enable_cmek ? 1 : 0

  lifecycle {
    precondition {
      condition     = var.cmek_key_self_link != ""
      error_message = "enable_cmek is true but cmek_key_self_link is empty. Provide a CMEK key id or set enable_cmek = false."
    }
  }
}
