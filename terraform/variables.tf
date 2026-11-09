variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "thcb-sentinela-radar"
}

variable "region" {
  description = "Default Google Cloud Region (us-central1 is lowest cost in the Americas)"
  type        = string
  default     = "us-central1"
}

variable "dataset_id" {
  description = "BigQuery dataset ID for raw and consolidated radar telemetry"
  type        = string
  default     = "sentinela_radar_data"
}

variable "gcs_bucket_name" {
  description = "Cloud Storage bucket name for compiled SQLite and release datasets"
  type        = string
  default     = "thcb-sentinela-radar-datasets"
}

variable "google_maps_api_key" {
  description = "Google Maps Geocoding API key for fallback resolution"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_repository_app" {
  description = "GitHub repository for Sentinela mobile app (used for WIF federation)"
  type        = string
  default     = "thcborges/sentinela-radar"
}

variable "github_repository_pipeline" {
  description = "GitHub repository for Sentinela data pipeline"
  type        = string
  default     = "thcborges/sentinela-data-pipeline"
}
