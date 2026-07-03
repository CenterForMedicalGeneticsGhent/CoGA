variable "project_id" {
  description = "GCP project ID that hosts the CoGA deployment."
  type        = string
}

variable "region" {
  description = "Primary region for Cloud Run, Cloud SQL, ClickHouse, and buckets. Keep in the EU for IVDR data residency."
  type        = string
  default     = "europe-west1"
}

variable "zone" {
  description = "Zone for the ClickHouse Compute Engine instance and its data disk."
  type        = string
  default     = "europe-west1-b"
}

variable "backend_image" {
  description = "Full backend container image URL, e.g. europe-west1-docker.pkg.dev/<project>/<repo>/coga-backend:<tag>."
  type        = string
}

variable "frontend_image" {
  description = "Full frontend container image URL, e.g. europe-west1-docker.pkg.dev/<project>/<repo>/coga-frontend:<tag>."
  type        = string
}

variable "app_domain" {
  description = "Public domain served by the external HTTPS load balancer. A managed TLS cert is provisioned for it; point an A record at the LB IP output."
  type        = string
  default     = "coga.cmgg.be"
}

# ---------------------------------------------------------------------------
# Encryption (CMEK)
# ---------------------------------------------------------------------------

variable "enable_cmek" {
  description = "Use a customer-managed KMS key (CMEK) for Cloud SQL, Compute disks, and GCS buckets. When false, Google-managed keys are used."
  type        = bool
  default     = true
}

variable "cmek_key_self_link" {
  description = "Resource id of the KMS crypto key for CMEK, in the form projects/<p>/locations/<region>/keyRings/<ring>/cryptoKeys/<key>. Must live in the same region as the resources it protects. Required when enable_cmek is true."
  type        = string
  default     = ""

  validation {
    condition     = var.cmek_key_self_link == "" || can(regex("^projects/[^/]+/locations/[^/]+/keyRings/[^/]+/cryptoKeys/[^/]+$", var.cmek_key_self_link))
    error_message = "cmek_key_self_link must be a fully-qualified crypto key id: projects/<p>/locations/<loc>/keyRings/<ring>/cryptoKeys/<key>."
  }
}

# ---------------------------------------------------------------------------
# Database sizing
# ---------------------------------------------------------------------------

variable "db_tier" {
  description = "Cloud SQL machine tier. db-custom-1-3840 (1 vCPU / 3.75GB) is a small-but-real default; scale up for production load."
  type        = string
  default     = "db-custom-1-3840"
}

variable "db_availability_type" {
  description = "Cloud SQL availability: ZONAL (single zone, cheaper) or REGIONAL (HA failover). Use REGIONAL for production."
  type        = string
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.db_availability_type)
    error_message = "db_availability_type must be ZONAL or REGIONAL."
  }
}

variable "db_backup_retained_count" {
  description = "Number of automated Cloud SQL backups to retain."
  type        = number
  default     = 30
}

# ---------------------------------------------------------------------------
# ClickHouse VM
# ---------------------------------------------------------------------------

variable "clickhouse_machine_type" {
  description = "Compute Engine machine type for the self-hosted ClickHouse VM. e2-standard-4 (4 vCPU / 16GB) is a sane analytical starting point."
  type        = string
  default     = "e2-standard-4"
}

variable "clickhouse_data_disk_gb" {
  description = "Size (GB) of the dedicated, snapshot-backed ClickHouse data disk."
  type        = number
  default     = 200
}

variable "clickhouse_image" {
  description = "ClickHouse server container image, digest-pinned to match the local stack (tag kept for readability). Bump the digest alongside the tag."
  type        = string
  default     = "clickhouse/clickhouse-server:25.3@sha256:b627d7a9bc0e0c1bac26cdbe9d2fc6316faa29c5d8a174f28f5abd57d0fa6ba2"
}

variable "clickhouse_snapshot_retention_days" {
  description = "Days to retain daily ClickHouse data-disk snapshots."
  type        = number
  default     = 14
}

# ---------------------------------------------------------------------------
# Cloud Run sizing
# ---------------------------------------------------------------------------

variable "backend_cpu" {
  description = "CPU limit for the backend Cloud Run service."
  type        = string
  default     = "2"
}

variable "backend_memory" {
  description = "Memory limit for the backend Cloud Run service. Reference bootstrap (dbNSFP/HPO) and ClickHouse client buffers want headroom."
  type        = string
  default     = "2Gi"
}

variable "backend_max_instances" {
  description = "Max backend instances. Job workers use FOR UPDATE SKIP LOCKED, so multiple instances are safe."
  type        = number
  default     = 4
}

variable "frontend_max_instances" {
  description = "Max frontend instances."
  type        = number
  default     = 5
}

# ---------------------------------------------------------------------------
# Identity provider (Azure AD / Entra) — optional, wired into the backend env
# ---------------------------------------------------------------------------

variable "azure_ad_tenant_id" {
  description = "Azure AD / Entra tenant id for institutional login. Empty disables Azure auth env."
  type        = string
  default     = ""
}

variable "azure_ad_client_id" {
  description = "Azure AD / Entra application (client) id."
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Cloud Armor (WAF / edge protection)
# ---------------------------------------------------------------------------

variable "enable_cloud_armor" {
  description = "Attach a Cloud Armor security policy (adaptive L7 DDoS, per-IP rate limiting, OWASP CRS WAF) to the load balancer's backend services."
  type        = bool
  default     = true
}

variable "cloud_armor_waf_enforce" {
  description = "Enforce the OWASP CRS WAF rules. false = preview/log-only (recommended until tuned against the genomics API's traffic, to avoid false-positive blocks); true = block matches with 403."
  type        = bool
  default     = false
}

variable "cloud_armor_rate_limit_per_minute" {
  description = "Per-client-IP request budget per minute before throttling (429). Tune to expected peak interactive use."
  type        = number
  default     = 600
}

# ---------------------------------------------------------------------------
# Database privilege separation (P1-3 / P1-4)
# ---------------------------------------------------------------------------

variable "run_db_schema_migrations_on_startup" {
  description = "Whether the API applies Postgres schema DDL + admin seed on startup. true = the app self-migrates as the table owner (current single-DSN deployment). false = migrations run out-of-band as the owner ('python -m backend.app.db_migrate') and the app boots as the restricted runtime role coga_app (which cannot run DDL). Part of the change-controlled DSN flip in docs/db-runtime-role-runbook.md — keep true until POSTGRES_USER is repointed at coga_app in the same deploy."
  type        = bool
  default     = true
}

variable "forwarded_allow_ips" {
  description = "Peers uvicorn trusts X-Forwarded-For from (FORWARDED_ALLOW_IPS). Cloud Run terminates the connection at Google's managed front end, so the immediate peer is a Google-internal IP that varies and the container gets no direct external ingress — '*' is the safe, standard value there and is required for the real client IP to reach the signup rate-limiter and audit log. Narrow to a specific CIDR only if you front the service with your own reverse proxy."
  type        = string
  default     = "*"
}

# ---------------------------------------------------------------------------
# Object storage backend
# ---------------------------------------------------------------------------

variable "storage_backend" {
  description = "Backend for raw family data: local, s3, or gcs. Flip to gcs once the PHI bucket is populated; the backend then serves IGV via IAM-signed URLs and stages imports from gs://."
  type        = string
  default     = "local"

  validation {
    condition     = contains(["local", "s3", "gcs"], var.storage_backend)
    error_message = "storage_backend must be local, s3, or gcs."
  }
}

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

variable "labels" {
  description = "Labels applied to created resources."
  type        = map(string)
  default = {
    app        = "coga"
    managed-by = "terraform"
  }
}
