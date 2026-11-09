"""Geocoder service orchestrating cache, Nominatim, and Google Maps fallback."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .cache_manager import AddressCacheManager
from .google_maps_client import GoogleMapsClient
from .nominatim_client import NominatimClient

logger = logging.getLogger(__name__)


class GeocoderService:
    """Orchestrates geocoding with multi-tier resolution: Cache -> Nominatim -> Google Maps."""

    def __init__(
        self,
        cache_manager: AddressCacheManager,
        nominatim_client: Optional[NominatimClient] = None,
        google_maps_client: Optional[GoogleMapsClient] = None,
    ) -> None:
        self.cache = cache_manager
        self.nominatim = nominatim_client or NominatimClient()
        self.google_maps = google_maps_client or GoogleMapsClient()

    def resolve_address(self, address_text: str) -> Optional[Tuple[float, float, str]]:
        """Resolves (latitude, longitude, source_name) for a given address string."""
        if not address_text or not address_text.strip():
            return None

        # Tier 1: Cache
        cached = self.cache.get(address_text)
        if cached and cached.get("latitude") is not None and cached.get("longitude") is not None:
            return float(cached["latitude"]), float(cached["longitude"]), cached.get("geocoding_source", "CACHE")

        # Tier 2: OpenStreetMap Nominatim
        nom_result = self.nominatim.geocode(address_text)
        if nom_result:
            lat, lon, _ = nom_result
            self.cache.set(address_text, lat, lon, source="NOMINATIM_OSM", precision="APPROXIMATE")
            return lat, lon, "NOMINATIM_OSM"

        # Tier 3: Google Maps Fallback
        gmaps_result = self.google_maps.geocode(address_text)
        if gmaps_result:
            lat, lon, precision = gmaps_result
            self.cache.set(address_text, lat, lon, source="GOOGLE_MAPS", precision=precision)
            return lat, lon, "GOOGLE_MAPS"

        # Record unresolved in cache to avoid redundant lookups in the same cycle
        self.cache.set(address_text, None, None, source="UNRESOLVED", precision="NONE")
        return None

    def enrich_records(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """Enriches a list of records with geocoded coordinates when missing.

        Returns (enriched_records, count_newly_resolved).
        """
        enriched: List[Dict[str, Any]] = []
        newly_resolved = 0

        for rec in records:
            copy_rec = dict(rec)
            # Already has coordinates
            if copy_rec.get("latitude") is not None and copy_rec.get("longitude") is not None:
                enriched.append(copy_rec)
                continue

            address = copy_rec.get("address_text") or copy_rec.get("rodovia_via") or ""
            if not address:
                enriched.append(copy_rec)
                continue

            res = self.resolve_address(address)
            if res:
                lat, lon, src = res
                copy_rec["latitude"] = lat
                copy_rec["longitude"] = lon
                copy_rec["geocoding_source"] = src
                copy_rec["has_coordinates"] = True
                newly_resolved += 1

            enriched.append(copy_rec)

        return enriched, newly_resolved
