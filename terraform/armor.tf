# ==========================================
# CLOUD ARMOR (edge WAF / DDoS / rate limiting)
# ==========================================
#
# Attached to the load balancer's backend services (loadbalancer.tf). Provides:
#  - Adaptive Protection: ML-based L7 DDoS defense.
#  - Per-client-IP rate limiting (throttle abusive sources).
#  - OWASP CRS preconfigured WAF (SQLi/XSS/RCE/LFI), at the lowest sensitivity to
#    limit false positives. Shipped in PREVIEW (log-only) by default so the team can
#    review hits against the genomics API before enforcing (cloud_armor_waf_enforce).

resource "google_compute_security_policy" "lb" {
  count = var.enable_cloud_armor ? 1 : 0
  name  = "${local.name_prefix}-armor"
  type  = "CLOUD_ARMOR"

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
    }
  }

  # Per-IP rate limit (always enforced — low false-positive risk).
  rule {
    action      = "throttle"
    priority    = 1000
    description = "Per-IP request rate limit"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.cloud_armor_rate_limit_per_minute
        interval_sec = 60
      }
    }
  }

  # OWASP CRS preconfigured WAF. preview = log-only until cloud_armor_waf_enforce.
  rule {
    action      = "deny(403)"
    priority    = 2000
    preview     = !var.cloud_armor_waf_enforce
    description = "OWASP CRS: SQLi / XSS / RCE / LFI"
    match {
      expr {
        expression = <<-EXPR
          evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})
          || evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})
          || evaluatePreconfiguredWaf('rce-v33-stable', {'sensitivity': 1})
          || evaluatePreconfiguredWaf('lfi-v33-stable', {'sensitivity': 1})
        EXPR
      }
    }
  }

  # Default: allow (the app enforces authn/authz behind the LB).
  rule {
    action      = "allow"
    priority    = 2147483647
    description = "Default allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}
