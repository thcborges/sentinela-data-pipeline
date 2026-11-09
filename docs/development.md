# Guia de Desenvolvimento, Testes e CI/CD 🛠️

## 1. Ambiente Local de Desenvolvimento

### 1.1. Pré-requisitos
* Python 3.12 ou superior.
* Git configurado.
* Google Cloud SDK (`gcloud`) para deploys manuais.

### 1.2. Criação do Ambiente Virtual
```bash
git clone git@github.com:thcborges/sentinela-data-pipeline.git
cd sentinela-data-pipeline

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"
```

---

## 2. Padrões de Código e Qualidade

O projeto utiliza um conjunto estrito de ferramentas para garantir manutenibilidade e confiabilidade:

### 2.1. Formatação e Linting com Ruff
```bash
# Verifica problemas de linting e regras de estilo
ruff check .

# Aplica correções automáticas seguras
ruff check --fix .

# Verifica formatação de código
ruff format --check .
```

### 2.2. Tipagem Estática com Mypy
```bash
mypy src/
```

---

## 3. Metodologia BDD/TDD e Execução de Testes

Seguindo as diretrizes de engenharia do Sentinela:
* Nenhum código de produção deve ser inserido sem um teste que garanta seu comportamento.
* A cobertura de testes do repositório deve ser obrigatoriamente **$\ge 90\%$**.

### 3.1. Execução de Testes com Pytest e Relatório de Cobertura
```bash
pytest --cov=sentinela_pipeline --cov-report=term-missing --cov-report=xml --cov-fail-under=90
```

### 3.2. Execução Rápida via Unittest (Sem Dependências Externas)
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 4. Estrutura de Testes Automatizados

* `tests/test_extractors.py`: Testa todos os 5 extratores de dados (`AnttExtractor`, `PrfExtractor`, `DnitExtractor`, `OpenClawExtractor`, `OsmExtractor`) com payloads reais e mocks de HTTP.
* `tests/test_cache_manager.py`: Testa normalização de strings, cálculo determinístico de hash SHA-256 e sincronização do cache com BigQuery.
* `tests/test_geocoding.py`: Valida a política multi-tier (`Cache ➔ Nominatim ➔ Google Maps`), rate-limiting e tratamento de falhas.
* `tests/test_deduplicator.py`: Testa distância Haversine, preservação de pistas duplas de sentidos opostos e compatibilidade semântica de tipos.
* `tests/test_sqlite_builder.py`: Testa compilação do banco SQLite com extensão nativa R\*Tree e consultas espaciais de bounding box.
* `tests/test_dataset_exporter.py`: Valida geração dos arquivos JSON, CSV e integridade dos checksums em `SHA256SUMS.txt`.
* `tests/test_functions_entrypoint.py`: Valida a execução das duas Cloud Run Functions simulando eventos CloudEvent e chamadas HTTP.

---

## 5. Esteira de Integração Contínua (GitHub Actions)

O workflow `.github/workflows/ci.yml` executa automaticamente a cada push e Pull Request:
1. Instalação limpa em ambiente Ubuntu 22.04 com Python 3.12.
2. Execução do `ruff check` e `ruff format --check`.
3. Execução do `mypy src/`.
4. Execução do `pytest` com barreira rígida de cobertura `--cov-fail-under=90`.
