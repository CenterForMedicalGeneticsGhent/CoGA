# ==========================================
# RUNTIME SERVICE ACCOUNTS (least privilege)
# ==========================================

# --- Backend Cloud Run service identity ------------------------------------
resource "google_service_account" "backend" {
  account_id   = "${local.name_prefix}-backend-run"
  display_name = "CoGA backend (Cloud Run)"
}

# Connect to Cloud SQL.
resource "google_project_iam_member" "backend_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Logs + metrics.
resource "google_project_iam_member" "backend_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Sign blobs as itself — required for V4 signed URLs to GCS without a JSON key
# (used by the forthcoming native-GCS storage backend; harmless to grant now).
resource "google_service_account_iam_member" "backend_token_creator" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.backend.email}"
}

# --- Frontend Cloud Run service identity ------------------------------------
resource "google_service_account" "frontend" {
  account_id   = "${local.name_prefix}-frontend-run"
  display_name = "CoGA frontend (Cloud Run)"
}

resource "google_project_iam_member" "frontend_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.frontend.email}"
}

# --- ClickHouse VM identity -------------------------------------------------
resource "google_service_account" "clickhouse_vm" {
  account_id   = "${local.name_prefix}-clickhouse-vm"
  display_name = "CoGA ClickHouse VM"
}

resource "google_project_iam_member" "clickhouse_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.clickhouse_vm.email}"
}

resource "google_project_iam_member" "clickhouse_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.clickhouse_vm.email}"
}
