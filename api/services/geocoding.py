"""
Geocoding service to convert location names into (latitude, longitude) coordinates.
Uses Photon (OpenStreetMap-based) and caches results in memory to minimize external calls.
Supports direct coordinate inputs (e.g. '40.7128, -74.0060' or [40.7128, -74.0060]).
"""

import re
import requests
from typing import Tuple, Union, List
from django.conf import settings
from .exceptions import LocationNotFoundError, ExternalServiceError

# In-memory cache to store geocoded locations during application runtime.
# Pre-seeded with major US freight/transit hubs for instant (0ms) resolution.
_GEOCODE_CACHE = {
    "new york, ny": (40.7128, -74.0060, "New York, NY"),
    "chicago, il": (41.8781, -87.6298, "Chicago, IL"),
    "los angeles, ca": (34.0522, -118.2437, "Los Angeles, CA"),
    "dallas, tx": (32.7767, -96.7970, "Dallas, TX"),
    "atlanta, ga": (33.7490, -84.3880, "Atlanta, GA"),
    "houston, tx": (29.7604, -95.3698, "Houston, TX"),
    "denver, co": (39.7392, -104.9903, "Denver, CO"),
    "philadelphia, pa": (39.9526, -75.1652, "Philadelphia, PA"),
    "indianapolis, in": (39.7684, -86.1581, "Indianapolis, IN"),
    "memphis, tn": (35.1495, -90.0490, "Memphis, TN"),
    "kansas city, mo": (39.0997, -94.5786, "Kansas City, MO"),
    "phoenix, az": (33.4484, -112.0740, "Phoenix, AZ"),
    "seattle, wa": (47.6062, -122.3321, "Seattle, WA"),
    "miami, fl": (25.7617, -80.1918, "Miami, FL"),
    "san francisco, ca": (37.7749, -122.4194, "San Francisco, CA"),
    "boston, ma": (42.3601, -71.0589, "Boston, MA"),
    "austin, tx": (30.2672, -97.7431, "Austin, TX"),
    "las vegas, nv": (36.1699, -115.1398, "Las Vegas, NV"),
}


def _parse_coordinates(value: Union[str, List[float]]) -> Union[Tuple[float, float], None]:
    """
    Checks if the input is already a pair of coordinates.
    Accepts:
      - "[lat, lon]" or (lat, lon)
      - "lat, lon" string
    Returns (lat, lon) or None.
    """
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            lat = float(value[0])
            lon = float(value[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except (ValueError, TypeError):
            return None

    if isinstance(value, str):
        # Match pattern "lat, lon"
        match = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$", value)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
            except ValueError:
                return None

    return None


def _geocode_via_nominatim(location_str: str, timeout: int = 6) -> Union[Tuple[float, float, str], None]:
    """Fallback geocoder using OpenStreetMap Nominatim."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": location_str, "format": "json", "limit": 1}
        headers = {"User-Agent": "FuelRouteOptimizer/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            results = resp.json()
            if results and len(results) > 0:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                display = results[0].get("display_name", location_str)
                # Shorten display name to first 2 parts (City, State)
                parts = [p.strip() for p in display.split(",")]
                clean_display = f"{parts[0]}, {parts[1]}" if len(parts) >= 2 else parts[0]
                return lat, lon, clean_display
    except Exception:
        pass
    return None


def geocode_location(location: Union[str, List[float]], timeout: int = 15) -> Tuple[float, float, str]:
    """
    Geocodes a location name into (latitude, longitude, display_name).

    Args:
        location: String address (e.g. "New York, NY") or coordinate pair.
        timeout: HTTP request timeout in seconds (default 15s).

    Returns:
        (latitude, longitude, display_name)

    Raises:
        LocationNotFoundError: If the location cannot be resolved.
        ExternalServiceError: If the geocoding service is unreachable.
    """
    # 1. Check if input is already coordinates
    parsed_coords = _parse_coordinates(location)
    if parsed_coords:
        lat, lon = parsed_coords
        display = f"{lat:.4f}, {lon:.4f}"
        return lat, lon, display

    location_str = str(location).strip()
    cache_key = location_str.lower()

    # 2. Check in-memory cache
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # 3. Call Photon Geocoding API
    url = getattr(settings, "GEOCODING_SERVICE_URL", "https://photon.komoot.io/api")
    params = {
        "q": location_str,
        "limit": 1
    }
    headers = {
        "User-Agent": "FuelRouteOptimizer/1.0"
    }

    photon_error = None
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            if features:
                first = features[0]
                coords = first.get("geometry", {}).get("coordinates", [])
                if len(coords) >= 2:
                    lon = float(coords[0])
                    lat = float(coords[1])
                    props = first.get("properties", {})
                    name = props.get("name") or location_str
                    state = props.get("state") or props.get("country") or ""
                    display_name = f"{name}, {state}".strip(", ") if state else name

                    result = (lat, lon, display_name)
                    _GEOCODE_CACHE[cache_key] = result
                    return result
            else:
                # No features from photon, try fallback before raising not found
                pass
        else:
            photon_error = f"Photon returned HTTP {response.status_code}"
    except requests.RequestException as e:
        photon_error = str(e)

    # 4. Fallback to Nominatim if Photon failed or returned no results
    nominatim_result = _geocode_via_nominatim(location_str, timeout=6)
    if nominatim_result:
        _GEOCODE_CACHE[cache_key] = nominatim_result
        return nominatim_result

    # If both services gave nothing:
    if photon_error:
        raise ExternalServiceError("Geocoding", photon_error)
    raise LocationNotFoundError(location_str)
