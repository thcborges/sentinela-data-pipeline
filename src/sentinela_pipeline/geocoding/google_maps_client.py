"""Google Maps Geocoding API client used as official fallback."""

import json
import logging
from typing import Any, Dict, Optional, Tuple
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """Client for Google Maps Geocoding API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://maps.googleapis.com/maps/api/geocode/json",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def geocode(self, query: str, timeout: int = 15) -> Optional[Tuple[float, float, str]]:
        """Geocodes an address string to (latitude, longitude, precision_level).

        Returns None if API key is missing, not found, or on error.
        """
        if not self.api_key:
            logger.debug("Google Maps API key not configured; skipping fallback.")
            return None

        if not query or not query.strip():
            return None

        params = {
            "address": query.strip(),
            "key": self.api_key,
            "components": "country:BR",
            "language": "pt-BR",
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SentinelaDataPipeline/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                status = data.get("status")
                if status != "OK":
                    logger.debug("Google Maps Geocoding returned status: %s", status)
                    return None

                results = data.get("results", [])
                if not results:
                    return None

                first = results[0]
                geometry = first.get("geometry", {})
                location = geometry.get("location", {})
                lat = float(location["lat"])
                lon = float(location["lng"])
                location_type = geometry.get("location_type", "APPROXIMATE")
                return lat, lon, location_type
        except Exception as exc:
            logger.warning("Google Maps geocoding error for query '%s': %s", query, exc)
            return None
