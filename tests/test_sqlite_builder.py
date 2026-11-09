"""Unit tests for SQLiteRadarBuilder and R*Tree spatial indexing."""

import os
import sqlite3
import tempfile
import unittest
from sentinela_pipeline.consolidation.sqlite_builder import SQLiteRadarBuilder


class TestSQLiteBuilder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_sentinela.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_database_with_rtree_and_metadata(self):
        builder = SQLiteRadarBuilder(self.db_path)
        sample_pois = [
            {
                "poi_type": "FIXED_RADAR",
                "latitude": -23.550520,
                "longitude": -46.633308,
                "speed_limit": 60,
                "direction": 180,
                "road_name": "Av. 23 de Maio",
                "city": "São Paulo",
                "state": "SP",
            },
            {
                "poi_type": "PHYSICAL_SPEED_BUMP",
                "latitude": -22.906847,
                "longitude": -43.172896,
                "road_name": "Aterro do Flamengo",
                "city": "Rio de Janeiro",
                "state": "RJ",
            },
            {
                "poi_type": "TOLL_BOOTH",
                "latitude": -19.916681,
                "longitude": -43.934493,
                "tarifa_automovel": 5.80,
                "operator": "VIA BRASIL",
                "city": "Belo Horizonte",
                "state": "MG",
            },
        ]

        saved_count = builder.build_database(
            sample_pois,
            source_summaries={"antt": 1, "osm": 2},
        )
        self.assertEqual(saved_count, 3)
        self.assertTrue(os.path.exists(self.db_path))

        # Query database directly using sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        self.assertIn("pois", tables)
        self.assertIn("pois_index", tables)
        self.assertIn("db_metadata", tables)

        # Check POIs count
        cursor.execute("SELECT COUNT(*) FROM pois;")
        self.assertEqual(cursor.fetchone()[0], 3)

        # Check metadata
        cursor.execute("SELECT value FROM db_metadata WHERE key='total_count';")
        self.assertEqual(cursor.fetchone()[0], "3")
        cursor.execute("SELECT value FROM db_metadata WHERE key='source_count_antt';")
        self.assertEqual(cursor.fetchone()[0], "1")

        # Check spatial bounding box query using R*Tree
        # Bounding box around São Paulo: lat [-23.6, -23.5], lon [-46.7, -46.6]
        cursor.execute("""
            SELECT p.id, p.road_name, p.speed_limit
            FROM pois p
            JOIN pois_index i ON p.id = i.id
            WHERE i.minX >= -46.7 AND i.maxX <= -46.6
              AND i.minY >= -23.6 AND i.maxY <= -23.5;
        """)
        sp_results = cursor.fetchall()
        self.assertEqual(len(sp_results), 1)
        self.assertEqual(sp_results[0][1], "Av. 23 de Maio")
        self.assertEqual(sp_results[0][2], 60)

        conn.close()


if __name__ == "__main__":
    unittest.main()
