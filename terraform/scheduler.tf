# Agendador semanal para disparo da Cloud Run Function Extractor
resource "google_cloud_scheduler_job" "weekly_extraction_job" {
  name        = "sentinela-weekly-extraction-trigger"
  description = "Dispara a extração e consolidação semanal de radares no domingo às 01:00 UTC (22:00 BRT sábado)."
  schedule    = "0 1 * * 0"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.extractor_function.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.pipeline_sa.email
      audience              = google_cloudfunctions2_function.extractor_function.service_config[0].uri
    }
  }

  depends_on = [
    google_project_service.services,
    google_cloudfunctions2_function.extractor_function
  ]
}
