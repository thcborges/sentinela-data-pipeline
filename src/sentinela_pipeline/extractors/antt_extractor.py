"""Extractor for ANTT open data (Toll booths and highway speed radars)."""

import json
import logging
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger(__name__)


class AnttExtractor:
    """Extracts and normalizes ANTT Toll Booth and Speed Radar datasets."""

    def __init__(self, pedagios_url: str, radares_url: str, user_agent: str) -> None:
        self.pedagios_url = pedagios_url
        self.radares_url = radares_url
        self.user_agent = user_agent

    def _fetch_json(self, url: str, timeout: int = 45) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content)

    def extract_pedagios(self, custom_data: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extracts toll booths from ANTT."""
        raw_items = custom_data if custom_data is not None else self._fetch_json(self.pedagios_url)
        if not isinstance(raw_items, list):
            raw_items = raw_items.get("data", []) if isinstance(raw_items, dict) else []

        normalized: List[Dict[str, Any]] = []
        for row in raw_items:
            lat_raw = str(row.get("latitude") or "").replace(",", ".").strip()
            lon_raw = str(row.get("longitude") or "").replace(",", ".").strip()
            try:
                lat = float(lat_raw)
                lon = float(lon_raw)
            except (ValueError, TypeError):
                continue
            if lat == 0.0 or lon == 0.0:
                continue

            concessionaria = str(row.get("concessionaria") or "").strip()
            praca = str(row.get("praca_de_pedagio") or row.get("praca") or "Praça de Pedágio").strip()
            rodovia = str(row.get("rodovia") or "").strip()
            uf = str(row.get("uf") or "").strip().upper()
            km = str(row.get("km_m") or "").strip()
            municipio = str(row.get("municipio") or "").strip()
            sentido = str(row.get("sentido") or "Bidirecional").strip()
            situacao = str(row.get("situacao") or "Ativo").strip()

            tarifa_auto_raw = str(row.get("tarifa_automovel") or "").replace(",", ".").strip()
            tarifa_com_raw = str(row.get("tarifa_comercial") or "").replace(",", ".").strip()
            try:
                tarifa_auto = float(tarifa_auto_raw) if tarifa_auto_raw else None
            except ValueError:
                tarifa_auto = None
            try:
                tarifa_com = float(tarifa_com_raw) if tarifa_com_raw else None
            except ValueError:
                tarifa_com = None

            is_free_flow = (
                "free flow" in praca.lower()
                or "pórtico" in praca.lower()
                or "portico" in praca.lower()
            )

            normalized.append({
                "source": "ANTT_PEDAGIOS",
                "poi_type": "FREE_FLOW_TOLL" if is_free_flow else "TOLL_BOOTH",
                "latitude": lat,
                "longitude": lon,
                "concessionaria": concessionaria,
                "praca_nome": praca,
                "rodovia": rodovia,
                "uf": uf,
                "km": km,
                "municipio": municipio,
                "sentido": sentido,
                "situacao": situacao,
                "tarifa_automovel": tarifa_auto,
                "tarifa_comercial": tarifa_com,
                "address_text": f"{rodovia} km {km}, {municipio} - {uf}" if rodovia else praca,
            })
        return normalized

    def extract_radares(self, custom_data: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extracts federal highway concession speed radars from ANTT."""
        raw_items = custom_data if custom_data is not None else self._fetch_json(self.radares_url)
        if not isinstance(raw_items, list):
            raw_items = raw_items.get("data", []) if isinstance(raw_items, dict) else []

        normalized: List[Dict[str, Any]] = []
        for row in raw_items:
            lat_raw = str(row.get("latitude") or "").replace(",", ".").strip()
            lon_raw = str(row.get("longitude") or "").replace(",", ".").strip()
            try:
                lat = float(lat_raw)
                lon = float(lon_raw)
            except (ValueError, TypeError):
                continue
            if lat == 0.0 or lon == 0.0:
                continue

            concessionaria = str(row.get("concessionaria") or "").strip()
            tipo_radar = str(row.get("tipo_de_radar") or "Controlador").strip()
            rodovia = str(row.get("rodovia") or "").strip()
            uf = str(row.get("uf") or "").strip().upper()
            km = str(row.get("km_m") or "").strip()
            municipio = str(row.get("municipio") or "").strip()
            sentido = str(row.get("sentido") or "").strip()

            vel_leve_raw = "".join(filter(str.isdigit, str(row.get("velocidade_leve") or "")))
            vel_pesado_raw = "".join(filter(str.isdigit, str(row.get("velocidade_pesado") or "")))
            vel_leve = int(vel_leve_raw) if vel_leve_raw else None
            vel_pesado = int(vel_pesado_raw) if vel_pesado_raw else None
            speed_limit = vel_leve or vel_pesado

            lower_tipo = tipo_radar.lower()
            if "semaforo" in lower_tipo or "semáforo" in lower_tipo or "vermelho" in lower_tipo:
                poi_type = "TRAFFIC_LIGHT_RADAR" if speed_limit else "RED_LIGHT_CAMERA"
            elif "redutor" in lower_tipo or "lombada" in lower_tipo:
                poi_type = "ELECTRONIC_SPEED_BUMP"
            else:
                poi_type = "FIXED_RADAR"

            normalized.append({
                "source": "ANTT_RADARES",
                "poi_type": poi_type,
                "latitude": lat,
                "longitude": lon,
                "speed_limit": speed_limit,
                "concessionaria": concessionaria,
                "tipo_radar": tipo_radar,
                "rodovia": rodovia,
                "uf": uf,
                "km": km,
                "municipio": municipio,
                "sentido": sentido,
                "situacao": str(row.get("situacao") or "Ativo").strip(),
                "address_text": f"{rodovia} km {km}, {municipio} - {uf}" if rodovia else f"{municipio} - {uf}",
            })
        return normalized
