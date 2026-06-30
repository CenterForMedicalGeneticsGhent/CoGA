# ==========================================
# CLICKHOUSE TLS (TF-13 S-2)
# ==========================================
#
# Encrypts the backend↔ClickHouse link. A private CA + server cert are generated
# locally; ClickHouse serves HTTPS on 8443 and the backend verifies the cert
# against the CA. The cert pins both a DNS SAN (used for verification when the
# backend connects by IP) and the VM's static internal IP.
#
# The CA cert is public and wired straight into the backend env. The server key +
# cert are stored in Secret Manager and fetched by the VM at boot (so the key is
# never in instance metadata).
#
# Rotation: the cert is long-lived (10y) and re-issued ~30 days before expiry on a
# subsequent apply; a re-issue requires restarting the VM to refetch. The CA key +
# server key live in Terraform state — keep the state bucket private + CMEK.

locals {
  clickhouse_tls_dns = "coga-clickhouse"
}

resource "tls_private_key" "ca" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "ca" {
  private_key_pem       = tls_private_key.ca.private_key_pem
  is_ca_certificate     = true
  validity_period_hours = 87600 # 10 years
  early_renewal_hours   = 720

  subject {
    common_name  = "CoGA ClickHouse CA"
    organization = "CMGG"
  }

  allowed_uses = ["cert_signing", "crl_signing", "digital_signature"]
}

resource "tls_private_key" "clickhouse" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_cert_request" "clickhouse" {
  private_key_pem = tls_private_key.clickhouse.private_key_pem

  subject {
    common_name  = local.clickhouse_tls_dns
    organization = "CMGG"
  }

  dns_names    = [local.clickhouse_tls_dns]
  ip_addresses = [google_compute_address.clickhouse.address]
}

resource "tls_locally_signed_cert" "clickhouse" {
  cert_request_pem   = tls_cert_request.clickhouse.cert_request_pem
  ca_private_key_pem = tls_private_key.ca.private_key_pem
  ca_cert_pem        = tls_self_signed_cert.ca.cert_pem

  validity_period_hours = 87600 # 10 years
  early_renewal_hours   = 720

  allowed_uses = ["server_auth", "digital_signature", "key_encipherment"]
}

# --- Server key + cert in Secret Manager (fetched by the VM at boot) --------

resource "google_secret_manager_secret" "clickhouse_tls" {
  for_each  = toset(["key", "cert"])
  secret_id = "${local.name_prefix}-clickhouse-tls-${each.key}"
  labels    = var.labels

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "clickhouse_tls_key" {
  secret      = google_secret_manager_secret.clickhouse_tls["key"].id
  secret_data = tls_private_key.clickhouse.private_key_pem
}

resource "google_secret_manager_secret_version" "clickhouse_tls_cert" {
  secret      = google_secret_manager_secret.clickhouse_tls["cert"].id
  secret_data = tls_locally_signed_cert.clickhouse.cert_pem
}

resource "google_secret_manager_secret_iam_member" "clickhouse_vm_tls" {
  for_each  = google_secret_manager_secret.clickhouse_tls
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.clickhouse_vm.email}"
}
