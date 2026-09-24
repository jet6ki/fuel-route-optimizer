"""
API URL Routing.
"""

from django.urls import path
from .views import RouteOptimizeView, HealthCheckView

urlpatterns = [
    path("route/", RouteOptimizeView.as_view(), name="route-optimize"),
    path("health/", HealthCheckView.as_view(), name="health-check"),
]
