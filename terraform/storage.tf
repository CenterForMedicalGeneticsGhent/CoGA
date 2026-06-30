# ==========================================
# OBJECT STORAGE (PHI family data + reference data)
# ==========================================
#
# NOTE: the backend's object-storage layer is currently S3/boto3-only
# (backend/app/core/object_storage.py). A native GCS backend is a separate code
# change (tracked as a follow-up). These buckets are provisioned now so the
# infrastructure, IAM, and audit posture are ready:
#  - phi: raw family data (CRAM/BAM + family packages) — read-only to the app.
#  - refdata: reference data (dbNSFP, HPO, clinical CNVs) mounted into the backend.

resource "google_storage_bucket" "phi" {
  name                        = "${var.project_id}-${local.name_prefix}-phi"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = var.labels

  versioning {
    enabled = true
  }

  dynamic "encryption" {
    for_each = local.cmek_key == null ? [] : [local.cmek_key]
    content {
      default_kms_key_name = encryption.value
    }
  }

  lifecycle_rule {
    condition {
      age        = 30
      with_state = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }

  depends_on = [google_kms_crypto_key_iam_member.storage]
}

resource "google_storage_bucket" "refdata" {
  name                        = "${var.project_id}-${local.name_prefix}-refdata"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = var.labels

  versioning {
    enabled = true
  }

  dynamic "encryption" {
    for_each = local.cmek_key == null ? [] : [local.cmek_key]
    content {
      default_kms_key_name = encryption.value
    }
  }

  depends_on = [google_kms_crypto_key_iam_member.storage]
}

# --- App access (least privilege) ------------------------------------------

# PHI bucket: the app only READS family bytes (presigned/streamed). Viewer only.
resource "google_storage_bucket_iam_member" "backend_phi_reader" {
  bucket = google_storage_bucket.phi.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.backend.email}"
}

# Reference data is mounted read-write so first-run bootstrap can populate it.
resource "google_storage_bucket_iam_member" "backend_refdata_user" {
  bucket = google_storage_bucket.refdata.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.backend.email}"
}

# --- S-4: byte-level PHI download audit ------------------------------------
# Presigned/direct object reads bypass the app, so capture them via GCS Data
# Access audit logs (the GCP equivalent of S3 access logging / CloudTrail data
# events). NOTE: this is project-wide for storage.googleapis.com.
resource "google_project_iam_audit_config" "storage_data_access" {
  project = var.project_id
  service = "storage.googleapis.com"

  audit_log_config {
    log_type = "DATA_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
}
