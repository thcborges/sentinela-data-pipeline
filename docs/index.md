# Documentação Técnica: Sentinela Data Pipeline 📚

Bem-vindo à documentação técnica do **Sentinela Data Pipeline**. Este repositório é responsável por orquestrar a ingestão massiva, geocodificação inteligente com cache e compilação de bases de dados de fiscalização eletrônica e tráfego viário no Brasil.

---

## 🗺️ Índice Geral de Documentos

1. [**Arquitetura do Sistema (`architecture.md`)**](architecture.md)
   * Visão geral dos componentes no Google Cloud Platform (GCP).
   * Desacoplamento via Cloud Run Functions e Cloud Pub/Sub.
   * Estratégia de concorrência e reaproveitamento do tempo ocioso de APIs.
   * Diagramas de fluxo C4 e Mermaid.

2. [**Modelagem de Dados e BigQuery (`bigquery-datasets.md`)**](bigquery-datasets.md)
   * Estrutura e schemas detalhados do dataset público `sentinela_radar_data`.
   * Tabelas RAW particionadas por data de ingestão.
   * Tabela `address_geocoding_cache` e clusterização por hash determinístico.
   * Tabela `pois_consolidated_snapshot` particionada semanalmente.
   * Scheduled Query de retenção (> 90 dias com manutenção da 1ª extração do mês).
   * Modelo de leitura pública de custo zero (`--billing_project_id`).

3. [**Pipeline de Geocodificação e Cache (`geocoding-pipeline.md`)**](geocoding-pipeline.md)
   * Desafio dos dados sem coordenadas no Inmetro/OpenClaw.
   * Algoritmo de normalização e hashing SHA-256 de logradouros brasileiros.
   * Cliente OpenStreetMap Nominatim e política estrita de rate-limit (1 req/s).
   * Fallback controlado para Google Maps Geocoding API com tetos de cota.
   * Ciclo de vida da resolução de endereços.

4. [**Infraestrutura como Código com Terraform (`terraform-gcp.md`)**](terraform-gcp.md)
   * Provisionamento em `us-central1` (região mais econômica das Américas).
   * Ativação e configuração de APIs no projeto `thcb-sentinela-radar`.
   * Políticas de menor privilégio IAM e Service Accounts.
   * Configuração de Workload Identity Federation (WIF) para o GitHub Actions sem chaves estáticas.
   * Instruções de execução do `terraform apply`.

5. [**Integração com o Aplicativo Sentinela (`mobile-integration.md`)**](mobile-integration.md)
   * Compilação do banco SQLite compilado com extensão espacial nativa **R\*Tree**.
   * Exportação dos artefatos `sentinela_brasil.db`, `sentinela_pois_brasil.json`, `sentinela_pois_brasil.csv` e `SHA256SUMS.txt`.
   * Armazenamento no bucket privado do Cloud Storage (`thcb-sentinela-radar-datasets`).
   * Espelhamento via GitHub Actions para a CDN pública de releases (`data-latest`).
   * Download 100% gratuito e offline-first para os motoristas.

6. [**Guia de Desenvolvimento e CI/CD (`development.md`)**](development.md)
   * Configuração do ambiente local de desenvolvimento com Python 3.12.
   * Execução da suíte de testes com `pytest` e cobertura $\ge 90\%$.
   * Linting estrito com `ruff` e tipagem estática com `mypy`.
   * Esteiras de integração contínua no GitHub Actions.
