"""
API Views for Route Optimization and Service Health.
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .services.exceptions import (
    LocationNotFoundError,
    RouteNotFoundError,
    NoUsableStationError,
    ExternalServiceError,
    OptimizerBaseException,
)
from .services.geocoding import geocode_location
from .services.routing import get_driving_route
from .services.station_store import find_stations_along_route, load_stations
from .services.optimizer import optimize_fuel_stops
from django.conf import settings

logger = logging.getLogger(__name__)


class RouteOptimizeView(APIView):
    """
    POST /api/route/
    Calculates the driving route between two USA locations, finds optimal fuel stops,
    and calculates total fuel cost based on real fuel-price data.
    """

    def post(self, request, *args, **kwargs):
        # 1. Validate request payload
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "error": "Invalid request payload.",
                    "details": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        start_input = serializer.validated_data["start"]
        finish_input = serializer.validated_data["finish"]

        try:
            # 2. Geocode start and finish points (1 or 2 external calls, cached)
            start_lat, start_lon, start_display = geocode_location(start_input)
            finish_lat, finish_lon, finish_display = geocode_location(finish_input)

            # 3. Fetch driving route from OSRM (1 external call)
            route_data = get_driving_route(start_lat, start_lon, finish_lat, finish_lon)
            total_distance = route_data["distance_miles"]
            duration_hours = route_data["duration_hours"]
            route_geometry = route_data["geometry"]

            # 4. Identify fuel stations along the route corridor (0 external calls, local spatial match)
            candidate_stations = find_stations_along_route(
                coordinates=route_geometry.get("coordinates", []),
                total_route_miles=total_distance
            )

            # 5. Optimize fuel stops based on vehicle range (500 miles) and minimum price
            optimization = optimize_fuel_stops(
                total_distance_miles=total_distance,
                candidate_stations=candidate_stations
            )

            # 6. Format final response
            response_payload = {
                "success": True,
                "start": start_display or start_input,
                "destination": finish_display or finish_input,
                "route_summary": {
                    "total_distance_miles": total_distance,
                    "total_duration_hours": duration_hours,
                    "fuel_economy_mpg": getattr(settings, "VEHICLE_FUEL_ECONOMY_MPG", 10.0),
                    "vehicle_range_miles": getattr(settings, "VEHICLE_MAX_RANGE_MILES", 500.0),
                    "total_gallons_used": optimization["total_gallons_used"],
                    "total_fuel_cost_usd": optimization["total_fuel_cost_usd"],
                    "estimated_consumed_fuel_value_usd": optimization.get("estimated_consumed_fuel_value_usd", 0.0),
                    "fuel_stops_count": optimization["fuel_stops_count"],
                    "summary_note": optimization["summary_note"]
                },
                "fuel_stops": optimization["fuel_stops"],
                "route_geometry": route_geometry
            }

            return Response(response_payload, status=status.HTTP_200_OK)

        except LocationNotFoundError as e:
            return Response(
                {"success": False, "error": e.message},
                status=status.HTTP_404_NOT_FOUND
            )
        except RouteNotFoundError as e:
            return Response(
                {"success": False, "error": e.message},
                status=status.HTTP_404_NOT_FOUND
            )
        except NoUsableStationError as e:
            return Response(
                {"success": False, "error": e.message},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except ExternalServiceError as e:
            return Response(
                {"success": False, "error": e.message},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.exception("Unexpected error occurred while processing route optimization.")
            return Response(
                {"success": False, "error": "An internal server error occurred while processing your request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """
    GET /api/health/
    Health check endpoint to verify API uptime and dataset availability.
    """

    def get(self, request, *args, **kwargs):
        stations = load_stations()
        return Response({
            "status": "healthy",
            "service": "fuel-route-optimizer",
            "version": "1.0.0",
            "fuel_stations_loaded": len(stations)
        }, status=status.HTTP_200_OK)
