# 1. Service Account da Pipeline de Dados (Execução interna das Functions e BQ)
resource "google_service_account" "pipeline_sa" {
  account_id   = "sentinela-pipeline-sa"
  display_name = "Sentinela Data Pipeline Runtime SA"
  description  = "Service Account para execução das Cloud Functions, BigQuery e Pub/Sub."
}

# Permissões mínimas da Pipeline SA
resource "google_project_iam_member" "pipeline_sa_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
    "roles/run.invoker",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# 2. Service Account para leitura segura do GitHub Actions (Workload Identity)
resource "google_service_account" "github_actions_sa" {
  account_id   = "sentinela-github-actions-sa"
  display_name = "Sentinela GitHub Actions Reader SA"
  description  = "Service Account autenticada via Workload Identity para ler o GCS e publicar na CDN."
}

# 3. Workload Identity Pool para GitHub Actions
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Pool de identidade federada para esteiras do GitHub Actions."

  depends_on = [google_project_service.services]
}

# Provedor OIDC do GitHub no Workload Identity Pool
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc-provider"
  display_name                       = "GitHub OIDC Provider"
  description                        = "Autenticação federada sem chaves JSON estáticas para repositórios GitHub."

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Permissão para o repositório thcborges/sentinela-radar assumir a Service Account
resource "google_service_account_iam_member" "wif_binding_radar" {
  service_account_id = google_service_account.github_actions_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository_app}"
}

# Permissão para o repositório thcborges/sentinela-data-pipeline assumir a Service Account
resource "google_service_account_iam_member" "wif_binding_pipeline" {
  service_account_id = google_service_account.github_actions_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository_pipeline}"
}
