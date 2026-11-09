"""Exports consolidated datasets to JSON, CSV and calculates SHA-256 checksums."""

import csv
import hashlib
import json
import os
from typing import Any, Dict, List


class DatasetExporter:
    """Exports consolidated radar points to multiple distribution formats."""

    @staticmethod
    def export_to_json(points: List[Dict[str, Any]], output_path: str, pretty: bool = True) -> str:
        """Exports points to the JSON structure expected by the Sentinela app sync parser."""
        elements = []
        for idx, p in enumerate(points, start=1):
            poi_type = str(p.get("poi_type") or "FIXED_RADAR")
            tags: Dict[str, str] = {}

            if p.get("speed_limit"):
                tags["maxspeed"] = str(p["speed_limit"])
            if p.get("direction") is not None:
                tags["direction"] = str(p["direction"])

            road = p.get("road_name") or p.get("rodovia") or p.get("rodovia_via") or ""
            if road:
                tags["name"] = road

            operator = p.get("operator") or p.get("concessionaria") or ""
            if operator:
                tags["operator"] = operator

            city = p.get("city") or p.get("municipio") or ""
            if city:
                tags["city"] = city

            state = p.get("state") or p.get("uf") or ""
            if state:
                tags["state"] = state

            # Map to OSM tags recognized by PoiSyncParser
            if poi_type == "TOLL_BOOTH":
                tags["barrier"] = "toll_booth"
            elif poi_type == "FREE_FLOW_TOLL":
                tags["highway"] = "toll_gantry"
            elif poi_type == "PHYSICAL_SPEED_BUMP":
                tags["traffic_calming"] = "bump"
            elif poi_type == "ELECTRONIC_SPEED_BUMP":
                tags["traffic_calming"] = "cushion"
            elif poi_type == "HIGHWAY_PATROL":
                tags["amenity"] = "police"
            elif poi_type == "TRAFFIC_LIGHT_RADAR":
                tags["enforcement"] = "red_light"
                tags["camera:traffic_signals"] = "yes"
            elif poi_type == "RED_LIGHT_CAMERA":
                tags["enforcement"] = "red_light"
            else:
                tags["highway"] = "speed_camera"

            elements.append({
                "type": "node",
                "id": idx,
                "lat": float(p["latitude"]),
                "lon": float(p["longitude"]),
                "tags": tags,
            })

        payload = {"elements": elements}
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            else:
                json.dump(payload, f, ensure_ascii=False)
        return output_path

    @staticmethod
    def export_to_csv(points: List[Dict[str, Any]], output_path: str) -> str:
        """Exports points to standard CSV table."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fieldnames = [
            "id", "poi_type", "latitude", "longitude", "speed_limit",
            "direction", "road_name", "operator", "city", "state",
            "toll_fee_car", "toll_fee_truck", "source"
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for idx, p in enumerate(points, start=1):
                writer.writerow({
                    "id": idx,
                    "poi_type": p.get("poi_type") or "FIXED_RADAR",
                    "latitude": p.get("latitude"),
                    "longitude": p.get("longitude"),
                    "speed_limit": p.get("speed_limit") or "",
                    "direction": p.get("direction") or "",
                    "road_name": p.get("road_name") or p.get("rodovia") or p.get("rodovia_via") or "",
                    "operator": p.get("operator") or p.get("concessionaria") or "",
                    "city": p.get("city") or p.get("municipio") or "",
                    "state": p.get("state") or p.get("uf") or "",
                    "toll_fee_car": p.get("tarifa_automovel") or p.get("toll_fee_car") or "",
                    "toll_fee_truck": p.get("tarifa_comercial") or p.get("toll_fee_truck") or "",
                    "source": p.get("source") or "SENTINELA_DATA_PIPELINE",
                })
        return output_path

    @staticmethod
    def generate_sha256_sums(files: List[str], output_path: str) -> str:
        """Generates SHA256SUMS.txt for list of target files."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        lines = []
        for file_path in files:
            if not os.path.exists(file_path):
                continue
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            filename = os.path.basename(file_path)
            lines.append(f"{sha256.hexdigest()}  {filename}\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return output_path
