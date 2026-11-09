# Tópico principal de requisições de geocodificação
resource "google_pubsub_topic" "geocoding_topic" {
  name = "geocoding-requests"

  message_retention_duration = "604800s" # 7 dias

  depends_on = [google_project_service.services]
}

# Tópico de Dead Letter para requisições com falha permanente
resource "google_pubsub_topic" "geocoding_dlq" {
  name = "geocoding-requests-dlq"

  depends_on = [google_project_service.services]
}

# Subscrição padrão com dead-letter configurado
resource "google_pubsub_subscription" "geocoding_sub" {
  name  = "geocoding-worker-sub"
  topic = google_pubsub_topic.geocoding_topic.id

  ack_deadline_seconds = 600

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.geocoding_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}
