"""
Fuel station data store and spatial route matching service.
Loads enriched fuel station records and finds stations within a corridor along any given route.
"""

import csv
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple
from django.conf import settings

# Earth radius in miles
EARTH_RADIUS_MILES = 3958.8

# Cached in-memory station list
_STATIONS_CACHE: List[Dict[str, Any]] = []


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points on the Earth in miles.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_MILES * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def load_stations(csv_path: Path = None) -> List[Dict[str, Any]]:
    """
    Loads fuel stations from the enriched CSV file into memory.
    Caches the results to avoid reading the file on every request.
    """
    global _STATIONS_CACHE
    if _STATIONS_CACHE:
        return _STATIONS_CACHE

    target_path = csv_path or getattr(settings, "FUEL_DATA_PATH", Path("data/fuel_stations.csv"))

    stations: List[Dict[str, Any]] = []
    if not target_path.exists():
        return stations

    with open(target_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stations.append({
                    "station_id": str(row["station_id"]).strip(),
                    "name": row["name"].strip(),
                    "address": row["address"].strip(),
                    "city": row["city"].strip(),
                    "state": row["state"].strip().upper(),
                    "retail_price": float(row["retail_price"]),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                })
            except (KeyError, ValueError):
                continue

    _STATIONS_CACHE = stations
    return _STATIONS_CACHE


def sample_route_polyline(
    coordinates: List[List[float]],
    step_miles: float = 2.0
) -> Tuple[List[Tuple[float, float, float]], float]:
    """
    Samples route coordinates to produce a lightweight polyline with cumulative road mileage.

    Args:
        coordinates: List of [longitude, latitude] pairs from GeoJSON.
        step_miles: Distance interval to sample points along the route.

    Returns:
        (sampled_points, total_distance) where each point is (lat, lon, cumulative_mile).
    """
    if not coordinates:
        return [], 0.0

    sampled: List[Tuple[float, float, float]] = []
    total_distance = 0.0

    # First point: coordinates[0] is [lon, lat]
    first_lon, first_lat = coordinates[0][0], coordinates[0][1]
    sampled.append((first_lat, first_lon, 0.0))
    last_sampled_lat, last_sampled_lon = first_lat, first_lon

    last_pt_lat, last_pt_lon = first_lat, first_lon

    for pt in coordinates[1:]:
        lon, lat = pt[0], pt[1]
        seg_dist = haversine_miles(last_pt_lat, last_pt_lon, lat, lon)
        total_distance += seg_dist
        last_pt_lat, last_pt_lon = lat, lon

        # Check distance from last sampled point
        dist_from_last_sample = haversine_miles(last_sampled_lat, last_sampled_lon, lat, lon)
        if dist_from_last_sample >= step_miles:
            sampled.append((lat, lon, total_distance))
            last_sampled_lat, last_sampled_lon = lat, lon

    # Ensure last destination coordinate is included
    last_lon, last_lat = coordinates[-1][0], coordinates[-1][1]
    if sampled[-1][0] != last_lat or sampled[-1][1] != last_lon:
        sampled.append((last_lat, last_lon, total_distance))

    return sampled, total_distance


def find_stations_along_route(
    coordinates: List[List[float]],
    search_radius_miles: float = None,
    total_route_miles: float = None
) -> List[Dict[str, Any]]:
    """
    Identifies all fuel stations from the dataset within the search corridor of the route.

    Args:
        coordinates: List of [longitude, latitude] pairs representing the route.
        search_radius_miles: Maximum off-route distance in miles (defaults to setting).
        total_route_miles: Total driving road miles from routing engine.

    Returns:
        List of matched stations sorted by route_mile ascending.
    """
    if search_radius_miles is None:
        search_radius_miles = getattr(settings, "FUEL_STATION_SEARCH_RADIUS_MILES", 10.0)

    stations = load_stations()
    if not stations or not coordinates:
        return []

    # 1. Sample the route polyline with cumulative distances
    sampled_route, polyline_total_dist = sample_route_polyline(coordinates, step_miles=2.0)
    if not sampled_route:
        return []

    # Use actual road distance to scale mile markers accurately if provided
    scale_factor = (total_route_miles / polyline_total_dist) if (total_route_miles and polyline_total_dist > 0) else 1.0

    # 2. Fast bounding box filter
    lats = [pt[0] for pt in sampled_route]
    lons = [pt[1] for pt in sampled_route]
    deg_buffer = (search_radius_miles / 69.0) + 0.1

    min_lat, max_lat = min(lats) - deg_buffer, max(lats) + deg_buffer
    min_lon, max_lon = min(lons) - deg_buffer, max(lons) + deg_buffer

    candidates = [
        s for s in stations
        if min_lat <= s["latitude"] <= max_lat and min_lon <= s["longitude"] <= max_lon
    ]

    matched: List[Dict[str, Any]] = []

    # 3. Find closest route point for each candidate
    for station in candidates:
        slat, slon = station["latitude"], station["longitude"]
        min_dist = float("inf")
        best_mile = 0.0

        for rlat, rlon, cum_mile in sampled_route:
            # Quick coarse delta check
            if abs(slat - rlat) <= deg_buffer and abs(slon - rlon) <= deg_buffer:
                d = haversine_miles(slat, slon, rlat, rlon)
                if d < min_dist:
                    min_dist = d
                    best_mile = cum_mile

        if min_dist <= search_radius_miles:
            # Scale cumulative mile to match the official driving route road distance
            scaled_mile = round(best_mile * scale_factor, 1)

            station_record = dict(station)
            station_record["route_mile"] = scaled_mile
            station_record["distance_to_highway_miles"] = round(min_dist, 2)
            matched.append(station_record)

    # Sort strictly by route mile ascending
    matched.sort(key=lambda s: s["route_mile"])
    return matched
