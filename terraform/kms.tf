# ==========================================
# CMEK SERVICE-AGENT GRANTS
# ==========================================
#
# When CMEK is enabled, the Cloud SQL, Compute Engine, and Cloud Storage service
# agents must each be able to encrypt/decrypt with the key BEFORE the resources
# that reference it are created. The key itself is created/managed outside this
# config (passed in via cmek_key_self_link) so the same key can be shared and
# rotated centrally.

resource "google_kms_crypto_key_iam_member" "sql" {
  count         = var.enable_cmek ? 1 : 0
  crypto_key_id = var.cmek_key_self_link
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${local.sql_service_agent}"
}

resource "google_kms_crypto_key_iam_member" "compute" {
  count         = var.enable_cmek ? 1 : 0
  crypto_key_id = var.cmek_key_self_link
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${local.compute_service_agent}"
}

resource "google_kms_crypto_key_iam_member" "storage" {
  count         = var.enable_cmek ? 1 : 0
  crypto_key_id = var.cmek_key_self_link
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}
