"""OpenStreetMap Nominatim Geocoding API Client with strict 1 req/sec rate limiting."""

import json
import logging
import time
from typing import Optional, Tuple
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class NominatimClient:
    """Client for OpenStreetMap Nominatim with rate limiting conforming to OSM usage policy."""

    def __init__(
        self,
        base_url: str = "https://nominatim.openstreetmap.org/search",
        user_agent: str = "SentinelaRadarDataPipeline/1.0 (+https://github.com/thcborges/sentinela-data-pipeline)",
        min_interval_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url
        self.user_agent = user_agent
        self.min_interval = min_interval_seconds
        self._last_request_time: float = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Enforces at least min_interval_seconds between consecutive requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def geocode(self, query: str, timeout: int = 15) -> Optional[Tuple[float, float, str]]:
        """Geocodes an address string to (latitude, longitude, display_name).

        Returns None if not found or on error.
        """
        if not query or not query.strip():
            return None

        self._wait_for_rate_limit()

        params = {
            "q": query.strip(),
            "format": "jsonv2",
            "countrycodes": "br",
            "limit": 1,
            "addressdetails": 1,
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data or not isinstance(data, list):
                    return None
                best = data[0]
                lat = float(best["lat"])
                lon = float(best["lon"])
                display_name = best.get("display_name", "")
                return lat, lon, display_name
        except Exception as exc:
            logger.warning("Nominatim geocoding failed for query '%s': %s", query, exc)
            return None
