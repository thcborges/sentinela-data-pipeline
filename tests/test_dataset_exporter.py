"""Unit tests for DatasetExporter (JSON, CSV and SHA-256 sums)."""

import json
import os
import tempfile
import unittest
from sentinela_pipeline.consolidation.dataset_exporter import DatasetExporter


class TestDatasetExporter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.points = [
            {
                "poi_type": "FIXED_RADAR",
                "latitude": -23.55052,
                "longitude": -46.63330,
                "speed_limit": 60,
                "direction": 180,
                "road_name": "Av. 23 de Maio",
                "city": "São Paulo",
                "state": "SP",
            },
            {
                "poi_type": "TOLL_BOOTH",
                "latitude": -22.90684,
                "longitude": -43.17289,
                "road_name": "Ponte Rio-Niterói",
                "operator": "ECOPONTE",
                "tarifa_automovel": 6.20,
            },
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_to_json(self):
        json_path = os.path.join(self.temp_dir.name, "sentinela_pois_brasil.json")
        DatasetExporter.export_to_json(self.points, json_path)

        self.assertTrue(os.path.exists(json_path))
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("elements", data)
        self.assertEqual(len(data["elements"]), 2)
        elem1 = data["elements"][0]
        self.assertEqual(elem1["lat"], -23.55052)
        self.assertEqual(elem1["tags"]["highway"], "speed_camera")
        self.assertEqual(elem1["tags"]["maxspeed"], "60")

        elem2 = data["elements"][1]
        self.assertEqual(elem2["tags"]["barrier"], "toll_booth")
        self.assertEqual(elem2["tags"]["operator"], "ECOPONTE")

    def test_export_to_csv(self):
        csv_path = os.path.join(self.temp_dir.name, "sentinela_pois_brasil.csv")
        DatasetExporter.export_to_csv(self.points, csv_path)

        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 3)  # header + 2 rows
        self.assertIn("poi_type,latitude,longitude", lines[0])
        self.assertIn("FIXED_RADAR,-23.55052,-46.6333", lines[1])

    def test_generate_sha256_sums(self):
        file1 = os.path.join(self.temp_dir.name, "file1.txt")
        file2 = os.path.join(self.temp_dir.name, "file2.txt")
        sha_path = os.path.join(self.temp_dir.name, "SHA256SUMS.txt")

        with open(file1, "w") as f:
            f.write("hello world")
        with open(file2, "w") as f:
            f.write("sentinela radar")

        DatasetExporter.generate_sha256_sums([file1, file2], sha_path)
        self.assertTrue(os.path.exists(sha_path))

        with open(sha_path, "r") as f:
            content = f.read()

        self.assertIn("file1.txt", content)
        self.assertIn("file2.txt", content)
        # Verify sha256 for 'hello world': b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
        self.assertIn("b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9", content)

        # Test ignoring missing files
        missing_sha = os.path.join(self.temp_dir.name, "MISSING_SHA.txt")
        DatasetExporter.generate_sha256_sums(["/non/existent/file.txt"], missing_sha)
        self.assertTrue(os.path.exists(missing_sha))


if __name__ == "__main__":
    unittest.main()
