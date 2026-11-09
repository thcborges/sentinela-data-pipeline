"""Spatial deduplication engine with semantic type compatibility."""

import math
from typing import Any, Dict, List, Optional


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in meters."""
    earth_radius_m = 6371000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return earth_radius_m * c


def are_types_compatible(type_a: str, type_b: str) -> bool:
    """Checks whether two POI types are semantically compatible to be merged as duplicates."""
    if type_a == type_b:
        return True

    radars = {"FIXED_RADAR", "TRAFFIC_LIGHT_RADAR", "MOBILE_RADAR"}
    if type_a in radars and type_b in radars:
        return True

    bumps = {"PHYSICAL_SPEED_BUMP", "ELECTRONIC_SPEED_BUMP"}
    if type_a in bumps and type_b in bumps:
        return True

    tolls = {"TOLL_BOOTH", "FREE_FLOW_TOLL"}
    if type_a in tolls and type_b in tolls:
        return True

    lights = {"TRAFFIC_LIGHT_RADAR", "RED_LIGHT_CAMERA"}
    if type_a in lights and type_b in lights:
        return True

    return False


def directions_match(dir_a: Optional[int], dir_b: Optional[int], tolerance_degrees: float = 45.0) -> bool:
    """Checks whether two headings are aligned within tolerance."""
    if dir_a is None or dir_b is None:
        return True
    diff = abs(dir_a - dir_b) % 360
    angle_diff = 360.0 - diff if diff > 180 else diff
    return angle_diff <= tolerance_degrees


class SpatialDeduplicator:
    """Performs spatial clustering and merges duplicate POIs within threshold."""

    def __init__(self, cluster_radius_meters: float = 35.0) -> None:
        self.cluster_radius = cluster_radius_meters

    def _merge_attributes(self, base: Dict[str, Any], duplicate: Dict[str, Any]) -> Dict[str, Any]:
        """Merges two records, retaining the richest information."""
        merged = dict(base)
        # Prioritize non-null speed limit
        if merged.get("speed_limit") is None and duplicate.get("speed_limit") is not None:
            merged["speed_limit"] = duplicate["speed_limit"]

        # Prioritize longer / more descriptive road name
        curr_road = str(merged.get("road_name") or merged.get("rodovia_via") or "")
        dup_road = str(duplicate.get("road_name") or duplicate.get("rodovia_via") or "")
        if len(dup_road) > len(curr_road):
            merged["road_name"] = dup_road

        # Prioritize operator / concessionaria
        curr_op = str(merged.get("operator") or merged.get("concessionaria") or "")
        dup_op = str(duplicate.get("operator") or duplicate.get("concessionaria") or "")
        if not curr_op and dup_op:
            merged["operator"] = dup_op

        # Preserve direction
        if merged.get("direction") is None and duplicate.get("direction") is not None:
            merged["direction"] = duplicate["direction"]

        return merged

    def deduplicate(self, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates a list of POI dictionaries by spatial proximity and type compatibility."""
        valid_points = [
            p for p in points
            if p.get("latitude") is not None and p.get("longitude") is not None
        ]

        # Spatial bucketing by ~0.005 degrees (~500m) for fast localized candidate searching
        grid: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        grid_step = 0.005

        def get_grid_cell(lat: float, lon: float) -> Tuple[int, int]:
            return int(lat / grid_step), int(lon / grid_step)

        consolidated: List[Dict[str, Any]] = []

        for candidate in valid_points:
            c_lat = float(candidate["latitude"])
            c_lon = float(candidate["longitude"])
            c_type = str(candidate.get("poi_type") or "FIXED_RADAR")
            c_dir = candidate.get("direction")

            cell_x, cell_y = get_grid_cell(c_lat, c_lon)
            found_existing = False

            # Check candidate against current cell and 8 adjacent neighbors
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbor_cell = (cell_x + dx, cell_y + dy)
                    if neighbor_cell not in grid:
                        continue

                    for existing in grid[neighbor_cell]:
                        e_lat = float(existing["latitude"])
                        e_lon = float(existing["longitude"])
                        e_type = str(existing.get("poi_type") or "FIXED_RADAR")
                        e_dir = existing.get("direction")

                        if not are_types_compatible(c_type, e_type):
                            continue

                        if not directions_match(c_dir, e_dir):
                            continue

                        dist = haversine_distance_meters(c_lat, c_lon, e_lat, e_lon)
                        if dist <= self.cluster_radius:
                            # Merge into existing
                            merged = self._merge_attributes(existing, candidate)
                            existing.update(merged)
                            found_existing = True
                            break

                    if found_existing:
                        break
                if found_existing:
                    break

            if not found_existing:
                # Add as a distinct new POI
                grid.setdefault((cell_x, cell_y), []).append(candidate)
                consolidated.append(candidate)

        return consolidated
