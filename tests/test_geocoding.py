"""Unit tests for GeocoderService, NominatimClient and GoogleMapsClient."""

import unittest
from unittest.mock import MagicMock, patch
from sentinela_pipeline.geocoding import (
    AddressCacheManager,
    GeocoderService,
    GoogleMapsClient,
    NominatimClient,
)


class TestGeocoding(unittest.TestCase):
    def test_nominatim_rate_limiting_wait(self):
        client = NominatimClient(min_interval_seconds=0.05)
        client._last_request_time = 0.0
        client._wait_for_rate_limit()
        # Ensure last request time updated
        self.assertGreater(client._last_request_time, 0.0)

    @patch("urllib.request.urlopen")
    def test_nominatim_geocode_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'[{"lat": "-23.5505", "lon": "-46.6333", "display_name": "Av. 23 de Maio"}]'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = NominatimClient(min_interval_seconds=0.0)
        result = client.geocode("Av. 23 de Maio, São Paulo")

        self.assertIsNotNone(result)
        lat, lon, name = result
        self.assertEqual(lat, -23.5505)
        self.assertEqual(lon, -46.6333)
        self.assertEqual(name, "Av. 23 de Maio")

    def test_google_maps_without_key_returns_none(self):
        client = GoogleMapsClient(api_key="")
        result = client.geocode("Rodovia BR-116 km 100")
        self.assertIsNone(result)

    @patch("urllib.request.urlopen")
    def test_google_maps_geocode_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "OK", "results": [{"geometry": {"location": {"lat": -22.9, "lng": -43.1}, "location_type": "ROOFTOP"}}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = GoogleMapsClient(api_key="TEST_KEY")
        result = client.geocode("Aterro do Flamengo, Rio de Janeiro")

        self.assertIsNotNone(result)
        lat, lon, precision = result
        self.assertEqual(lat, -22.9)
        self.assertEqual(lon, -43.1)
        self.assertEqual(precision, "ROOFTOP")

    def test_clients_empty_and_error_handling(self):
        nom = NominatimClient(min_interval_seconds=0.0)
        self.assertIsNone(nom.geocode(""))
        self.assertIsNone(nom.geocode("   "))

        gmaps = GoogleMapsClient(api_key="KEY")
        self.assertIsNone(gmaps.geocode(""))
        self.assertIsNone(gmaps.geocode("   "))

        # Status != OK
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ZERO_RESULTS", "results": []}'
            mock_url.return_value.__enter__.return_value = mock_resp
            self.assertIsNone(gmaps.geocode("Unknown Island"))

            # Exception
            mock_url.side_effect = Exception("Network down")
            self.assertIsNone(gmaps.geocode("Anywhere"))
            self.assertIsNone(nom.geocode("Anywhere"))

    def test_geocoder_service_multi_tier(self):
        cache = AddressCacheManager()
        mock_nom = MagicMock(spec=NominatimClient)
        mock_gmaps = MagicMock(spec=GoogleMapsClient)

        service = GeocoderService(cache_manager=cache, nominatim_client=mock_nom, google_maps_client=mock_gmaps)

        # 1. First call: miss cache, hits Nominatim
        mock_nom.geocode.return_value = (-15.7942, -47.8821, "Eixão")
        res1 = service.resolve_address("Eixão Sul, Brasília - DF")
        self.assertIsNotNone(res1)
        self.assertEqual(res1[0], -15.7942)
        self.assertEqual(res1[2], "NOMINATIM_OSM")
        mock_nom.geocode.assert_called_once()
        mock_gmaps.geocode.assert_not_called()

        # 2. Second call with same address: must hit cache directly without calling Nominatim
        mock_nom.reset_mock()
        res2 = service.resolve_address("Eixão Sul, Brasília - DF")
        self.assertIsNotNone(res2)
        self.assertEqual(res2[0], -15.7942)
        mock_nom.geocode.assert_not_called()

        # 3. Third call: Nominatim fails, triggers Google Maps fallback
        mock_nom.geocode.return_value = None
        mock_gmaps.geocode.return_value = (-20.3155, -40.3128, "APPROXIMATE")

        res3 = service.resolve_address("Rodovia do Sol km 10, Vila Velha - ES")
        self.assertIsNotNone(res3)
        self.assertEqual(res3[0], -20.3155)
        self.assertEqual(res3[2], "GOOGLE_MAPS")
        mock_gmaps.geocode.assert_called_once()

    def test_enrich_records(self):
        cache = AddressCacheManager()
        mock_nom = MagicMock(spec=NominatimClient)
        mock_nom.geocode.return_value = (-25.4289, -49.2671, "Curitiba")

        service = GeocoderService(cache_manager=cache, nominatim_client=mock_nom)

        records = [
            {"id": 1, "latitude": -23.5, "longitude": -46.6, "address_text": "Existing"},
            {"id": 2, "latitude": None, "longitude": None, "address_text": "Linha Verde, Curitiba"},
            {"id": 3, "latitude": None, "longitude": None, "address_text": ""},  # No address
        ]

        enriched, newly_resolved = service.enrich_records(records)
        self.assertEqual(len(enriched), 3)
        self.assertEqual(newly_resolved, 1)
        self.assertEqual(enriched[0]["latitude"], -23.5)
        self.assertEqual(enriched[1]["latitude"], -25.4289)
        self.assertIsNone(enriched[2]["latitude"])


if __name__ == "__main__":
    unittest.main()
