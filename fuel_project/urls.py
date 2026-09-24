"""
URL configuration for fuel_project.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings


def demo_view(request):
    """Serves the interactive Leaflet map frontend directly at http://127.0.0.1:8000/"""
    demo_file = settings.BASE_DIR / "demo.html"
    if demo_file.exists():
        with open(demo_file, "r", encoding="utf-8") as f:
            return HttpResponse(f.read(), content_type="text/html")
    return HttpResponse("demo.html not found", status=404)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("", demo_view, name="demo-ui"),
]
