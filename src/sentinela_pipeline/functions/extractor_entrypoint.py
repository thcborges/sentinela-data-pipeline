"""Cloud Run Function 1: Extractor & Staging handler."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from sentinela_pipeline.config import DEFAULT_CONFIG, PipelineConfig
from sentinela_pipeline.extractors import (
    AnttExtractor,
    DnitExtractor,
    OpenClawExtractor,
    OsmExtractor,
    PrfExtractor,
)
from sentinela_pipeline.geocoding.cache_manager import AddressCacheManager

logger = logging.getLogger(__name__)


def extract_and_stage_pipeline(
    config: Optional[PipelineConfig] = None,
    bq_client: Optional[Any] = None,
    pubsub_publisher: Optional[Any] = None,
    sample_records: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Core execution logic for extraction and staging."""
    cfg = config or DEFAULT_CONFIG
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    samples = sample_records or {}

    logger.info("Starting Sentinela extraction and staging for date %s...", today_str)

    # 1. ANTT Pedagios
    antt_ext = AnttExtractor(cfg.antt_pedagios_url, cfg.antt_radares_url, cfg.user_agent)
    pedagios = antt_ext.extract_pedagios(custom_data=samples.get("antt_pedagios"))

    # 2. ANTT Radares
    antt_radares = antt_ext.extract_radares(custom_data=samples.get("antt_radares"))

    # 3. PRF Radares
    prf_ext = PrfExtractor(cfg.prf_radares_url, cfg.user_agent)
    prf_radares = prf_ext.extract_radares(custom_data=samples.get("prf_radares"))

    # 4. DNIT PNCV
    dnit_ext = DnitExtractor(user_agent=cfg.user_agent)
    dnit_radares = dnit_ext.extract_pncv(raw_records=samples.get("dnit_pncv"))

    # 5. OpenStreetMap Comunitário
    osm_sample = samples.get("osm_comunitario")
    osm_pois = OsmExtractor.parse_payload(osm_sample) if osm_sample else []

    # 6. OpenClaw / Cadastro Nacional Aberto (27 UFs)
    openclaw_ext = OpenClawExtractor(cfg.openclaw_base_url, cfg.user_agent)
    if "openclaw_raw" in samples:
        openclaw_with_coords = []
        openclaw_needs_geocode = []
        for r in samples["openclaw_raw"]:
            norm = openclaw_ext.normalize_record(r)
            if norm["has_coordinates"]:
                openclaw_with_coords.append(norm)
            elif norm["address_text"]:
                openclaw_needs_geocode.append(norm)
    else:
        # In live execution, extracts all UFs
        openclaw_with_coords, openclaw_needs_geocode = openclaw_ext.extract_all_ufs(cfg.brazilian_ufs)

    # Cache check for records needing geocode
    cache = AddressCacheManager(bq_client=bq_client)
    uncached_for_pubsub: List[Dict[str, Any]] = []

    for item in openclaw_needs_geocode:
        addr = item.get("address_text")
        if addr and not cache.get(addr):
            uncached_for_pubsub.append(item)

    # Publish to Pub/Sub topic if publisher client provided
    published_count = 0
    if pubsub_publisher and uncached_for_pubsub:
        topic_path = f"projects/{cfg.project_id}/topics/{cfg.pubsub_topic}"
        for item in uncached_for_pubsub:
            data_bytes = json.dumps(item).encode("utf-8")
            try:
                pubsub_publisher.publish(topic_path, data=data_bytes)
                published_count += 1
            except Exception as e:
                logger.warning("Failed to publish geocoding task: %e", e)

    summary = {
        "status": "SUCCESS",
        "ingestion_date": today_str,
        "counts": {
            "antt_pedagios": len(pedagios),
            "antt_radares": len(antt_radares),
            "prf_radares": len(prf_radares),
            "dnit_pncv": len(dnit_radares),
            "osm_comunitario": len(osm_pois),
            "openclaw_with_coordinates": len(openclaw_with_coords),
            "openclaw_needs_geocoding": len(openclaw_needs_geocode),
            "geocoding_tasks_published": published_count,
        },
    }
    logger.info("Extraction completed: %s", summary["counts"])
    return summary


def extract_and_stage_handler(request: Any) -> Any:
    """HTTP Cloud Function handler entrypoint for Cloud Scheduler."""
    result = extract_and_stage_pipeline()
    return json.dumps(result), 200, {"Content-Type": "application/json"}
