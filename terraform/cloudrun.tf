# ==========================================
# 3. STATELESS SERVICES (CLOUD RUN)
# ==========================================

# Backend API
resource "google_cloud_run_v2_service" "backend" {
  name     = "coga-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/coga-repo/backend:latest"
      ports {
        container_port = 8000
      }
      env {
        name  = "POSTGRES_HOST"
        value = google_sql_database_instance.postgres.private_ip_address
      }
      env {
        name  = "POSTGRES_USER"
        value = google_sql_user.db_user.name
      }
      env {
        name  = "POSTGRES_PASSWORD"
        value = var.pg_db_password
      }
      env {
        name  = "CLICKHOUSE_HOST"
        value = google_compute_instance.clickhouse.network_interface[0].network_ip
      }
      env {
        name  = "CLICKHOUSE_USER"
        value = "clickhouse_admin"
      }
      env {
        name  = "CLICKHOUSE_PASSWORD"
        value = var.ch_db_password
      }
      env {
        name  = "CLICKHOUSE_HTTP_PORT"
        value = "8123"
      }
    }
    
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
  }
}

# Frontend UI
resource "google_cloud_run_v2_service" "frontend" {
  name     = "coga-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/coga-repo/frontend:latest"
      ports {
        container_port = 3000
      }
      env {
        name  = "VITE_API_BASE_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }
}

# Make both applications publicly accessible on the web
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.viewer"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  name     = google_cloud_run_v2_service.frontend.name
  location = google_cloud_run_v2_service.frontend.location
  role     = "roles/run.viewer"
  member   = "allUsers"
}