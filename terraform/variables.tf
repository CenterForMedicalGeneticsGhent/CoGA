variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary region for Cloud Run and Artifact Registry"
  type        = string
  default     = "europe-west1"
}

variable "domain_short" {
  description = "Short domain identifier used in institute group naming"
  type        = string
}

variable "app_domain" {
  description = "Public domain used by the HTTPS load balancer"
  type        = string
  default     = "coga.cmgg.be"
}

variable "ch_db_password" {
  description = "Password for clickhouse"
  type        = string
}

variable "pg_db_password" {
  description = "Password for postgress"
  type        = string
}

variable "image" {
  description = "Full container image URL to deploy, e.g. europe-west1-docker.pkg.dev/<project>/<repo>/coga:<tag>"
  type        = string
}

variable "azure_ad_tenant_id" {
  description = "Optional Azure AD tenant id"
  type        = string
  default     = "common"
}

variable "azure_ad_client_id" {
  description = "Optional Azure AD client id"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_ad_client_secret" {
  description = "Deprecated plaintext Azure AD client secret. Leave empty and use azure_ad_client_secret_secret_id instead."
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_ad_client_secret_secret_id" {
  description = "Secret Manager secret id containing Azure AD client secret value"
  type        = string
  default     = "hpotool-azure-ad-client-secret"
}


variable "enable_cmek" {
  description = "Create and manage a CMEK key for storage/build resources"
  type        = bool
  default     = true
}

variable "cmek_key_ring_name" {
  description = "KMS key ring name for CMEK"
  type        = string
  default     = "gen-kms-mgmt-euw1"
}

variable "cmek_key_name" {
  description = "KMS crypto key name for CMEK"
  type        = string
  default     = "gen-kms-mgmt-euw1"
}

variable "cmek_rotation_period" {
  description = "Rotation period for CMEK key"
  type        = string
  default     = "7776000s"
}

variable "cmek_use_hsm" {
  description = "Use HSM protection level for CMEK key"
  type        = bool
  default     = true
}