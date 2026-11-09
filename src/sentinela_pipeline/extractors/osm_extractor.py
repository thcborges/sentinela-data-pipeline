"""Extractor for OpenStreetMap community POIs (radars, bumps, tolls, traffic lights)."""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OsmExtractor:
    """Parses and normalizes OpenStreetMap nodes and tags into standard POI records."""

    @staticmethod
    def parse_payload(payload_str_or_dict: Any) -> List[Dict[str, Any]]:
        """Parses OSM elements into clean POI records."""
        data = (
            json.loads(payload_str_or_dict)
            if isinstance(payload_str_or_dict, str)
            else payload_str_or_dict
        )
        elements = data.get("elements", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        pois: List[Dict[str, Any]] = []
        for elem in elements:
            if not isinstance(elem, dict):
                continue

            lat = elem.get("lat") or elem.get("latitude")
            lon = elem.get("lon") or elem.get("longitude")
            if lat is None or lon is None:
                continue

            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                continue
            if lat_f == 0.0 or lon_f == 0.0:
                continue

            tags = elem.get("tags", {}) if isinstance(elem.get("tags"), dict) else {}
            poi_id = elem.get("id") or elem.get("osm_id")

            # Classification
            highway = tags.get("highway", "")
            barrier = tags.get("barrier", "")
            enforcement = tags.get("enforcement", "")
            traffic_calming = tags.get("traffic_calming", "")
            amenity = tags.get("amenity", "")

            maxspeed_str = "".join(filter(str.isdigit, str(tags.get("maxspeed", ""))))
            speed_limit = int(maxspeed_str) if maxspeed_str else None

            road_name = (
                tags.get("name")
                or tags.get("ref")
                or tags.get("description")
                or tags.get("road_name")
                or ""
            )

            poi_type = "FIXED_RADAR"
            if barrier == "toll_booth":
                poi_type = "TOLL_BOOTH"
            elif highway == "toll_gantry":
                poi_type = "FREE_FLOW_TOLL"
            elif traffic_calming == "bump" or traffic_calming == "table" or traffic_calming == "hump":
                poi_type = "PHYSICAL_SPEED_BUMP"
            elif traffic_calming == "cushion" or "redutor" in road_name.lower():
                poi_type = "ELECTRONIC_SPEED_BUMP"
            elif amenity == "police" or "policia" in road_name.lower() or "polícia" in road_name.lower():
                poi_type = "HIGHWAY_PATROL"
            elif enforcement == "red_light" or tags.get("camera:traffic_signals") == "yes":
                poi_type = "TRAFFIC_LIGHT_RADAR" if speed_limit else "RED_LIGHT_CAMERA"
            elif highway == "speed_camera":
                poi_type = "FIXED_RADAR"

            # Parse direction / heading
            direction_raw = tags.get("direction")
            direction: Optional[int] = None
            if direction_raw:
                try:
                    direction = int(float(direction_raw)) % 360
                except (ValueError, TypeError):
                    direction = None

            pois.append({
                "source": "OSM_COMUNITARIO",
                "osm_id": str(poi_id),
                "poi_type": poi_type,
                "latitude": lat_f,
                "longitude": lon_f,
                "speed_limit": speed_limit,
                "direction": direction,
                "road_name": road_name,
                "operator": tags.get("operator", ""),
                "address_text": road_name,
            })
        return pois
