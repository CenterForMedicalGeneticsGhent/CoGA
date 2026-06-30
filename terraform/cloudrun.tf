# ==========================================
# STATELESS SERVICES (CLOUD RUN)
# ==========================================
#
# Both services accept traffic only from the external HTTPS load balancer
# (loadbalancer.tf): the LB routes /api/* -> backend and everything else ->
# frontend. Same-origin, so no CORS hop and the backend is never publicly
# reachable on its run.app URL.

# ---- Backend API ----------------------------------------------------------

resource "google_cloud_run_v2_service" "backend" {
  name     = "${local.name_prefix}-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.backend.email

    # GCS volume mounts require the 2nd-gen execution environment.
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      # min 1 keeps the in-process workers (gene-refresh, family-import, audit,
      # ui-event) alive; job claims use FOR UPDATE SKIP LOCKED so >1 is safe.
      min_instance_count = 1
      max_instance_count = var.backend_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      # Private ranges (Cloud SQL + ClickHouse) via the connector; public
      # reference APIs (HGNC/Ensembl/NCBI/ClinGen/dbNSFP/HPO) egress directly.
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.backend_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.backend_cpu
          memory = var.backend_memory
        }
        # Always-allocated CPU so background workers run between requests.
        cpu_idle          = false
        startup_cpu_boost = true
      }

      # Reference data (dbNSFP/HPO/clinical CNVs) persisted in a bucket so it
      # survives cold starts instead of re-downloading into ephemeral memory.
      volume_mounts {
        name       = "refdata"
        mount_path = "/data/ref-data"
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        # Boot runs schema init + seeds (+ optional reference bootstrap): allow
        # generous headroom (~5 min) before the revision is marked failed.
        failure_threshold = 30
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "ENABLE_HSTS"
        value = "true"
      }

      # --- Object storage (PHI family data) ---
      # Defaults to local; flip var.storage_backend to "gcs" once the PHI bucket is
      # populated. GCS_BUCKET is always wired so activation is a single var change.
      # Signed URLs use IAM SignBlob via the backend SA (serviceAccountTokenCreator
      # on itself, granted in iam.tf).
      env {
        name  = "STORAGE_BACKEND"
        value = var.storage_backend
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.phi.name
      }

      # --- Postgres ---
      env {
        name  = "POSTGRES_HOST"
        value = google_sql_database_instance.postgres.private_ip_address
      }
      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }
      env {
        name  = "POSTGRES_DB"
        value = google_sql_database.coga.name
      }
      env {
        name  = "POSTGRES_USER"
        value = google_sql_user.coga.name
      }
      env {
        name  = "POSTGRES_SSLMODE"
        value = "require"
      }
      env {
        name = "POSTGRES_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["postgres_password"].secret_id
            version = "latest"
          }
        }
      }

      # --- ClickHouse (TLS, TF-13 S-2) ---
      env {
        name  = "CLICKHOUSE_HOST"
        value = google_compute_address.clickhouse.address
      }
      env {
        name  = "CLICKHOUSE_HTTP_PORT"
        value = "8443"
      }
      env {
        name  = "CLICKHOUSE_DATABASE"
        value = "coga"
      }
      env {
        name  = "CLICKHOUSE_USER"
        value = "clickhouse_admin"
      }
      env {
        name  = "CLICKHOUSE_SECURE"
        value = "true"
      }
      env {
        name  = "CLICKHOUSE_VERIFY"
        value = "true"
      }
      # Connect by IP but verify against the cert's DNS SAN.
      env {
        name  = "CLICKHOUSE_SERVER_HOST_NAME"
        value = local.clickhouse_tls_dns
      }
      # Private CA (public material) so verification of the server cert succeeds.
      env {
        name  = "CLICKHOUSE_CA_CERT"
        value = tls_self_signed_cert.ca.cert_pem
      }
      env {
        name = "CLICKHOUSE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["clickhouse_password"].secret_id
            version = "latest"
          }
        }
      }

      # --- App secrets ---
      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["secret_key"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "INTEGRITY_ANCHOR_SIGNING_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["integrity_anchor"].secret_id
            version = "latest"
          }
        }
      }

      # --- Admin bootstrap user ---
      env {
        name  = "ADMIN_USERNAME"
        value = "coga-admin"
      }
      env {
        name  = "ADMIN_EMAIL"
        value = "admin@${var.app_domain}"
      }
      env {
        name = "ADMIN_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["admin_password"].secret_id
            version = "latest"
          }
        }
      }

      # --- Web / auth ---
      env {
        name  = "CORS_ORIGINS"
        value = jsonencode(["https://${var.app_domain}"])
      }
      env {
        name  = "AZURE_TENANT_ID"
        value = var.azure_ad_tenant_id
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.azure_ad_client_id
      }
    }

    volumes {
      name = "refdata"
      gcs {
        bucket    = google_storage_bucket.refdata.name
        read_only = false
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_secret_manager_secret_iam_member.backend,
  ]
}

# ---- Frontend UI ----------------------------------------------------------

resource "google_cloud_run_v2_service" "frontend" {
  name     = "${local.name_prefix}-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.frontend.email

    scaling {
      min_instance_count = 1
      max_instance_count = var.frontend_max_instances
    }

    containers {
      image = var.frontend_image

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }
    }
  }

  depends_on = [google_project_service.services]
}

# ---- Public invocation (LB is unauthenticated; ingress blocks direct .run.app) ----

resource "google_cloud_run_v2_service_iam_member" "backend_invoker" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "frontend_invoker" {
  name     = google_cloud_run_v2_service.frontend.name
  location = google_cloud_run_v2_service.frontend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
