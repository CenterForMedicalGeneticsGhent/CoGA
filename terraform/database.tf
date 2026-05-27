# ==========================================
# 2. MANAGED DATABASES (POSTGRES & CLICKHOUSE)
# ==========================================

resource "google_sql_database_instance" "postgres" {
  name             = "coga-postgres-db"
  database_version = "POSTGRES_16"
  region           = var.region
  depends_on       = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier = "db-f1-micro" # Scale up as needed for production workloads
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc_network.id
    }
  }
  deletion_protection = true
}

resource "google_sql_user" "db_user" {
  name     = "coga_admin"
  instance = google_sql_database_instance.postgres.name
  password = var.pg_db_password
}

# ClickHouse hosted on Compute Engine Container-Optimized OS
resource "google_compute_instance" "clickhouse" {
  name         = "coga-clickhouse-vm"
  machine_type = "e2-medium"
  zone         = "${var.region}-a"

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 50
      type  = "pd-ssd" # Fast solid-state storage for analytical engine queries
    }
  }

  network_interface {
    network    = google_compute_network.vpc_network.id
    subnetwork = google_compute_subnetwork.subnet.id
    # No external public IP assigned for security
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    docker run -d \
      --name clickhouse-server \
      --restart always \
      -p 8123:8123 -p 9000:9000 \
      -v /var/lib/clickhouse:/var/lib/clickhouse \
      -e CLICKHOUSE_DB=coga_analytics \
      -e CLICKHOUSE_USER=clickhouse_admin \
      -e CLICKHOUSE_PASSWORD=${var.ch_db_password} \
      -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
      clickhouse/clickhouse-server:25.3
  EOT
}

# Allow internal traffic to ClickHouse ports
resource "google_compute_firewall" "allow_internal_db" {
  name    = "allow-internal-db-traffic"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["8123", "9000"]
  }

  source_ranges = ["10.0.0.0/24", "10.8.0.0/28"]
}
