"""
Serializers for Route Optimization API request validation and response formatting.
"""

from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Validates incoming route request containing start and finish locations."""
    start = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=255,
        help_text="Starting location in the USA (e.g., 'New York, NY' or '40.7128, -74.0060')"
    )
    finish = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=255,
        help_text="Destination location in the USA (e.g., 'Chicago, IL' or '41.8781, -87.6298')"
    )

    def validate(self, attrs):
        start = attrs.get("start", "").strip()
        finish = attrs.get("finish", "").strip()

        if not start:
            raise serializers.ValidationError({"start": "The start location cannot be empty."})
        if not finish:
            raise serializers.ValidationError({"finish": "The finish location cannot be empty."})

        if start.lower() == finish.lower():
            raise serializers.ValidationError({
                "finish": "Start location and finish location cannot be identical."
            })

        attrs["start"] = start
        attrs["finish"] = finish
        return attrs


class FuelStopSerializer(serializers.Serializer):
    """Formats details for each selected fuel stop along the route."""
    stop_number = serializers.IntegerField()
    station_id = serializers.CharField()
    station_name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    route_mile = serializers.FloatField()
    distance_from_last_stop_miles = serializers.FloatField()
    fuel_price_per_gallon = serializers.FloatField()
    gallons_refueled = serializers.FloatField()
    leg_fuel_cost_usd = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class RouteSummarySerializer(serializers.Serializer):
    """Summary of distances, duration, fuel usage, and total costs."""
    total_distance_miles = serializers.FloatField()
    total_duration_hours = serializers.FloatField()
    fuel_economy_mpg = serializers.FloatField()
    vehicle_range_miles = serializers.FloatField()
    total_gallons_used = serializers.FloatField()
    total_fuel_cost_usd = serializers.FloatField()
    estimated_consumed_fuel_value_usd = serializers.FloatField(required=False)
    fuel_stops_count = serializers.IntegerField()
    summary_note = serializers.CharField()


class RouteResponseSerializer(serializers.Serializer):
    """Complete response structure for the POST /api/route/ endpoint."""
    success = serializers.BooleanField(default=True)
    start = serializers.CharField()
    destination = serializers.CharField()
    route_summary = RouteSummarySerializer()
    fuel_stops = FuelStopSerializer(many=True)
    route_geometry = serializers.DictField()
