"""Cloud Run Function 2: Geocoding Worker & Consolidation handler."""

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

from sentinela_pipeline.config import DEFAULT_CONFIG, PipelineConfig
from sentinela_pipeline.consolidation import (
    DatasetExporter,
    SpatialDeduplicator,
    SQLiteRadarBuilder,
)
from sentinela_pipeline.geocoding import (
    AddressCacheManager,
    GeocoderService,
    GoogleMapsClient,
    NominatimClient,
)

logger = logging.getLogger(__name__)


def process_geocoding_message(
    message_payload: Dict[str, Any],
    geocoder: GeocoderService,
) -> Optional[Dict[str, Any]]:
    """Resolves coordinates for an individual geocoding request."""
    address = message_payload.get("address_text")
    if not address:
        return None

    res = geocoder.resolve_address(address)
    if res:
        lat, lon, src = res
        result = dict(message_payload)
        result["latitude"] = lat
        result["longitude"] = lon
        result["geocoding_source"] = src
        result["has_coordinates"] = True
        return result
    return None


def consolidate_and_export_pipeline(
    raw_pois: List[Dict[str, Any]],
    output_dir: str = "/tmp/sentinela_build",
    config: Optional[PipelineConfig] = None,
    gcs_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Deduplicates POIs, compiles SQLite R*Tree, JSON, CSV and uploads to GCS."""
    cfg = config or DEFAULT_CONFIG
    os.makedirs(output_dir, exist_ok=True)

    db_path = os.path.join(output_dir, "sentinela_brasil.db")
    json_path = os.path.join(output_dir, "sentinela_pois_brasil.json")
    csv_path = os.path.join(output_dir, "sentinela_pois_brasil.csv")
    sha_path = os.path.join(output_dir, "SHA256SUMS.txt")

    # 1. Deduplicate
    deduplicator = SpatialDeduplicator(cluster_radius_meters=35.0)
    consolidated = deduplicator.deduplicate(raw_pois)

    # 2. Compile SQLite R*Tree
    builder = SQLiteRadarBuilder(db_path)
    count_saved = builder.build_database(consolidated)

    # 3. Export JSON & CSV
    exporter = DatasetExporter()
    exporter.export_to_json(consolidated, json_path)
    exporter.export_to_csv(consolidated, csv_path)

    # 4. Checksums
    exporter.generate_sha256_sums([db_path, json_path, csv_path], sha_path)

    # 5. Upload to GCS if client provided
    uploaded_files: List[str] = []
    if gcs_client:
        bucket = gcs_client.bucket(cfg.gcs_bucket_name)
        for local_file in [db_path, json_path, csv_path, sha_path]:
            fname = os.path.basename(local_file)
            blob = bucket.blob(f"latest/{fname}")
            blob.upload_from_filename(local_file)
            uploaded_files.append(f"gs://{cfg.gcs_bucket_name}/latest/{fname}")

    return {
        "status": "SUCCESS",
        "total_consolidated_pois": count_saved,
        "files_generated": [db_path, json_path, csv_path, sha_path],
        "uploaded_to_gcs": uploaded_files,
    }


def geocoding_worker_handler(event_or_request: Any) -> Any:
    """Entrypoint for Pub/Sub push or CloudEvent in Cloud Functions."""
    # Support CloudEvents or HTTP POST push
    payload: Dict[str, Any] = {}
    if hasattr(event_or_request, "data") and isinstance(event_or_request.data, dict):
        # CloudEvent
        message = event_or_request.data.get("message", {})
        data_b64 = message.get("data", "")
        if data_b64:
            payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    elif hasattr(event_or_request, "get_json"):
        # HTTP Request
        body = event_or_request.get_json(silent=True) or {}
        message = body.get("message", {})
        data_b64 = message.get("data", "")
        if data_b64:
            payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
        else:
            payload = body

    cache_mgr = AddressCacheManager()
    nom = NominatimClient(min_interval_seconds=1.0)
    gmaps = GoogleMapsClient(api_key=DEFAULT_CONFIG.google_maps_api_key)
    geocoder = GeocoderService(cache_manager=cache_mgr, nominatim_client=nom, google_maps_client=gmaps)

    result = process_geocoding_message(payload, geocoder)
    return json.dumps(result or {"status": "NO_OP"}), 200, {"Content-Type": "application/json"}
