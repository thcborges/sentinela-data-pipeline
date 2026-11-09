output "gcp_project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "gcp_region" {
  description = "GCP Region (us-central1)"
  value       = var.region
}

output "bigquery_dataset_public_reference" {
  description = "Referência pública do dataset no BigQuery (para consultas externas com --billing_project_id)"
  value       = "${var.project_id}.${var.dataset_id}"
}

output "gcs_releases_bucket" {
  description = "Nome do bucket GCS privado para datasets"
  value       = google_storage_bucket.datasets_bucket.name
}

output "pubsub_geocoding_topic" {
  description = "Nome do tópico de requisições de geocodificação"
  value       = google_pubsub_topic.geocoding_topic.name
}

output "workload_identity_provider_name" {
  description = "Identificador do WIF Provider para configuração no GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "github_actions_service_account" {
  description = "Email da Service Account do GitHub Actions para Workload Identity"
  value       = google_service_account.github_actions_sa.email
}

output "extractor_function_uri" {
  description = "URI da Cloud Run Function de extração"
  value       = google_cloudfunctions2_function.extractor_function.service_config[0].uri
}
