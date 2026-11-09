"""Extractor for OpenClaw / National Open Radar dataset covering 27 Brazilian UFs."""

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class OpenClawExtractor:
    """Extracts radar records from OpenClaw across all 27 UFs with cursor-based pagination."""

    def __init__(self, base_url: str, user_agent: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent

    def _fetch_url(self, url: str, timeout: int = 40) -> Optional[Dict[str, Any]]:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data if isinstance(data, dict) else {"data": data}
        except Exception as exc:
            logger.warning("Error fetching URL %s: %s", url, exc)
            return None

    def normalize_record(self, raw: Dict[str, Any], uf_fallback: str = "") -> Dict[str, Any]:
        """Normalizes a single record and flags whether it needs geocoding."""
        lat_val = raw.get("latitude")
        lon_val = raw.get("longitude")

        lat: Optional[float] = None
        lon: Optional[float] = None
        has_coordinates = False

        if lat_val is not None and lon_val is not None:
            try:
                lat = float(str(lat_val).replace(",", ".").strip())
                lon = float(str(lon_val).replace(",", ".").strip())
                if lat != 0.0 and lon != 0.0 and -35.0 <= lat <= 6.0 and -75.0 <= lon <= -30.0:
                    has_coordinates = True
                else:
                    lat, lon = None, None
            except (ValueError, TypeError):
                lat, lon = None, None

        identificador = str(raw.get("id") or raw.get("codigo") or raw.get("numero_inmetro") or "").strip()
        tipo = str(raw.get("tipo_radar") or raw.get("tipo") or raw.get("modalidade") or "Radar").strip()
        uf = str(raw.get("uf") or uf_fallback).strip().upper()
        municipio = str(raw.get("municipio") or "").strip()
        via = str(raw.get("via") or raw.get("rodovia") or raw.get("logradouro") or "").strip()
        num_km = str(raw.get("numero") or raw.get("km") or raw.get("local") or "").strip()
        sentido = str(raw.get("sentido") or "").strip()
        situacao = str(raw.get("situacao") or "Ativo").strip()

        vel_raw = "".join(filter(str.isdigit, str(raw.get("velocidade") or raw.get("velocidade_regulamentada") or "")))
        speed_limit = int(vel_raw) if vel_raw else None

        # Build clean address string for geocoding
        address_parts = []
        if via:
            address_parts.append(via)
        if num_km:
            address_parts.append(num_km)
        if municipio:
            address_parts.append(municipio)
        if uf:
            address_parts.append(uf)
        address_parts.append("Brasil")
        address_text = ", ".join(address_parts) if via else ""

        lower_tipo = tipo.lower()
        if "semaforo" in lower_tipo or "semáforo" in lower_tipo or "vermelho" in lower_tipo:
            poi_type = "TRAFFIC_LIGHT_RADAR" if speed_limit else "RED_LIGHT_CAMERA"
        elif "redutor" in lower_tipo or "lombada" in lower_tipo:
            poi_type = "ELECTRONIC_SPEED_BUMP"
        elif "movel" in lower_tipo or "móvel" in lower_tipo or "portatil" in lower_tipo:
            poi_type = "MOBILE_RADAR"
        else:
            poi_type = "FIXED_RADAR"

        return {
            "source": "OPENCLAW_NACIONAL",
            "identificador": identificador,
            "poi_type": poi_type,
            "has_coordinates": has_coordinates,
            "latitude": lat,
            "longitude": lon,
            "speed_limit": speed_limit,
            "tipo_original": tipo,
            "rodovia_via": via,
            "km_numero": num_km,
            "municipio": municipio,
            "uf": uf,
            "sentido": sentido,
            "situacao": situacao,
            "address_text": address_text,
            "raw_payload": raw,
        }

    def extract_uf(
        self,
        uf: str,
        max_pages: int = 100,
        on_batch_extracted: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Paginates through all radar records for a single UF."""
        all_records: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        uf_upper = uf.upper()

        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/{uf_upper}"
            if cursor:
                url = f"{url}?cursor={urllib.parse.quote(cursor)}"

            data = self._fetch_url(url)
            if not data:
                break

            items = data.get("data") or data.get("radares") or data.get("items") or []
            if not items and isinstance(data, list):
                items = data

            if not items:
                break

            batch: List[Dict[str, Any]] = []
            for item in items:
                if isinstance(item, dict):
                    normalized = self.normalize_record(item, uf_fallback=uf_upper)
                    batch.append(normalized)

            all_records.extend(batch)

            # Fire callback during idle time between pages to optimize concurrent geocoding
            if on_batch_extracted:
                on_batch_extracted(batch)

            next_cursor = data.get("next_cursor") or data.get("proximo_cursor") or data.get("cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = str(next_cursor)
            time.sleep(0.05)  # small pause to avoid bursting the server

        return all_records

    def extract_all_ufs(
        self,
        ufs: List[str],
        on_batch_extracted: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extracts all UFs, returning (records_with_coords, records_needing_geocode)."""
        with_coords: List[Dict[str, Any]] = []
        needs_geocode: List[Dict[str, Any]] = []

        for uf in ufs:
            logger.info("Extracting OpenClaw records for UF %s...", uf)
            uf_records = self.extract_uf(uf, on_batch_extracted=on_batch_extracted)
            for rec in uf_records:
                if rec["has_coordinates"]:
                    with_coords.append(rec)
                elif rec["address_text"]:
                    needs_geocode.append(rec)

        logger.info(
            "OpenClaw extraction complete: %d with coordinates, %d pending geocoding.",
            len(with_coords),
            len(needs_geocode),
        )
        return with_coords, needs_geocode
