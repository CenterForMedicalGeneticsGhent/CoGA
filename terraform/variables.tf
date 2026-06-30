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
  description = "ClickHouse server container image, pinned to match the local stack."
  type        = string
  default     = "clickhouse/clickhouse-server:25.3"
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
