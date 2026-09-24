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

# In-memory cache to store geocoded locations during application runtime
_GEOCODE_CACHE = {}


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


def geocode_location(location: Union[str, List[float]], timeout: int = 8) -> Tuple[float, float, str]:
    """
    Geocodes a location name into (latitude, longitude, display_name).

    Args:
        location: String address (e.g. "New York, NY") or coordinate pair.
        timeout: HTTP request timeout in seconds.

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

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise ExternalServiceError("Geocoding", f"Status code {response.status_code}")
        data = response.json()
    except requests.RequestException as e:
        raise ExternalServiceError("Geocoding", str(e))

    features = data.get("features", [])
    if not features:
        raise LocationNotFoundError(location_str)

    first = features[0]
    coords = first.get("geometry", {}).get("coordinates", [])
    if len(coords) < 2:
        raise LocationNotFoundError(location_str)

    # GeoJSON returns [longitude, latitude]
    lon = float(coords[0])
    lat = float(coords[1])

    # Build readable display name
    props = first.get("properties", {})
    name = props.get("name") or location_str
    state = props.get("state") or props.get("country") or ""
    display_name = f"{name}, {state}".strip(", ") if state else name

    result = (lat, lon, display_name)
    _GEOCODE_CACHE[cache_key] = result
    return result
