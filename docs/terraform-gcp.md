# Infraestrutura como Código no GCP com Terraform ☁️

## 1. Visão Geral da Infraestrutura

Toda a infraestrutura do **Sentinela Data Pipeline** é declarada e versionada em HCL no diretório `terraform/`:
* **Projeto GCP:** `thcb-sentinela-radar`
* **Região:** `us-central1` (região mais econômica das Américas para compute, storage e BigQuery)
* **Padrão de Autenticação:** Workload Identity Federation (WIF) para o GitHub Actions, eliminando o armazenamento de chaves privadas JSON estáticas.

---

## 2. Recursos Provisionados

| Arquivo | Recurso Terraform | Descrição |
| :--- | :--- | :--- |
| `main.tf` | `google_project_service` | Ativação automática de 13 APIs essenciais do GCP. |
| `bigquery.tf` | `google_bigquery_dataset` | Dataset `sentinela_radar_data` com permissão pública de leitura. |
| `bigquery.tf` | `google_bigquery_table` | 6 tabelas RAW, `address_geocoding_cache` e `pois_consolidated_snapshot`. |
| `bigquery.tf` | `google_bigquery_data_transfer_config` | Scheduled Query de retenção mensal para dados > 90 dias. |
| `storage.tf` | `google_storage_bucket` | Bucket privado `thcb-sentinela-radar-datasets` com versionamento e ciclo de vida. |
| `pubsub.tf` | `google_pubsub_topic` | Tópico `geocoding-requests` com dead-letter topic para tolerância a falhas. |
| `functions.tf` | `google_cloudfunctions2_function` | Duas Cloud Run Functions (Python 3.12) para extração e geocodificação. |
| `scheduler.tf` | `google_cloud_scheduler_job` | Cron semanal (Domingo 01:00 UTC) com autenticação OIDC. |
| `iam.tf` | `google_service_account` | Service Accounts com princípio do menor privilégio (`pipeline_sa` e `github_actions_sa`). |
| `iam.tf` | `google_iam_workload_identity_pool` | Pool e Provider OIDC federado com o GitHub Actions. |

---

## 3. Passo a Passo de Execução Local do Terraform

### 3.1. Pré-requisitos
* Terraform CLI instalado (`>= 1.5.0`).
* Google Cloud SDK (`gcloud`) autenticado.

### 3.2. Autenticação no GCP
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project thcb-sentinela-radar
```

### 3.3. Inicialização e Planejamento
```bash
cd terraform
terraform init
terraform plan -out=tfplan
```

### 3.4. Aplicação do Plano
```bash
terraform apply tfplan
```

---

## 4. Configuração do GitHub Actions com Workload Identity

Após o `terraform apply`, os outputs do Terraform fornecerão os valores para configurar a esteira do GitHub Actions sem chaves estáticas:

```bash
terraform output workload_identity_provider_name
# Exemplo: projects/123456789/locations/global/workloadIdentityPools/github-actions-pool/providers/github-oidc-provider

terraform output github_actions_service_account
# Exemplo: sentinela-github-actions-sa@thcb-sentinela-radar.iam.gserviceaccount.com
```

No GitHub (`Settings ➔ Secrets and variables ➔ Actions`), adicione as variáveis:
* `GCP_WORKLOAD_IDENTITY_PROVIDER`: valor do provider retornado.
* `GCP_SERVICE_ACCOUNT`: email da service account retornado.
