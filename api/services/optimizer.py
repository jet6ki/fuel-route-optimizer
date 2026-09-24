"""
Fuel stop optimization engine.
Determines the optimal, reachable, and cost-effective fuel stops for a vehicle
with a 500-mile range and 10 miles/gallon fuel economy.
"""

from typing import List, Dict, Any, Optional
from django.conf import settings
from .exceptions import NoUsableStationError


def optimize_fuel_stops(
    total_distance_miles: float,
    candidate_stations: List[Dict[str, Any]],
    max_range_miles: float = None,
    fuel_economy_mpg: float = None,
    safety_buffer_miles: float = 20.0,
    min_leg_distance_miles: float = 250.0
) -> Dict[str, Any]:
    """
    Selects optimal fuel stops along the route to ensure the vehicle completes the journey
    at the minimum fuel cost without exceeding its range.

    Args:
        total_distance_miles: Total driving distance in miles.
        candidate_stations: List of candidate stations sorted by route_mile ascending.
        max_range_miles: Maximum tank range (default 500 miles).
        fuel_economy_mpg: Vehicle fuel efficiency in mpg (default 10 mpg).
        safety_buffer_miles: Miles subtracted from max range as safety reserve (default 20 miles).
        min_leg_distance_miles: Minimum progress before seeking next stop (default 250 miles).

    Returns:
        Dict with keys:
            - total_gallons_used
            - total_fuel_cost_usd
            - fuel_stops_count
            - fuel_stops (list of dicts)
            - summary_note
    """
    if max_range_miles is None:
        max_range_miles = getattr(settings, "VEHICLE_MAX_RANGE_MILES", 500.0)
    if fuel_economy_mpg is None:
        fuel_economy_mpg = getattr(settings, "VEHICLE_FUEL_ECONOMY_MPG", 10.0)

    total_gallons_used = round(total_distance_miles / fuel_economy_mpg, 2)
    effective_max_range = max_range_miles - safety_buffer_miles  # 480 miles

    # Case 1: Short trips under max range (500 miles)
    if total_distance_miles <= max_range_miles:
        # Determine average/cheapest nearby station price if available for reference
        ref_price = candidate_stations[0]["retail_price"] if candidate_stations else 3.50
        consumed_value = round(total_gallons_used * ref_price, 2)

        return {
            "total_gallons_used": total_gallons_used,
            "total_fuel_cost_usd": 0.0,
            "estimated_consumed_fuel_value_usd": consumed_value,
            "fuel_stops_count": 0,
            "fuel_stops": [],
            "summary_note": (
                f"Trip distance ({total_distance_miles:.1f} mi) is within the vehicle's 500-mile range. "
                "The journey is completed on the starting full tank without needing en-route fuel stops."
            )
        }

    # Case 2: Trips requiring one or more fuel stops
    selected_stops: List[Dict[str, Any]] = []
    current_mile = 0.0
    total_cost = 0.0
    stop_number = 1

    # Remove candidate stations behind current starting point or beyond destination
    valid_stations = [
        s for s in candidate_stations
        if 0.0 < s["route_mile"] < total_distance_miles
    ]

    while (total_distance_miles - current_mile) > max_range_miles:
        # Target search window: from (current_mile + min_leg_distance) up to (current_mile + effective_max_range)
        window_start = current_mile + min_leg_distance_miles
        window_end = current_mile + effective_max_range

        # Filter stations inside ideal window
        window_candidates = [
            s for s in valid_stations
            if window_start <= s["route_mile"] <= window_end
        ]

        # If no stations in the ideal 250-480 mile window, widen search to (current_mile, current_mile + 480]
        if not window_candidates:
            window_candidates = [
                s for s in valid_stations
                if current_mile < s["route_mile"] <= window_end
            ]

        # If still no station, try up to the absolute hard limit (current_mile + max_range_miles)
        if not window_candidates:
            window_candidates = [
                s for s in valid_stations
                if current_mile < s["route_mile"] <= (current_mile + max_range_miles)
            ]

        # If still no station reachable within 500 miles, vehicle cannot proceed!
        if not window_candidates:
            raise NoUsableStationError(
                mile_marker=current_mile,
                next_target_mile=min(current_mile + max_range_miles, total_distance_miles)
            )

        # Select the station with the lowest retail price
        # In case of tie, choose the station furthest along the route to maximize progress
        best_station = min(
            window_candidates,
            key=lambda s: (s["retail_price"], -s["route_mile"])
        )

        leg_distance = round(best_station["route_mile"] - current_mile, 1)
        leg_gallons = round(leg_distance / fuel_economy_mpg, 2)
        leg_cost = round(leg_gallons * best_station["retail_price"], 2)

        stop_entry = {
            "stop_number": stop_number,
            "station_id": best_station["station_id"],
            "station_name": best_station["name"],
            "address": best_station["address"],
            "city": best_station["city"],
            "state": best_station["state"],
            "route_mile": best_station["route_mile"],
            "distance_from_last_stop_miles": leg_distance,
            "fuel_price_per_gallon": best_station["retail_price"],
            "gallons_refueled": leg_gallons,
            "leg_fuel_cost_usd": leg_cost,
            "latitude": best_station["latitude"],
            "longitude": best_station["longitude"],
        }

        selected_stops.append(stop_entry)
        total_cost += leg_cost
        current_mile = best_station["route_mile"]
        stop_number += 1

    # Remaining distance from the last stop to the destination
    remaining_distance = round(total_distance_miles - current_mile, 1)
    if remaining_distance > 0 and selected_stops:
        last_stop = selected_stops[-1]
        final_leg_gallons = round(remaining_distance / fuel_economy_mpg, 2)
        final_leg_cost = round(final_leg_gallons * last_stop["fuel_price_per_gallon"], 2)

        # The vehicle refuels at the last stop with enough fuel to complete the destination leg
        last_stop["gallons_refueled"] = round(last_stop["gallons_refueled"] + final_leg_gallons, 2)
        last_stop["leg_fuel_cost_usd"] = round(last_stop["leg_fuel_cost_usd"] + final_leg_cost, 2)
        total_cost += final_leg_cost

    total_cost = round(total_cost, 2)

    return {
        "total_gallons_used": total_gallons_used,
        "total_fuel_cost_usd": total_cost,
        "estimated_consumed_fuel_value_usd": total_cost,
        "fuel_stops_count": len(selected_stops),
        "fuel_stops": selected_stops,
        "summary_note": (
            f"Journey requires {len(selected_stops)} fuel stop(s) to complete "
            f"{total_distance_miles:.1f} miles cost-effectively within vehicle range."
        )
    }
