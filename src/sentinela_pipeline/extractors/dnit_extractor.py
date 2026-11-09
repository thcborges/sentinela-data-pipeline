"""Extractor for DNIT PNCV (Plano Nacional de Controle de Velocidade)."""

import json
import logging
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger(__name__)


class DnitExtractor:
    """Extracts and normalizes DNIT federal highway speed cameras and reducers."""

    def __init__(self, endpoint_url: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        self.endpoint_url = endpoint_url
        self.user_agent = user_agent or "SentinelaRadarDataPipeline/1.0"

    def extract_pncv(self, raw_records: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extracts and standardizes DNIT PNCV records."""
        items: List[Dict[str, Any]] = []
        if raw_records is not None:
            items = raw_records
        elif self.endpoint_url:
            req = urllib.request.Request(self.endpoint_url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data if isinstance(data, list) else data.get("records", [])

        normalized: List[Dict[str, Any]] = []
        for row in items:
            lat_val = row.get("latitude") or row.get("LATITUDE")
            lon_val = row.get("longitude") or row.get("LONGITUDE")
            if lat_val is None or lon_val is None:
                continue

            try:
                lat = float(str(lat_val).replace(",", ".").strip())
                lon = float(str(lon_val).replace(",", ".").strip())
            except (ValueError, TypeError):
                continue
            if lat == 0.0 or lon == 0.0:
                continue

            codigo = str(row.get("codigo") or row.get("Código Identificação") or "").strip()
            uf = str(row.get("uf") or row.get("UF") or "").strip().upper()
            br_raw = str(row.get("rodovia") or row.get("Rodovia") or "").strip()
            rodovia = br_raw if (not br_raw or br_raw.startswith("BR-")) else f"BR-{br_raw}"
            km_raw = str(row.get("km") or row.get("Km") or "").replace(",", ".").strip()
            municipio = str(row.get("municipio") or row.get("Município") or "").strip()
            tipo = str(row.get("tipo") or row.get("Tipo") or "RAD").strip()
            marca = str(row.get("marca_modelo") or row.get("Marca / Modelo") or "").strip()

            vel_raw = "".join(filter(str.isdigit, str(row.get("velocidade") or row.get("Velocidade") or "")))
            speed_limit = int(vel_raw) if vel_raw else None

            upper_tipo = tipo.upper()
            if "REV" in upper_tipo or "LOMBADA" in upper_tipo or "REDUTOR" in upper_tipo:
                poi_type = "ELECTRONIC_SPEED_BUMP"
            elif "SEMAFORO" in upper_tipo or "SEMÁFORO" in upper_tipo:
                poi_type = "TRAFFIC_LIGHT_RADAR"
            else:
                poi_type = "FIXED_RADAR"

            normalized.append({
                "source": "DNIT_PNCV",
                "codigo": codigo,
                "poi_type": poi_type,
                "latitude": lat,
                "longitude": lon,
                "speed_limit": speed_limit,
                "rodovia": rodovia,
                "uf": uf,
                "km": km_raw,
                "municipio": municipio,
                "tipo_equipamento": tipo,
                "marca_modelo": marca,
                "situacao": str(row.get("situacao") or "Ativo").strip(),
                "address_text": f"{rodovia} km {km_raw}, {municipio} - {uf}" if rodovia else f"{municipio} - {uf}",
            })
        return normalized
