"""
Lightweight CORS middleware to allow frontend clients (like VS Code Live Server or Vite)
to query the API locally without browser cross-origin blocks.
"""

from django.http import HttpResponse


class SimpleCorsMiddleware:
    """Adds CORS headers to every response and handles OPTIONS pre-flight checks."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse()
        else:
            response = self.get_response(request)

        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
        return response
