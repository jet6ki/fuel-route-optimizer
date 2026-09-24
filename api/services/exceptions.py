"""
Custom exceptions for the Fuel Route Optimizer service.
"""

class OptimizerBaseException(Exception):
    """Base exception for all application-level errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LocationNotFoundError(OptimizerBaseException):
    """Raised when geocoding fails to resolve an address."""
    def __init__(self, location: str):
        super().__init__(
            message=f"Could not locate '{location}'. Please check the city and state spelling.",
            status_code=404
        )
        self.location = location


class RouteNotFoundError(OptimizerBaseException):
    """Raised when the routing engine cannot find a driving route."""
    def __init__(self, reason: str = "No driving route found between start and destination."):
        super().__init__(message=reason, status_code=404)


class NoUsableStationError(OptimizerBaseException):
    """Raised when vehicle range runs out and no usable fuel station exists."""
    def __init__(self, mile_marker: float, next_target_mile: float):
        super().__init__(
            message=(
                f"Cannot complete the journey: no fuel station is reachable within the "
                f"vehicle's 500-mile range after mile {mile_marker:.1f} (next target mile: {next_target_mile:.1f})."
            ),
            status_code=422
        )
        self.mile_marker = mile_marker
        self.next_target_mile = next_target_mile


class ExternalServiceError(OptimizerBaseException):
    """Raised when an external routing or geocoding API fails or times out."""
    def __init__(self, service_name: str, detail: str = ""):
        msg = f"External {service_name} service is currently unavailable or returned an error."
        if detail:
            msg += f" Details: {detail}"
        super().__init__(message=msg, status_code=502)
        self.service_name = service_name
