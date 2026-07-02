# ==========================================
# CLOUD ARMOR (edge WAF / DDoS / rate limiting)
# ==========================================
#
# Attached to the load balancer's backend services (loadbalancer.tf). Provides:
#  - Adaptive Protection: ML-based L7 DDoS defense.
#  - Per-client-IP rate limiting (throttle abusive sources).
#  - OWASP CRS 4.22 preconfigured WAF (SQLi/XSS/RCE/LFI), at the lowest sensitivity to
#    limit false positives. Shipped in PREVIEW (log-only) by default so the team can
#    review hits against the genomics API before enforcing (cloud_armor_waf_enforce).
#  - Optional institutional IP allowlist (var.allowed_ingress_cidrs): when set, only
#    those source ranges (UGent/UZ Gent + VPN) reach the app; everything else is denied
#    at the edge, before rate limiting / WAF / the app's own auth.

resource "google_compute_security_policy" "lb" {
  count = var.enable_cloud_armor ? 1 : 0
  name  = "${local.name_prefix}-armor"
  type  = "CLOUD_ARMOR"

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
    }
  }

  # Institutional IP allowlist (UGent / UZ Gent + VPN). Highest priority so it runs
  # FIRST: any source NOT in var.allowed_ingress_cidrs is denied here, before rate
  # limiting / WAF / default-allow. Allowed sources do not match this rule and fall
  # through to the rules below (so they are still rate-limited and WAF-checked). Only
  # emitted when the list is non-empty — empty list keeps the app open (app auth only).
  dynamic "rule" {
    for_each = length(var.allowed_ingress_cidrs) > 0 ? [1] : []
    content {
      action      = "deny(403)"
      priority    = 100
      description = "Allow only institutional (UGent/UZ) source ranges"
      match {
        expr {
          expression = "!(${join(" || ", [for c in var.allowed_ingress_cidrs : "inIpRange(origin.ip, '${c}')"])})"
        }
      }
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

  # OWASP CRS 4.22 preconfigured WAF. preview = log-only until cloud_armor_waf_enforce.
  rule {
    action      = "deny(403)"
    priority    = 2000
    preview     = !var.cloud_armor_waf_enforce
    description = "OWASP CRS 4.22: SQLi / XSS / RCE / LFI"
    match {
      expr {
        expression = <<-EXPR
          evaluatePreconfiguredWaf('sqli-v422-stable', {'sensitivity': 1})
          || evaluatePreconfiguredWaf('xss-v422-stable', {'sensitivity': 1})
          || evaluatePreconfiguredWaf('rce-v422-stable', {'sensitivity': 1})
          || evaluatePreconfiguredWaf('lfi-v422-stable', {'sensitivity': 1})
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
