# Dataset Sentinela Radar no BigQuery
resource "google_bigquery_dataset" "radar_dataset" {
  dataset_id                  = var.dataset_id
  friendly_name               = "Sentinela Radar Data Lakehouse"
  description                 = "Base pública de telemetria de radares, semáforos, lombadas e pedágios do Brasil."
  location                    = "US"
  default_table_expiration_ms = null # Partições controladas por política de retenção personalizada

  # Permissão de leitura pública com custo zero de processamento para o mantenedor
  # Quem consulta usa seu próprio billing_project_id
  access {
    role          = "READER"
    special_group = "allAuthenticatedUsers"
  }

  access {
    role          = "roles/bigquery.dataEditor"
    user_by_email = google_service_account.pipeline_sa.email
  }

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }

  depends_on = [google_project_service.services]
}

# Tabela permanente de Cache de Geocodificação
resource "google_bigquery_table" "address_cache" {
  dataset_id = google_bigquery_dataset.radar_dataset.dataset_id
  table_id   = "address_geocoding_cache"

  description = "Cache determinístico de endereços geocodificados via OpenStreetMap e Google Maps."

  clustering = ["address_hash"]

  schema = jsonencode([
    { name = "address_hash", type = "STRING", mode = "REQUIRED", description = "SHA-256 do endereço normalizado" },
    { name = "raw_address", type = "STRING", mode = "REQUIRED", description = "Texto bruto do endereço" },
    { name = "normalized_address", type = "STRING", mode = "NULLABLE" },
    { name = "latitude", type = "FLOAT", mode = "NULLABLE" },
    { name = "longitude", type = "FLOAT", mode = "NULLABLE" },
    { name = "precision_level", type = "STRING", mode = "NULLABLE" },
    { name = "geocoding_source", type = "STRING", mode = "NULLABLE" },
    { name = "resolved_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

# Tabela consolidada semanal particionada por data de snapshot
resource "google_bigquery_table" "consolidated_snapshot" {
  dataset_id = google_bigquery_dataset.radar_dataset.dataset_id
  table_id   = "pois_consolidated_snapshot"

  description = "Snapshot consolidado, higienizado e enriquecido dos pontos de fiscalização ativos no Brasil."

  time_partitioning {
    type  = "DAY"
    field = "snapshot_date"
  }

  clustering = ["uf", "poi_type"]

  schema = jsonencode([
    { name = "snapshot_date", type = "DATE", mode = "REQUIRED", description = "Data da extração semanal" },
    { name = "poi_id", type = "INTEGER", mode = "REQUIRED" },
    { name = "poi_type", type = "STRING", mode = "REQUIRED" },
    { name = "latitude", type = "FLOAT", mode = "REQUIRED" },
    { name = "longitude", type = "FLOAT", mode = "REQUIRED" },
    { name = "speed_limit", type = "INTEGER", mode = "NULLABLE" },
    { name = "direction", type = "INTEGER", mode = "NULLABLE" },
    { name = "road_name", type = "STRING", mode = "NULLABLE" },
    { name = "operator", type = "STRING", mode = "NULLABLE" },
    { name = "city", type = "STRING", mode = "NULLABLE" },
    { name = "uf", type = "STRING", mode = "NULLABLE" },
    { name = "toll_fee_car", type = "FLOAT", mode = "NULLABLE" },
    { name = "toll_fee_truck", type = "FLOAT", mode = "NULLABLE" },
    { name = "source_origin", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

# Tabelas RAW particionadas por data de ingestão
locals {
  raw_tables = [
    "raw_antt_pedagios",
    "raw_antt_radares",
    "raw_prf_radares",
    "raw_dnit_pncv",
    "raw_nacional_aberto",
    "raw_osm_comunitario"
  ]
}

resource "google_bigquery_table" "raw_tables" {
  for_each   = toset(locals.raw_tables)
  dataset_id = google_bigquery_dataset.radar_dataset.dataset_id
  table_id   = each.value

  description = "Dados brutos ingeridos da fonte ${each.value} particionados por dia de extração."

  time_partitioning {
    type  = "DAY"
    field = "ingestion_date"
  }

  schema = jsonencode([
    { name = "ingestion_date", type = "DATE", mode = "REQUIRED" },
    { name = "record_id", type = "STRING", mode = "NULLABLE" },
    { name = "payload_json", type = "STRING", mode = "REQUIRED" },
    { name = "has_coordinates", type = "BOOLEAN", mode = "REQUIRED" },
    { name = "address_text", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

# Scheduled Query: Política de retenção > 90 dias mantendo apenas a 1ª extração de cada mês
resource "google_bigquery_data_transfer_config" "retention_prune_query" {
  display_name           = "Sentinela Radar Retention Prune (>90 days)"
  location               = "US"
  data_source_id         = "scheduled_query"
  schedule               = "1 of month 03:00" # Roda todo dia 01 às 03:00 UTC
  destination_dataset_id = google_bigquery_dataset.radar_dataset.dataset_id
  service_account_name   = google_service_account.pipeline_sa.email

  params = {
    query = <<-EOT
      -- Higienização das partições brutas e de snapshot com mais de 90 dias,
      -- preservando exclusivamente a primeira extração de cada mês histórico.
      DELETE FROM `${var.project_id}.${var.dataset_id}.pois_consolidated_snapshot`
      WHERE snapshot_date < DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND snapshot_date NOT IN (
          SELECT MIN(snapshot_date)
          FROM `${var.project_id}.${var.dataset_id}.pois_consolidated_snapshot`
          GROUP BY FORMAT_DATE('%Y-%m', snapshot_date)
        );
    EOT
  }

  depends_on = [
    google_project_service.services,
    google_bigquery_table.consolidated_snapshot
  ]
}
