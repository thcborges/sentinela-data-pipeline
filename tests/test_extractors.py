"""Unit tests for all 5 radar and POI extractors."""

import unittest
from unittest.mock import MagicMock, patch
from sentinela_pipeline.extractors import (
    AnttExtractor,
    DnitExtractor,
    OpenClawExtractor,
    OsmExtractor,
    PrfExtractor,
)


class TestExtractors(unittest.TestCase):
    def test_antt_pedagios_extraction(self):
        sample = [
            {
                "concessionaria": "AUTOPISTA FLUMINENSE",
                "praca_de_pedagio": "Conselheiro Josino",
                "rodovia": "BR-101",
                "uf": "RJ",
                "km_m": "40.5",
                "municipio": "Campos dos Goytacazes",
                "latitude": "-21.552594",
                "longitude": "-41.331597",
                "tarifa_automovel": "7.50",
                "tarifa_comercial": "15.00",
            },
            {
                "concessionaria": "CCR RIO-SP",
                "praca_de_pedagio": "Pórtico Free Flow Itaguaí",
                "rodovia": "BR-101",
                "uf": "RJ",
                "km_m": "414",
                "municipio": "Itaguaí",
                "latitude": "-22.9123",
                "longitude": "-43.8234",
            },
            {
                # Invalid coordinates (must be skipped)
                "concessionaria": "INVALID",
                "latitude": "0.0",
                "longitude": "0.0",
            },
        ]
        extractor = AnttExtractor("http://mock/pedagios", "http://mock/radares", "TestAgent")
        results = extractor.extract_pedagios(custom_data=sample)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["poi_type"], "TOLL_BOOTH")
        self.assertEqual(results[0]["tarifa_automovel"], 7.50)
        self.assertEqual(results[0]["uf"], "RJ")

        # Free Flow detection
        self.assertEqual(results[1]["poi_type"], "FREE_FLOW_TOLL")

    def test_antt_radares_extraction(self):
        sample = [
            {
                "concessionaria": "CONCEBRA",
                "tipo_de_radar": "Controlador",
                "rodovia": "BR-060",
                "uf": "GO",
                "km_m": "120",
                "municipio": "Anápolis",
                "latitude": "-16.3214",
                "longitude": "-48.9512",
                "velocidade_leve": "80 km/h",
                "velocidade_pesado": "60 km/h",
            },
            {
                "concessionaria": "VIA PAULISTA",
                "tipo_de_radar": "Semáforo com Radar",
                "rodovia": "SP-255",
                "uf": "SP",
                "km_m": "50",
                "municipio": "Araraquara",
                "latitude": "-21.7812",
                "longitude": "-48.1723",
                "velocidade_leve": "60",
            },
        ]
        extractor = AnttExtractor("http://mock/pedagios", "http://mock/radares", "TestAgent")
        results = extractor.extract_radares(custom_data=sample)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["poi_type"], "FIXED_RADAR")
        self.assertEqual(results[0]["speed_limit"], 80)
        self.assertEqual(results[1]["poi_type"], "TRAFFIC_LIGHT_RADAR")
        self.assertEqual(results[1]["speed_limit"], 60)

    def test_prf_radares_extraction(self):
        sample = [
            {
                "IDENTIFICADOR": "PRF-RJ-001",
                "CONCESSIONÁRIA": "NOVADUTRA",
                "BR": "116",
                "UF": "RJ",
                "LOCAL": "165.5",
                "MUNICÍPIO": "São João de Meriti",
                "LATITUDE": -22.8021,
                "LONGITUDE": -43.3712,
                "VELOCIDADE LEVE": "80",
                "VELOCIDADE PESADO": "80",
                "TIPO EQUIPAMENTO": "CONTROLADOR",
            },
            {
                "IDENTIFICADOR": "PRF-SC-002",
                "CONCESSIONÁRIA": "",
                "BR": "BR-101",
                "UF": "SC",
                "LOCAL": "200",
                "MUNICÍPIO": "São José",
                "LATITUDE": -27.6012,
                "LONGITUDE": -48.6234,
                "VELOCIDADE LEVE": "60",
                "VELOCIDADE PESADO": "60",
                "TIPO EQUIPAMENTO": "REDUTOR",
            },
        ]
        extractor = PrfExtractor("http://mock/prf", "TestAgent")
        results = extractor.extract_radares(custom_data=sample)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["poi_type"], "FIXED_RADAR")
        self.assertEqual(results[0]["rodovia"], "BR-116")
        self.assertEqual(results[0]["speed_limit"], 80)
        self.assertEqual(results[1]["poi_type"], "ELECTRONIC_SPEED_BUMP")

    def test_dnit_pncv_extraction(self):
        sample = [
            {
                "codigo": "DNIT-101",
                "uf": "MG",
                "rodovia": "381",
                "km": "480",
                "municipio": "Betim",
                "latitude": -19.9823,
                "longitude": -44.2012,
                "tipo": "RAD",
                "velocidade": "80",
            },
            {
                "codigo": "DNIT-102",
                "uf": "RS",
                "rodovia": "BR-290",
                "km": "112",
                "municipio": "Eldorado do Sul",
                "latitude": -30.0123,
                "longitude": -51.3412,
                "tipo": "REV",
                "velocidade": "50",
            },
        ]
        extractor = DnitExtractor()
        results = extractor.extract_pncv(raw_records=sample)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["poi_type"], "FIXED_RADAR")
        self.assertEqual(results[0]["rodovia"], "BR-381")
        self.assertEqual(results[1]["poi_type"], "ELECTRONIC_SPEED_BUMP")
        self.assertEqual(results[1]["speed_limit"], 50)

    def test_openclaw_normalization_with_and_without_coords(self):
        extractor = OpenClawExtractor("http://mock/openclaw", "TestAgent")

        # Record with coordinates
        rec_coords = {
            "id": "CET-SP-123",
            "tipo_radar": "Fixo",
            "latitude": "-23.5505",
            "longitude": "-46.6333",
            "velocidade": "60",
            "via": "Av. 23 de Maio",
            "municipio": "São Paulo",
            "uf": "SP",
        }
        norm1 = extractor.normalize_record(rec_coords)
        self.assertTrue(norm1["has_coordinates"])
        self.assertEqual(norm1["latitude"], -23.5505)
        self.assertEqual(norm1["longitude"], -46.6333)
        self.assertEqual(norm1["speed_limit"], 60)

        # Record lacking coordinates (needs geocode)
        rec_no_coords = {
            "id": "INMETRO-789",
            "tipo_radar": "Lombada Eletronica",
            "latitude": None,
            "longitude": None,
            "velocidade": "40",
            "logradouro": "Av. das Americas",
            "numero": "500",
            "municipio": "Rio de Janeiro",
            "uf": "RJ",
        }
        norm2 = extractor.normalize_record(rec_no_coords)
        self.assertFalse(norm2["has_coordinates"])
        self.assertIsNone(norm2["latitude"])
        self.assertIn("Av. das Americas", norm2["address_text"])
        self.assertIn("Rio de Janeiro", norm2["address_text"])
        self.assertEqual(norm2["poi_type"], "ELECTRONIC_SPEED_BUMP")

    def test_osm_extractor_parsing(self):
        payload = {
            "elements": [
                {
                    "type": "node",
                    "id": 101,
                    "lat": -23.5505,
                    "lon": -46.6333,
                    "tags": {
                        "highway": "speed_camera",
                        "maxspeed": "60",
                        "name": "Marginal Tiete",
                        "direction": "90",
                    },
                },
                {
                    "type": "node",
                    "id": 102,
                    "lat": -23.5510,
                    "lon": -46.6340,
                    "tags": {
                        "enforcement": "red_light",
                        "camera:traffic_signals": "yes",
                    },
                },
                {
                    "type": "node",
                    "id": 103,
                    "lat": -23.5520,
                    "lon": -46.6350,
                    "tags": {
                        "traffic_calming": "bump",
                    },
                },
                {
                    "type": "node",
                    "id": 104,
                    "lat": -23.5530,
                    "lon": -46.6360,
                    "tags": {
                        "barrier": "toll_booth",
                        "operator": "AutoBAn",
                    },
                },
                {
                    "type": "node",
                    "id": 105,
                    "lat": -23.5540,
                    "lon": -46.6370,
                    "tags": {
                        "amenity": "police",
                        "name": "Posto PRF",
                    },
                },
            ]
        }

        pois = OsmExtractor.parse_payload(payload)
        self.assertEqual(len(pois), 5)
        self.assertEqual(pois[0]["poi_type"], "FIXED_RADAR")
        self.assertEqual(pois[0]["direction"], 90)
        self.assertEqual(pois[1]["poi_type"], "RED_LIGHT_CAMERA")
        self.assertEqual(pois[2]["poi_type"], "PHYSICAL_SPEED_BUMP")
        self.assertEqual(pois[3]["poi_type"], "TOLL_BOOTH")
        self.assertEqual(pois[4]["poi_type"], "HIGHWAY_PATROL")

    def test_openclaw_pagination_and_all_ufs(self):
        extractor = OpenClawExtractor("http://mock/openclaw", "TestAgent")

        # Mock _fetch_url to return page 1 with next_cursor, then page 2
        def mock_fetch(url, timeout=40):
            if "cursor=cur2" in url:
                return {
                    "data": [
                        {"id": "2", "latitude": -23.1, "longitude": -46.1, "tipo": "Radar"}
                    ],
                    "next_cursor": None,
                }
            return {
                "data": [
                    {"id": "1", "latitude": None, "longitude": None, "via": "Av. Brasil", "uf": "SP"}
                ],
                "next_cursor": "cur2",
            }

        extractor._fetch_url = mock_fetch
        batch_events = []
        records = extractor.extract_uf("SP", on_batch_extracted=lambda b: batch_events.append(b))

        self.assertEqual(len(records), 2)
        self.assertEqual(len(batch_events), 2)

        # Test extract_all_ufs
        with_coords, needs_geocode = extractor.extract_all_ufs(["SP"])
        self.assertEqual(len(with_coords), 1)
        self.assertEqual(len(needs_geocode), 1)

    def test_fetch_methods_with_mocked_http(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'[{"latitude": "-22.1", "longitude": "-43.1", "praca_de_pedagio": "P1"}]'

        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value = mock_resp

            antt = AnttExtractor("http://mock/p", "http://mock/r", "Agent")
            res = antt.extract_pedagios()
            self.assertEqual(len(res), 1)

            prf = PrfExtractor("http://mock/prf", "Agent")
            mock_resp.read.return_value = b'[{"LATITUDE": -22.1, "LONGITUDE": -43.1, "IDENTIFICADOR": "PRF-1"}]'
            res_prf = prf.extract_radares()
            self.assertEqual(len(res_prf), 1)

            dnit = DnitExtractor(endpoint_url="http://mock/dnit")
            mock_resp.read.return_value = b'[{"latitude": -22.1, "longitude": -43.1, "codigo": "D1"}]'
            res_dnit = dnit.extract_pncv()
            self.assertEqual(len(res_dnit), 1)


if __name__ == "__main__":
    unittest.main()
