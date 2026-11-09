"""Extractor for Polícia Rodoviária Federal (PRF) official radar feed."""

import json
import logging
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger(__name__)


class PrfExtractor:
    """Extracts and normalizes PRF federal highway speed radars."""

    def __init__(self, prf_url: str, user_agent: str) -> None:
        self.prf_url = prf_url
        self.user_agent = user_agent

    def _fetch_json(self, url: str, timeout: int = 45) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content)

    def extract_radares(self, custom_data: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extracts PRF radars."""
        raw_items = custom_data if custom_data is not None else self._fetch_json(self.prf_url)
        if not isinstance(raw_items, list):
            raw_items = raw_items.get("data", []) if isinstance(raw_items, dict) else []

        normalized: List[Dict[str, Any]] = []
        for row in raw_items:
            lat_val = row.get("LATITUDE")
            lon_val = row.get("LONGITUDE")
            if lat_val is None or lon_val is None:
                continue

            try:
                lat = float(str(lat_val).replace(",", ".").strip())
                lon = float(str(lon_val).replace(",", ".").strip())
            except (ValueError, TypeError):
                continue
            if lat == 0.0 or lon == 0.0:
                continue

            identificador = str(row.get("IDENTIFICADOR") or "").strip()
            conc = str(row.get("CONCESSIONÁRIA") or "").strip()
            br = str(row.get("BR") or "").strip()
            rodovia = br if (not br or br.startswith("BR-")) else f"BR-{br}"
            uf = str(row.get("UF") or "").strip().upper()
            km_raw = str(row.get("LOCAL") or "").replace(",", ".").strip()
            municipio = str(row.get("MUNICÍPIO") or "").strip()
            sentido = str(row.get("SENTIDO") or "").strip()
            tipo_equip = str(row.get("TIPO EQUIPAMENTO") or "CONTROLADOR").strip()

            vel_leve_raw = "".join(filter(str.isdigit, str(row.get("VELOCIDADE LEVE") or "")))
            vel_pesado_raw = "".join(filter(str.isdigit, str(row.get("VELOCIDADE PESADO") or "")))
            vel_leve = int(vel_leve_raw) if vel_leve_raw else None
            vel_pesado = int(vel_pesado_raw) if vel_pesado_raw else None
            speed_limit = vel_leve or vel_pesado

            lower_tipo = tipo_equip.lower()
            if "redutor" in lower_tipo or "lombada" in lower_tipo:
                poi_type = "ELECTRONIC_SPEED_BUMP"
            elif "portatil" in lower_tipo or "movel" in lower_tipo or "móvel" in lower_tipo:
                poi_type = "MOBILE_RADAR"
            else:
                poi_type = "FIXED_RADAR"

            normalized.append({
                "source": "PRF_RADARES_FIXOS",
                "identificador": identificador,
                "poi_type": poi_type,
                "latitude": lat,
                "longitude": lon,
                "speed_limit": speed_limit,
                "concessionaria": conc or "Polícia Rodoviária Federal",
                "tipo_equipamento": tipo_equip,
                "rodovia": rodovia,
                "uf": uf,
                "km": km_raw,
                "municipio": municipio,
                "sentido": sentido,
                "situacao": str(row.get("ESTADO") or "ATIVO").strip(),
                "address_text": f"{rodovia} km {km_raw}, {municipio} - {uf}" if rodovia else f"{municipio} - {uf}",
            })
        return normalized
