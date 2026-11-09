"""Unit tests for SpatialDeduplicator and semantic type compatibility."""

import unittest
from sentinela_pipeline.consolidation.deduplicator import (
    SpatialDeduplicator,
    are_types_compatible,
    directions_match,
    haversine_distance_meters,
)


class TestDeduplicator(unittest.TestCase):
    def test_haversine_distance(self):
        # Coordinates in São Paulo separated by ~111 meters
        lat1, lon1 = -23.55000, -46.63000
        lat2, lon2 = -23.55100, -46.63000
        dist = haversine_distance_meters(lat1, lon1, lat2, lon2)
        self.assertAlmostEqual(dist, 111.2, delta=2.0)

    def test_are_types_compatible(self):
        # Same types are compatible
        self.assertTrue(are_types_compatible("FIXED_RADAR", "FIXED_RADAR"))
        self.assertTrue(are_types_compatible("PHYSICAL_SPEED_BUMP", "PHYSICAL_SPEED_BUMP"))

        # Radars are compatible with each other
        self.assertTrue(are_types_compatible("FIXED_RADAR", "TRAFFIC_LIGHT_RADAR"))
        self.assertTrue(are_types_compatible("FIXED_RADAR", "MOBILE_RADAR"))

        # Speed bumps are compatible with each other
        self.assertTrue(are_types_compatible("PHYSICAL_SPEED_BUMP", "ELECTRONIC_SPEED_BUMP"))

        # Incompatible types MUST return False
        self.assertFalse(are_types_compatible("FIXED_RADAR", "PHYSICAL_SPEED_BUMP"))
        self.assertFalse(are_types_compatible("FIXED_RADAR", "TOLL_BOOTH"))
        self.assertFalse(are_types_compatible("TOLL_BOOTH", "HIGHWAY_PATROL"))

    def test_directions_match(self):
        self.assertTrue(directions_match(90, 95))      # 5 deg diff
        self.assertTrue(directions_match(355, 5))      # 10 deg diff across 0/360 wrap
        self.assertTrue(directions_match(None, 90))    # Unknown direction matches
        self.assertFalse(directions_match(0, 180))     # Opposite directions (dual carriageway)

    def test_deduplicate_merges_close_radars_with_same_direction(self):
        dedup = SpatialDeduplicator(cluster_radius_meters=35.0)
        points = [
            {
                "id": 1,
                "poi_type": "FIXED_RADAR",
                "latitude": -23.55000,
                "longitude": -46.63000,
                "speed_limit": None,
                "road_name": "Av. 23 de Maio",
                "direction": 90,
            },
            {
                # Duplicate 15m away with speed limit and operator
                "id": 2,
                "poi_type": "FIXED_RADAR",
                "latitude": -23.55010,
                "longitude": -46.63005,
                "speed_limit": 60,
                "road_name": "Av. 23 de Maio - Sentido Bairro",
                "operator": "CET-SP",
                "direction": 90,
            },
        ]

        result = dedup.deduplicate(points)
        self.assertEqual(len(result), 1)
        merged = result[0]
        self.assertEqual(merged["speed_limit"], 60)
        self.assertEqual(merged["operator"], "CET-SP")
        self.assertEqual(merged["road_name"], "Av. 23 de Maio - Sentido Bairro")

    def test_deduplicate_preserves_opposite_directions_on_dual_carriageway(self):
        dedup = SpatialDeduplicator(cluster_radius_meters=35.0)
        points = [
            {
                "id": 1,
                "poi_type": "FIXED_RADAR",
                "latitude": -23.55000,
                "longitude": -46.63000,
                "speed_limit": 80,
                "direction": 0,  # North
            },
            {
                "id": 2,
                "poi_type": "FIXED_RADAR",
                "latitude": -23.55010,
                "longitude": -46.63005,
                "speed_limit": 80,
                "direction": 180,  # South (opposite side of highway)
            },
        ]
        result = dedup.deduplicate(points)
        self.assertEqual(len(result), 2)

    def test_deduplicate_never_drops_incompatible_types_near_radar(self):
        dedup = SpatialDeduplicator(cluster_radius_meters=35.0)
        points = [
            {
                "id": 1,
                "poi_type": "FIXED_RADAR",
                "latitude": -23.55000,
                "longitude": -46.63000,
                "speed_limit": 60,
            },
            {
                # Speed bump 10m away
                "id": 2,
                "poi_type": "PHYSICAL_SPEED_BUMP",
                "latitude": -23.55008,
                "longitude": -46.63002,
            },
            {
                # Toll booth 15m away
                "id": 3,
                "poi_type": "TOLL_BOOTH",
                "latitude": -23.55010,
                "longitude": -46.63005,
            },
        ]
        result = dedup.deduplicate(points)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
