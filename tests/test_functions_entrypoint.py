"""Unit tests for Cloud Run Function entrypoints."""

import tempfile
import unittest
from unittest.mock import MagicMock
from sentinela_pipeline.functions.extractor_entrypoint import extract_and_stage_pipeline
from sentinela_pipeline.functions.geocoder_entrypoint import (
    consolidate_and_export_pipeline,
    process_geocoding_message,
)
from sentinela_pipeline.geocoding import AddressCacheManager, GeocoderService


class TestFunctionEntrypoints(unittest.TestCase):
    def test_extract_and_stage_pipeline(self):
        sample_records = {
            "antt_pedagios": [
                {
                    "praca": "Pedagio 1",
                    "latitude": "-22.5",
                    "longitude": "-43.5",
                }
            ],
            "antt_radares": [
                {
                    "tipo_de_radar": "Controlador",
                    "latitude": "-22.6",
                    "longitude": "-43.6",
                    "velocidade_leve": "80",
                }
            ],
            "prf_radares": [
                {
                    "IDENTIFICADOR": "PRF-1",
                    "LATITUDE": -22.7,
                    "LONGITUDE": -43.7,
                    "VELOCIDADE LEVE": "90",
                }
            ],
            "dnit_pncv": [
                {
                    "codigo": "DNIT-1",
                    "latitude": -22.8,
                    "longitude": -43.8,
                    "velocidade": "60",
                }
            ],
            "osm_comunitario": [
                {
                    "type": "node",
                    "id": 999,
                    "lat": -22.9,
                    "lon": -43.9,
                    "tags": {"highway": "speed_camera", "maxspeed": "70"},
                }
            ],
            "openclaw_raw": [
                {
                    "id": "OPEN-1",
                    "latitude": -23.0,
                    "longitude": -44.0,
                },
                {
                    "id": "OPEN-2",
                    "latitude": None,
                    "longitude": None,
                    "via": "Av. Brasil",
                    "municipio": "Rio de Janeiro",
                    "uf": "RJ",
                },
            ],
        }

        mock_pubsub = MagicMock()
        summary = extract_and_stage_pipeline(
            sample_records=sample_records,
            pubsub_publisher=mock_pubsub,
        )

        self.assertEqual(summary["status"], "SUCCESS")
        counts = summary["counts"]
        self.assertEqual(counts["antt_pedagios"], 1)
        self.assertEqual(counts["antt_radares"], 1)
        self.assertEqual(counts["prf_radares"], 1)
        self.assertEqual(counts["dnit_pncv"], 1)
        self.assertEqual(counts["osm_comunitario"], 1)
        self.assertEqual(counts["openclaw_with_coordinates"], 1)
        self.assertEqual(counts["openclaw_needs_geocoding"], 1)
        self.assertEqual(counts["geocoding_tasks_published"], 1)
        mock_pubsub.publish.assert_called_once()

    def test_process_geocoding_message(self):
        cache = AddressCacheManager()
        mock_nom = MagicMock()
        mock_nom.geocode.return_value = (-22.9068, -43.1729, "Aterro")
        geocoder = GeocoderService(cache_manager=cache, nominatim_client=mock_nom)

        msg = {
            "id": "REQ-101",
            "address_text": "Aterro do Flamengo, Rio de Janeiro",
            "has_coordinates": False,
        }
        result = process_geocoding_message(msg, geocoder)
        self.assertIsNotNone(result)
        self.assertTrue(result["has_coordinates"])
        self.assertEqual(result["latitude"], -22.9068)
        self.assertEqual(result["geocoding_source"], "NOMINATIM_OSM")

    def test_consolidate_and_export_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_pois = [
                {
                    "poi_type": "FIXED_RADAR",
                    "latitude": -23.5505,
                    "longitude": -46.6333,
                    "speed_limit": 60,
                    "road_name": "Av. 23 de Maio",
                },
                {
                    "poi_type": "TOLL_BOOTH",
                    "latitude": -22.9068,
                    "longitude": -43.1728,
                    "road_name": "Ponte Rio-Niterói",
                },
            ]

            mock_gcs = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_gcs.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob

            res = consolidate_and_export_pipeline(
                raw_pois=sample_pois,
                output_dir=temp_dir,
                gcs_client=mock_gcs,
            )

            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["total_consolidated_pois"], 2)
            self.assertEqual(len(res["uploaded_to_gcs"]), 4)
            # 4 uploads: db, json, csv, sha
            self.assertEqual(mock_blob.upload_from_filename.call_count, 4)

    def test_entrypoint_http_and_cloudevent_handlers(self):
        import base64
        import json
        from unittest.mock import patch
        from sentinela_pipeline.functions import (
            extract_and_stage_handler,
            geocoding_worker_handler,
        )

        # 1. Test extract_and_stage_handler
        with patch("sentinela_pipeline.functions.extractor_entrypoint.extract_and_stage_pipeline") as mock_pipe:
            mock_pipe.return_value = {"status": "SUCCESS", "counts": {}}
            mock_req = MagicMock()
            body_str, code, headers = extract_and_stage_handler(mock_req)
            self.assertEqual(code, 200)
            self.assertIn("SUCCESS", body_str)

        # 2. Test geocoding_worker_handler with HTTP body
        mock_http_req = MagicMock()
        mock_http_req.get_json.return_value = {
            "address_text": "Av. Brasil 100",
            "has_coordinates": False,
        }
        with patch("sentinela_pipeline.functions.geocoder_entrypoint.NominatimClient.geocode") as mock_geo:
            mock_geo.return_value = (-22.8, -43.2, "Av Brasil")
            res_str, code, _ = geocoding_worker_handler(mock_http_req)
            self.assertEqual(code, 200)
            self.assertIn("NOMINATIM_OSM", res_str)

        # 3. Test geocoding_worker_handler with CloudEvent
        class MockCloudEvent:
            def __init__(self, data_dict):
                raw = json.dumps(data_dict).encode("utf-8")
                self.data = {"message": {"data": base64.b64encode(raw).decode("utf-8")}}

        event = MockCloudEvent({"address_text": "Av Paulista", "has_coordinates": False})
        with patch("sentinela_pipeline.functions.geocoder_entrypoint.NominatimClient.geocode") as mock_geo:
            mock_geo.return_value = (-23.5, -46.6, "Paulista")
            res_str2, code2, _ = geocoding_worker_handler(event)
            self.assertEqual(code2, 200)
            self.assertIn("NOMINATIM_OSM", res_str2)


if __name__ == "__main__":
    unittest.main()
