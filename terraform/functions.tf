# Bucket de staging para código-fonte das Cloud Functions
resource "google_storage_bucket" "function_source_bucket" {
  name                        = "${var.project_id}-function-source"
  location                    = "US"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.services]
}

# Zip do código-fonte da pipeline
data "archive_file" "function_source_zip" {
  type        = "zip"
  output_path = "${path.module}/build/sentinela_pipeline_source.zip"
  source_dir  = "${path.module}/../"
  excludes = [
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "tests",
    "docs",
    "terraform",
    "*.db",
    "*.zip"
  ]
}

resource "google_storage_bucket_object" "function_source_archive" {
  name   = "source-${data.archive_file.function_source_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_source_bucket.name
  source = data.archive_file.function_source_zip.output_path
}

# Cloud Run Function 1: Extractor & Staging (Semanal)
resource "google_cloudfunctions2_function" "extractor_function" {
  name        = "sentinela-extractor-staging"
  location    = var.region
  description = "Extrai radares de todas as fontes oficiais e faz staging no BigQuery."

  build_config {
    runtime     = "python312"
    entry_point = "extract_and_stage_handler"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source_bucket.name
        object = google_storage_bucket_object.function_source_archive.name
      }
    }
  }

  service_config {
    max_instance_count    = 2
    min_instance_count    = 0
    available_memory      = "2Gi"
    timeout_seconds       = 3600 # 60 minutos
    service_account_email = google_service_account.pipeline_sa.email

    environment_variables = {
      GCP_PROJECT_ID          = var.project_id
      GCP_REGION              = var.region
      BQ_DATASET_ID           = var.dataset_id
      GCS_BUCKET_NAME         = var.gcs_bucket_name
      PUBSUB_GEOCODING_TOPIC  = google_pubsub_topic.geocoding_topic.name
    }
  }

  depends_on = [google_project_service.services]
}

# Cloud Run Function 2: Geocoding Worker (Consumidor Pub/Sub)
resource "google_cloudfunctions2_function" "geocoder_function" {
  name        = "sentinela-geocoding-worker"
  location    = var.region
  description = "Consome requisições de geocodificação respeitando rate-limit do OSM e Google Maps fallback."

  build_config {
    runtime     = "python312"
    entry_point = "geocoding_worker_handler"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source_bucket.name
        object = google_storage_bucket_object.function_source_archive.name
      }
    }
  }

  service_config {
    max_instance_count    = 1 # Crucial: Mantém exatamente 1 instância concorrente para respeitar o rate-limit do OSM
    min_instance_count    = 0
    available_memory      = "1Gi"
    timeout_seconds       = 600
    service_account_email = google_service_account.pipeline_sa.email

    environment_variables = {
      GCP_PROJECT_ID       = var.project_id
      GCP_REGION           = var.region
      BQ_DATASET_ID        = var.dataset_id
      GCS_BUCKET_NAME      = var.gcs_bucket_name
      GOOGLE_MAPS_API_KEY  = var.google_maps_api_key
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.geocoding_topic.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  depends_on = [google_project_service.services]
}
