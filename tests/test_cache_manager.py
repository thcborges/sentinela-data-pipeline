"""Unit tests for AddressCacheManager, address normalization and hashing."""

import unittest
from unittest.mock import MagicMock
from sentinela_pipeline.geocoding.cache_manager import (
    AddressCacheManager,
    compute_address_hash,
    normalize_address,
)


class TestCacheManager(unittest.TestCase):
    def test_normalize_address(self):
        raw = "  Av. das Américas, nº 500 - Bloco 2 / Barra da Tijuca, Rio de Janeiro - RJ!  "
        normalized = normalize_address(raw)
        self.assertEqual(
            normalized,
            "AV DAS AMERICAS NO 500 BLOCO 2 BARRA DA TIJUCA RIO DE JANEIRO RJ",
        )

    def test_compute_address_hash_deterministic(self):
        addr1 = "Rodovia BR-116, km 205 - Arujá/SP"
        addr2 = "rodovia br-116, km 205 - aruja/sp"
        hash1 = compute_address_hash(addr1)
        hash2 = compute_address_hash(addr2)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)

    def test_cache_get_and_set(self):
        cache = AddressCacheManager()
        self.assertEqual(cache.size, 0)
        self.assertIsNone(cache.get("Av. Paulista, 1000"))

        cache.set("Av. Paulista, 1000", -23.5614, -46.6558, source="TEST")
        self.assertEqual(cache.size, 1)

        hit = cache.get("av. paulista, 1000")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["latitude"], -23.5614)
        self.assertEqual(hit["longitude"], -46.6558)
        self.assertEqual(hit["geocoding_source"], "TEST")

    def test_load_from_records(self):
        cache = AddressCacheManager()
        records = [
            {
                "raw_address": "Rua das Flores, 10",
                "latitude": -22.9,
                "longitude": -43.1,
            },
            {
                "address_hash": "customhash123",
                "raw_address": "Av. Brasil, 50",
                "latitude": -22.8,
                "longitude": -43.2,
            },
        ]
        count = cache.load_from_records(records)
        self.assertEqual(count, 2)
        self.assertEqual(cache.size, 2)
        self.assertIsNotNone(cache.get("Rua das Flores, 10"))

    def test_flush_to_bigquery_success(self):
        mock_bq = MagicMock()
        mock_bq.insert_rows_json.return_value = []  # no errors
        cache = AddressCacheManager(bq_client=mock_bq, table_id="my_project.dataset.table")
        cache.set("Rua A, 1", -20.0, -40.0)
        cache.set("Rua B, 2", -21.0, -41.0)

        flushed = cache.flush_to_bigquery()
        self.assertEqual(flushed, 2)
        mock_bq.insert_rows_json.assert_called_once()

    def test_flush_to_bigquery_with_errors(self):
        mock_bq = MagicMock()
        mock_bq.insert_rows_json.return_value = [{"index": 0, "errors": ["invalid"]}]
        cache = AddressCacheManager(bq_client=mock_bq, table_id="my_project.dataset.table")
        cache.set("Rua C, 3", -22.0, -42.0)

        flushed = cache.flush_to_bigquery()
        self.assertEqual(flushed, 0)

    def test_flush_to_bigquery_exception_and_empty(self):
        cache = AddressCacheManager()
        # Empty cache
        self.assertEqual(cache.flush_to_bigquery(), 0)

        # Exception
        mock_bq = MagicMock()
        mock_bq.insert_rows_json.side_effect = RuntimeError("BigQuery down")
        cache_err = AddressCacheManager(bq_client=mock_bq, table_id="my_table")
        cache_err.set("Rua D", -20.0, -40.0)
        self.assertEqual(cache_err.flush_to_bigquery(), 0)


if __name__ == "__main__":
    unittest.main()
