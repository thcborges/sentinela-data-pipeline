# Modelagem de Dados e Google BigQuery: `sentinela_radar_data` 💾

## 1. Visão Geral do Lakehouse no BigQuery

O dataset **`sentinela_radar_data`** no projeto GCP **`thcb-sentinela-radar`** armazena todas as camadas de dados:
* **Camada Raw (Bronze):** Tabelas individuais para cada fonte pública, preservando o JSON bruto e particionadas pelo dia de extração.
* **Camada de Enriquecimento (Silver):** Tabela de cache determinístico de geocodificação indexada por hash SHA-256 do endereço.
* **Camada de Consumo (Gold):** Tabela consolidada semanal com deduplicação espacial (<35m), resolução semântica de tipos e coordenadas prontas para distribuição.

---

## 2. Esquema Detalhado das Tabelas

### 2.1. `pois_consolidated_snapshot` (Gold)
Particionada diariamente por `snapshot_date` e clusterizada por `(uf, poi_type)`.

| Coluna | Tipo | Modo | Descrição |
| :--- | :--- | :--- | :--- |
| `snapshot_date` | `DATE` | REQUIRED | Data da extração e consolidação semanal |
| `poi_id` | `INTEGER` | REQUIRED | Identificador sequencial unificado |
| `poi_type` | `STRING` | REQUIRED | Categoria (`FIXED_RADAR`, `TRAFFIC_LIGHT_RADAR`, `RED_LIGHT_CAMERA`, `ELECTRONIC_SPEED_BUMP`, `PHYSICAL_SPEED_BUMP`, `TOLL_BOOTH`, `FREE_FLOW_TOLL`, `HIGHWAY_PATROL`, `MOBILE_RADAR`) |
| `latitude` | `FLOAT64` | REQUIRED | Latitude decimal (WGS 84) |
| `longitude` | `FLOAT64` | REQUIRED | Longitude decimal (WGS 84) |
| `speed_limit` | `INTEGER` | NULLABLE | Limite regulamentado de velocidade em km/h |
| `direction` | `INTEGER` | NULLABLE | Rumo/azimute de monitoramento da via (0° a 359°) |
| `road_name` | `STRING` | NULLABLE | Nome da via, rodovia ou logradouro |
| `operator` | `STRING` | NULLABLE | Órgão ou concessionária responsável (ex: DNIT, PRF, CET, CCR) |
| `city` | `STRING` | NULLABLE | Município |
| `uf` | `STRING` | NULLABLE | Sigla da Unidade Federativa (27 UFs) |
| `toll_fee_car` | `FLOAT64` | NULLABLE | Valor da tarifa para automóveis (R$) |
| `toll_fee_truck` | `FLOAT64` | NULLABLE | Valor da tarifa para eixos comerciais (R$) |
| `source_origin` | `STRING` | NULLABLE | Origem dos dados primários |
| `ingested_at` | `TIMESTAMP` | NULLABLE | Timestamp UTC da compilação |

---

### 2.2. `address_geocoding_cache` (Silver)
Tabela permanente de cache, clusterizada por `address_hash`.

| Coluna | Tipo | Modo | Descrição |
| :--- | :--- | :--- | :--- |
| `address_hash` | `STRING` | REQUIRED | Hash SHA-256 do endereço normalizado (Primary Key lógica) |
| `raw_address` | `STRING` | REQUIRED | Texto bruto original do logradouro |
| `normalized_address` | `STRING` | NULLABLE | Texto normalizado (uppercase, sem acentos, sem pontuação) |
| `latitude` | `FLOAT64` | NULLABLE | Coordenada latitude inferida pelo geocodificador |
| `longitude` | `FLOAT64` | NULLABLE | Coordenada longitude inferida pelo geocodificador |
| `precision_level` | `STRING` | NULLABLE | Nível de precisão (`EXACT`, `INTERPOLATED`, `STREET`, `APPROXIMATE`, `NONE`) |
| `geocoding_source` | `STRING` | NULLABLE | Fonte que resolveu (`NOMINATIM_OSM`, `GOOGLE_MAPS`, `UNRESOLVED`) |
| `resolved_at` | `TIMESTAMP` | NULLABLE | Data/hora UTC da resolução |

---

### 2.3. Tabelas RAW (Bronze)
Tabelas: `raw_antt_pedagios`, `raw_antt_radares`, `raw_prf_radares`, `raw_dnit_pncv`, `raw_nacional_aberto`, `raw_osm_comunitario`.
Particionadas por `ingestion_date` (`DATE`).

| Coluna | Tipo | Modo | Descrição |
| :--- | :--- | :--- | :--- |
| `ingestion_date` | `DATE` | REQUIRED | Data da ingestão da partição |
| `record_id` | `STRING` | NULLABLE | Identificador original no órgão de origem |
| `payload_json` | `STRING` | REQUIRED | Payload JSON bruto completo original |
| `has_coordinates` | `BOOLEAN` | REQUIRED | Indica se a fonte original já continha GPS |
| `address_text` | `STRING` | NULLABLE | Logradouro construído para eventual geocodificação |
| `ingested_at` | `TIMESTAMP` | REQUIRED | Timestamp UTC da gravação |

---

## 3. Política de Retenção e Higienização de Partições (> 90 Dias)

Para otimizar os custos de armazenamento e preservar a série histórica relevante, uma **Scheduled Query** no BigQuery Data Transfer Service executa no 1º dia de cada mês às 03:00 UTC:

```sql
-- Remove partições anteriores a 90 dias, preservando exclusivamente a primeira extração de cada mês
DELETE FROM `thcb-sentinela-radar.sentinela_radar_data.pois_consolidated_snapshot`
WHERE snapshot_date < DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  AND snapshot_date NOT IN (
    SELECT MIN(snapshot_date)
    FROM `thcb-sentinela-radar.sentinela_radar_data.pois_consolidated_snapshot`
    GROUP BY FORMAT_DATE('%Y-%m', snapshot_date)
  );
```

---

## 4. Como Consultar com Custo Zero para o Mantenedor

O dataset possui leitura pública configurada:
* **Role concedida:** `READER` (`roles/bigquery.dataViewer`) para `allAuthenticatedUsers`.
* **Sem permissão de jobs:** `roles/bigquery.jobUser` **não** é concedido.
* Toda e qualquer query disparada por usuários externos ou analistas de tráfego utiliza o projeto pessoal do consultor como faturador:

```bash
bq query \
  --use_legacy_sql=false \
  --billing_project_id=MEU_PROJETO_GCP \
  "SELECT uf, COUNT(*) as qtd_radares
   FROM \`thcb-sentinela-radar.sentinela_radar_data.pois_consolidated_snapshot\`
   WHERE snapshot_date = CURRENT_DATE() AND poi_type = 'FIXED_RADAR'
   GROUP BY uf
   ORDER BY qtd_radares DESC;"
```
