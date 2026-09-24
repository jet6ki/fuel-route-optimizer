"""
Routing service using the free Open Source Routing Machine (OSRM).
Queries the driving route between two points and returns the road distance, duration, and GeoJSON geometry.
"""

import requests
from typing import Dict, Any
from django.conf import settings
from .exceptions import RouteNotFoundError, ExternalServiceError

METERS_TO_MILES = 1.0 / 1609.344


def get_driving_route(
    start_lat: float,
    start_lon: float,
    finish_lat: float,
    finish_lon: float,
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Fetches the driving route between start and destination coordinates.

    Args:
        start_lat: Starting latitude.
        start_lon: Starting longitude.
        finish_lat: Destination latitude.
        finish_lon: Destination longitude.
        timeout: HTTP timeout in seconds.

    Returns:
        Dict containing:
            - distance_miles (float)
            - duration_hours (float)
            - geometry (dict with GeoJSON LineString)

    Raises:
        RouteNotFoundError: If no driving path exists.
        ExternalServiceError: If the routing API is down or returns an error.
    """
    base_url = getattr(settings, "ROUTING_SERVICE_URL", "http://router.project-osrm.org").rstrip("/")
    endpoint = f"{base_url}/route/v1/driving/{start_lon},{start_lat};{finish_lon},{finish_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson"
    }
    headers = {
        "User-Agent": "FuelRouteOptimizer/1.0"
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise ExternalServiceError("Routing", f"HTTP status {response.status_code}")
        data = response.json()
    except requests.RequestException as e:
        raise ExternalServiceError("Routing", str(e))

    code = data.get("code")
    if code != "Ok":
        if code == "NoRoute":
            raise RouteNotFoundError("No driving route found between start and destination.")
        message = data.get("message", f"Routing engine returned error code: {code}")
        raise RouteNotFoundError(message)

    routes = data.get("routes", [])
    if not routes:
        raise RouteNotFoundError("No route was returned by the routing engine.")

    best_route = routes[0]
    distance_meters = float(best_route.get("distance", 0.0))
    duration_seconds = float(best_route.get("duration", 0.0))

    distance_miles = distance_meters * METERS_TO_MILES
    duration_hours = duration_seconds / 3600.0

    return {
        "distance_miles": round(distance_miles, 2),
        "duration_hours": round(duration_hours, 2),
        "geometry": best_route.get("geometry", {
            "type": "LineString",
            "coordinates": [[start_lon, start_lat], [finish_lon, finish_lat]]
        })
    }
