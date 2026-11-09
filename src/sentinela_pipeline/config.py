"""Configuration settings for Sentinela Data Pipeline."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class PipelineConfig:
    project_id: str = os.getenv("GCP_PROJECT_ID", "thcb-sentinela-radar")
    region: str = os.getenv("GCP_REGION", "us-central1")
    dataset_id: str = os.getenv("BQ_DATASET_ID", "sentinela-radar-data")
    gcs_bucket_name: str = os.getenv("GCS_BUCKET_NAME", "thcb-sentinela-radar-datasets")
    pubsub_topic: str = os.getenv("PUBSUB_GEOCODING_TOPIC", "geocoding-requests")
    google_maps_api_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # API Endpoints
    antt_pedagios_url: str = (
        "https://dados.antt.gov.br/dataset/a7e1e12d-f8e8-40cd-bc1f-57973a4a4a6d/"
        "resource/d400debd-8058-4971-9625-8b614b08cf9c/download/dados-dos-praas-de-pedgio.json"
    )
    antt_radares_url: str = (
        "https://dados.antt.gov.br/dataset/79d287f4-f5ca-4385-a17c-f61f53831f17/"
        "resource/81c5895f-7e59-4397-ad25-43c87d3acef5/download/dados-dos-radares10_2026.json"
    )
    prf_radares_url: str = (
        "https://script.google.com/macros/s/"
        "AKfycbwnuoKDXO_3-d5hp-FSLBDRxZQhsC-WHTPIEKthAUNEDA6xsWH6EWZiE6HDz2vDZQOS2g/exec"
    )
    openclaw_base_url: str = (
        "https://servidor3.lucas.inf.br/openclaw/radar/api.pse?rota=/api/v1/status/estados/"
    )
    nominatim_base_url: str = "https://nominatim.openstreetmap.org/search"
    google_geocode_base_url: str = "https://maps.googleapis.com/maps/api/geocode/json"

    # User-Agent strictly compliant with OSM Nominatim Usage Policy
    user_agent: str = (
        "SentinelaRadarDataPipeline/1.0 (+https://github.com/thcborges/sentinela-data-pipeline)"
    )

    # 27 Brazilian Federated Units
    brazilian_ufs: List[str] = field(
        default_factory=lambda: [
            "SP", "RJ", "MG", "PR", "RS", "SC", "BA", "PE", "DF", "GO",
            "ES", "CE", "MT", "MS", "PA", "PB", "RN", "AL", "SE", "PI",
            "MA", "TO", "RO", "AC", "AP", "RR", "AM",
        ]
    )


DEFAULT_CONFIG = PipelineConfig()
