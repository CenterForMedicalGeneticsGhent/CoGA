# ==========================================
# 1. NETWORKING & PRIVATE CONNECTIONS
# ==========================================

resource "google_compute_network" "vpc_network" {
  name                    = "coga-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "coga-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc_network.id
}

# Required for Cloud SQL Private IP placement
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "coga-private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

# Connector allowing Cloud Run to access the private VPC
resource "google_vpc_access_connector" "connector" {
  name          = "coga-vpc-connector"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc_network.name
}
