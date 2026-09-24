"""
Automated Test Suite for Fuel Route Optimizer API.

Covers all 10 required assessment test scenarios:
1. Valid route request
2. Missing start
3. Missing destination (finish)
4. Invalid input (empty strings, identical locations)
5. Short route (<500 miles, 0 stops)
6. Route requiring fuel stop (e.g. ~800 miles, 1 stop)
7. Multiple fuel stops (e.g. >1500 miles)
8. No usable fuel station (unreachable gap -> 422)
9. Fuel-cost calculation precision
10. External API failure (timeout / 500 -> 502)
Plus location not found (404) and health check endpoint (200).
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
import requests

from api.services.exceptions import (
    LocationNotFoundError,
    RouteNotFoundError,
    NoUsableStationError,
    ExternalServiceError,
)
from api.services.optimizer import optimize_fuel_stops


class FuelRouteOptimizerTests(TestCase):
    """Test suite covering API validation, routing, fuel stop logic, and error handling."""

    def setUp(self):
        self.client = APIClient()
        self.route_url = reverse("route-optimize")
        self.health_url = reverse("health-check")

        # Mock GeoJSON geometry for a simple straight route
        self.sample_geometry = {
            "type": "LineString",
            "coordinates": [
                [-74.0060, 40.7128],
                [-77.0369, 40.0000],
                [-80.6474, 41.0986],
                [-84.0000, 41.5000],
                [-87.6298, 41.8781]
            ]
        }

    # -------------------------------------------------------------------------
    # Test 1: Valid route request (mocked external API)
    # -------------------------------------------------------------------------
    @patch("api.views.get_driving_route")
    @patch("api.views.geocode_location")
    def test_valid_route_request(self, mock_geocode, mock_route):
        """A valid request with start and finish returns 200 and expected schema."""
        mock_geocode.side_effect = [
            (40.7128, -74.0060, "New York, NY"),
            (41.8781, -87.6298, "Chicago, IL")
        ]
        mock_route.return_value = {
            "distance_miles": 790.0,
            "duration_hours": 14.5,
            "geometry": self.sample_geometry
        }

        payload = {"start": "New York, NY", "finish": "Chicago, IL"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["start"], "New York, NY")
        self.assertEqual(data["destination"], "Chicago, IL")
        self.assertIn("route_summary", data)
        self.assertIn("fuel_stops", data)
        self.assertIn("route_geometry", data)
        self.assertEqual(data["route_summary"]["total_distance_miles"], 790.0)
        self.assertEqual(data["route_summary"]["fuel_economy_mpg"], 10.0)
        self.assertEqual(data["route_summary"]["vehicle_range_miles"], 500.0)

    # -------------------------------------------------------------------------
    # Test 2: Missing start
    # -------------------------------------------------------------------------
    def test_missing_start_returns_400(self):
        """Omitting the start field returns 400 Bad Request."""
        payload = {"finish": "Chicago, IL"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("start", data["details"])

    # -------------------------------------------------------------------------
    # Test 3: Missing destination (finish)
    # -------------------------------------------------------------------------
    def test_missing_finish_returns_400(self):
        """Omitting the finish field returns 400 Bad Request."""
        payload = {"start": "New York, NY"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("finish", data["details"])

    # -------------------------------------------------------------------------
    # Test 4: Invalid input (empty strings, whitespace, identical locations)
    # -------------------------------------------------------------------------
    def test_empty_string_input_returns_400(self):
        """Empty or whitespace strings return 400 Bad Request."""
        payload = {"start": "   ", "finish": "Chicago, IL"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data["success"])

    def test_identical_start_and_finish_returns_400(self):
        """Start and finish being identical returns 400 Bad Request."""
        payload = {"start": "Chicago, IL", "finish": "Chicago, IL"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data["success"])

    # -------------------------------------------------------------------------
    # Test 5: Short route (<500 miles, 0 stops required)
    # -------------------------------------------------------------------------
    @patch("api.views.get_driving_route")
    @patch("api.views.geocode_location")
    def test_short_route_requires_zero_stops(self, mock_geocode, mock_route):
        """A route under 500 miles completes without fuel stops (0 stops, cost 0.00)."""
        mock_geocode.side_effect = [
            (40.7128, -74.0060, "New York, NY"),
            (39.9526, -75.1652, "Philadelphia, PA")
        ]
        mock_route.return_value = {
            "distance_miles": 95.0,
            "duration_hours": 2.0,
            "geometry": self.sample_geometry
        }

        payload = {"start": "New York, NY", "finish": "Philadelphia, PA"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        summary = data["route_summary"]
        self.assertEqual(summary["fuel_stops_count"], 0)
        self.assertEqual(summary["total_gallons_used"], 9.5)
        self.assertEqual(summary["total_fuel_cost_usd"], 0.0)
        self.assertEqual(data["fuel_stops"], [])
        self.assertIn("within the vehicle's 500-mile range", summary["summary_note"])

    # -------------------------------------------------------------------------
    # Test 6: Route requiring a single fuel stop (~800 miles)
    # -------------------------------------------------------------------------
    def test_optimizer_single_fuel_stop(self):
        """Route of 780 miles requires exactly 1 fuel stop within vehicle range."""
        stations = [
            {
                "station_id": "101",
                "name": "Midway Fuel",
                "address": "I-80 Exit 100",
                "city": "Youngstown",
                "state": "OH",
                "retail_price": 3.10,
                "latitude": 41.0,
                "longitude": -80.6,
                "route_mile": 390.0,
                "distance_to_highway_miles": 1.0
            },
            {
                "station_id": "102",
                "name": "Expensive Fuel",
                "address": "I-80 Exit 95",
                "city": "Girard",
                "state": "OH",
                "retail_price": 3.80,
                "latitude": 41.1,
                "longitude": -80.7,
                "route_mile": 380.0,
                "distance_to_highway_miles": 2.0
            }
        ]

        result = optimize_fuel_stops(total_distance_miles=780.0, candidate_stations=stations)

        self.assertEqual(result["fuel_stops_count"], 1)
        selected = result["fuel_stops"][0]
        # Should pick the cheaper station ($3.10 vs $3.80)
        self.assertEqual(selected["station_id"], "101")
        self.assertEqual(selected["fuel_price_per_gallon"], 3.10)
        self.assertEqual(result["total_gallons_used"], 78.0)
        # Total cost = 78.0 gal * $3.10 = $241.80
        self.assertAlmostEqual(result["total_fuel_cost_usd"], 241.80, places=2)

    # -------------------------------------------------------------------------
    # Test 7: Route requiring multiple fuel stops (>1500 miles)
    # -------------------------------------------------------------------------
    def test_optimizer_multiple_fuel_stops(self):
        """Route of 1600 miles requires multiple stops, each leg <= 500 miles."""
        stations = [
            {
                "station_id": "S1",
                "name": "Stop 1",
                "address": "Exit 1",
                "city": "City 1",
                "state": "ST",
                "retail_price": 3.20,
                "latitude": 40.0,
                "longitude": -80.0,
                "route_mile": 420.0,
                "distance_to_highway_miles": 1.0
            },
            {
                "station_id": "S2",
                "name": "Stop 2",
                "address": "Exit 2",
                "city": "City 2",
                "state": "ST",
                "retail_price": 3.00,
                "latitude": 40.0,
                "longitude": -85.0,
                "route_mile": 880.0,
                "distance_to_highway_miles": 1.5
            },
            {
                "station_id": "S3",
                "name": "Stop 3",
                "address": "Exit 3",
                "city": "City 3",
                "state": "ST",
                "retail_price": 3.40,
                "latitude": 40.0,
                "longitude": -90.0,
                "route_mile": 1300.0,
                "distance_to_highway_miles": 2.0
            }
        ]

        result = optimize_fuel_stops(total_distance_miles=1600.0, candidate_stations=stations)

        self.assertEqual(result["fuel_stops_count"], 3)
        self.assertEqual(result["total_gallons_used"], 160.0)

        # Verify every consecutive leg is strictly <= 500 miles
        stops = result["fuel_stops"]
        prev_mile = 0.0
        for stop in stops:
            leg = stop["route_mile"] - prev_mile
            self.assertLessEqual(leg, 500.0)
            prev_mile = stop["route_mile"]

        final_leg = 1600.0 - prev_mile
        self.assertLessEqual(final_leg, 500.0)

    # -------------------------------------------------------------------------
    # Test 8: No usable fuel station (unreachable gap -> 422)
    # -------------------------------------------------------------------------
    def test_optimizer_raises_when_no_usable_station_in_range(self):
        """If no fuel station exists within 500 miles of current position, raises error."""
        # Route is 1200 miles, but only station is at mile 600 (vehicle runs dry at 500)
        stations = [
            {
                "station_id": "S_FAR",
                "name": "Too Far",
                "address": "Exit 600",
                "city": "Desert",
                "state": "NV",
                "retail_price": 3.50,
                "latitude": 40.0,
                "longitude": -80.0,
                "route_mile": 600.0,
                "distance_to_highway_miles": 1.0
            }
        ]

        with self.assertRaises(NoUsableStationError):
            optimize_fuel_stops(total_distance_miles=1200.0, candidate_stations=stations)

    @patch("api.views.find_stations_along_route")
    @patch("api.views.get_driving_route")
    @patch("api.views.geocode_location")
    def test_api_returns_422_when_no_station_reachable(self, mock_geocode, mock_route, mock_stations):
        """API returns 422 Unprocessable Entity when vehicle range is exceeded."""
        mock_geocode.side_effect = [
            (40.0, -80.0, "Start Point"),
            (40.0, -95.0, "End Point")
        ]
        mock_route.return_value = {
            "distance_miles": 1200.0,
            "duration_hours": 20.0,
            "geometry": self.sample_geometry
        }
        # No stations along the route
        mock_stations.return_value = []

        payload = {"start": "Start Point", "finish": "End Point"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("no fuel station is reachable", data["error"])

    # -------------------------------------------------------------------------
    # Test 9: Fuel-cost calculation precision
    # -------------------------------------------------------------------------
    def test_fuel_cost_calculation_math(self):
        """Total fuel gallons = total distance / 10 mpg, and leg costs sum accurately."""
        stations = [
            {
                "station_id": "1",
                "name": "Station 1",
                "address": "Addr 1",
                "city": "City 1",
                "state": "OH",
                "retail_price": 3.00,
                "latitude": 41.0,
                "longitude": -80.0,
                "route_mile": 400.0,
                "distance_to_highway_miles": 1.0
            }
        ]

        # 700 miles total:
        # Leg 1: 0 to 400 = 400 mi -> 40.0 gal @ $3.00 = $120.00
        # Leg 2: 400 to 700 = 300 mi -> 30.0 gal @ $3.00 = $90.00
        # Total gallons: 70.0 gal
        # Total cost: $210.00
        result = optimize_fuel_stops(total_distance_miles=700.0, candidate_stations=stations)

        self.assertEqual(result["total_gallons_used"], 70.0)
        self.assertEqual(result["total_fuel_cost_usd"], 210.0)

    # -------------------------------------------------------------------------
    # Test 10: External API failure (Routing engine error / timeout)
    # -------------------------------------------------------------------------
    @patch("api.views.get_driving_route")
    @patch("api.views.geocode_location")
    def test_routing_api_failure_returns_502(self, mock_geocode, mock_route):
        """When external routing service fails, API returns 502 Bad Gateway."""
        mock_geocode.side_effect = [
            (40.7128, -74.0060, "New York, NY"),
            (41.8781, -87.6298, "Chicago, IL")
        ]
        mock_route.side_effect = ExternalServiceError("Routing", "Connection timed out.")

        payload = {"start": "New York, NY", "finish": "Chicago, IL"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("Routing service is currently unavailable", data["error"])

    # -------------------------------------------------------------------------
    # Test 11: Geocoding location not found (404)
    # -------------------------------------------------------------------------
    @patch("api.views.geocode_location")
    def test_location_not_found_returns_404(self, mock_geocode):
        """When an address cannot be geocoded, API returns 404 Not Found."""
        mock_geocode.side_effect = LocationNotFoundError("NonExistentFakePlace12345")

        payload = {"start": "NonExistentFakePlace12345", "finish": "Chicago, IL"}
        response = self.client.post(self.route_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("Could not locate", data["error"])

    # -------------------------------------------------------------------------
    # Test 12: Health check endpoint
    # -------------------------------------------------------------------------
    def test_health_check_endpoint(self):
        """GET /api/health/ returns 200 OK and healthy status."""
        response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("fuel_stations_loaded", data)
