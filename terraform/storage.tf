# Bucket privado para releases compiladas do banco SQLite e datasets
resource "google_storage_bucket" "datasets_bucket" {
  name                        = var.gcs_bucket_name
  location                    = "US"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced" # Bucket 100% privado

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.services]
}

# Permissão de escrita para a Service Account da pipeline
resource "google_storage_bucket_iam_member" "pipeline_sa_writer" {
  bucket = google_storage_bucket.datasets_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissão de leitura para a Service Account do GitHub Actions
resource "google_storage_bucket_iam_member" "github_reader" {
  bucket = google_storage_bucket.datasets_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.github_actions_sa.email}"
}
