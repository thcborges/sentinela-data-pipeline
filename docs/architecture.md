# Arquitetura do Sistema: Sentinela Data Pipeline 🏛️

## 1. Visão Geral e Contexto

O **Sentinela Data Pipeline** opera como a espinha dorsal de inteligência geoespacial do ecossistema Sentinela. O aplicativo móvel é estritamente *100% offline-first* e não executa chamadas pesadas de rede durante a condução do veículo. Cabe a este pipeline em nuvem coletar, higienizar, geocodificar e compilar a base nacional de radares, publicando-a de forma versionada.

---

## 2. Diagrama de Fluxo e Componentes GCP

```mermaid
flowchart TD
    subgraph SchedulerLayer [Agendamento no GCP - us-central1]
        CronExtract["Cloud Scheduler:<br/>0 1 * * 0 (Domingo 01:00 UTC)<br/>22:00 BRT Sábado"]
        CronPrune["Cloud Scheduler:<br/>1 of month 03:00 UTC"]
    end

    subgraph ComputeLayer [Execução Serverless no Cloud Run Functions]
        CronExtract --> Func1["Cloud Run Function 1:<br/>sentinela-extractor-staging<br/>(Python 3.12, 2 GiB, timeout 3600s)"]
        
        Func1 --> ExtANTT["AnttExtractor"]
        Func1 --> ExtPRF["PrfExtractor"]
        Func1 --> ExtDNIT["DnitExtractor"]
        Func1 --> ExtOpenClaw["OpenClawExtractor (27 UFs)"]
        Func1 --> ExtOSM["OsmExtractor"]
    end

    subgraph StorageLayer [Lakehouse & BigQuery Dataset: sentinela_radar_data]
        Func1 --> RawTables[("Tabelas RAW Particionadas:<br/>• raw_antt_pedagios<br/>• raw_antt_radares<br/>• raw_prf_radares<br/>• raw_dnit_pncv<br/>• raw_nacional_aberto<br/>• raw_osm_comunitario")]
        
        AddressCache[("Tabela de Cache de Geocodificação:<br/>address_geocoding_cache<br/>(Clusterizada por address_hash)")]
        
        ConsolidatedSnapshot[("Tabela Consolidada Semanal:<br/>pois_consolidated_snapshot<br/>(Particionada por snapshot_date)")]
    end

    subgraph MessagingLayer [Cloud Pub/Sub & Geocoding Worker]
        Func1 -- "Endereços sem GPS<br/>(Não encontrados no Cache)" --> Topic["Pub/Sub: geocoding-requests"]
        Topic --> Func2["Cloud Run Function 2:<br/>sentinela-geocoding-worker<br/>(max_instance_count = 1)"]
        
        Func2 --> OSMNominatim["1º: OSM Nominatim<br/>(1 req/s, User-Agent)"]
        Func2 -.-> GoogleMaps["2º Fallback:<br/>Google Maps Geocoding API"]
        Func2 --> AddressCache
    end

    subgraph ExportLayer [Compilação & Distribuição de Artefatos]
        ConsolidatedSnapshot --> Compiler["Compilador SQLite R*Tree, JSON & CSV"]
        Compiler --> GCSBucket[("Cloud Storage (Privado):<br/>gs://thcb-sentinela-radar-datasets/latest/<br/>• sentinela_brasil.db<br/>• sentinela_pois_brasil.json<br/>• sentinela_pois_brasil.csv<br/>• SHA256SUMS.txt")]
    end

    subgraph DistributionLayer [Espelhamento Seguro para Usuários Finais]
        CronGH["GitHub Actions Semanal:<br/>Domingo 03:00 UTC (2h após GCP)"] --> GHAWorkflow["sync-radar-dataset.yml<br/>(sentinela-radar)"]
        GHAWorkflow -- "Auth via Workload Identity (WIF)" --> GCSBucket
        GHAWorkflow --> GHRelease["GitHub Releases CDN:<br/>tag data-latest"]
        GHRelease --> MobileApp["Sentinela Mobile App<br/>(Download via Wi-Fi ou Móvel)"]
    end

    CronPrune --> BQTransfer["Scheduled Query:<br/>DELETE partições > 90 dias<br/>exceto 1ª de cada mês"]
    BQTransfer --> RawTables
    BQTransfer --> ConsolidatedSnapshot
```

---

## 3. Decisões Arquiteturais Fundamentais

### 3.1. Duas Cloud Run Functions Desacopladas via Pub/Sub
* **Problema:** A extração das 27 UFs do cadastro nacional identifica milhares de radares cadastrados pelo Inmetro que possuem endereço/logradouro, mas não latitude e longitude. A geocodificação no OpenStreetMap Nominatim exige estritamente um intervalo mínimo de 1 segundo entre requisições. Tentar geocodificar todos os pontos dentro de uma única execução linear geraria timeouts de função e risco de esgotamento de memória.
* **Solução:**
  1. A **Function 1 (`sentinela-extractor-staging`)** executa aos domingos às 01:00 UTC. Ela extrai os dados das APIs oficiais, grava as tabelas RAW particionadas no BigQuery, consulta o cache de endereços já resolvidos e publica mensagens individuais no Pub/Sub `geocoding-requests` apenas para os endereços pendentes.
  2. A **Function 2 (`sentinela-geocoding-worker`)** consome a fila do Pub/Sub. Configurada com `max_instance_count = 1`, ela garante serialização rigorosa das requisições para respeitar a cota do Nominatim (1 req/s), preenchendo a tabela permanente `address_geocoding_cache`.

### 3.2. Otimização do Tempo Ocioso de Extração
Durante a paginação das 27 UFs pela API do OpenClaw, pequenas pausas de cooldown e latências de rede ocorrem naturalmente.
O pipeline utiliza processamento assíncrono para que, a cada página de dados recebida contendo endereços não geocodificados, esses registros sejam imediatamente normalizados, verificados contra o cache em memória e despachados para o Pub/Sub sem bloquear o loop de extração.

### 3.3. Snapshot Semanal e Limpeza de Radares Inexistentes
Em vez de depender de flags manuais de status que podem ficar desatualizadas nos órgãos emissores, cada extração semanal captura um **snapshot completo** da malha viária ativa.
* Radares desativados ou removidos pelas concessionárias deixam de figurar na tabela consolidada mais recente.
* A rastreabilidade histórica é mantida íntegra, pois todas as partições anteriores permanecem arquivadas no BigQuery.
