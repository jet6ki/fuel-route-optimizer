"""
Django settings for fuel_project.

Configured for Fuel Stop & Route Optimizer API.
"""

import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Suppress benign LibreSSL warning on macOS Python 3.9
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key-change-in-production-1234567890")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    # Local apps
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fuel_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fuel_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "UNAUTHENTICATED_USER": None,
}

# ==========================================
# Fuel Stop & Routing Optimizer Settings
# ==========================================

# Routing service (OSRM public server by default, can be overridden by env)
ROUTING_SERVICE_URL = os.getenv("ROUTING_SERVICE_URL", "http://router.project-osrm.org").rstrip("/")

# Geocoding service (Photon OSM-based geocoder by default, free and no API key required)
GEOCODING_SERVICE_URL = os.getenv("GEOCODING_SERVICE_URL", "https://photon.komoot.io/api").rstrip("/")

# Path to the enriched fuel station dataset
FUEL_DATA_PATH = Path(os.getenv("FUEL_DATA_PATH", BASE_DIR / "data" / "fuel_stations.csv"))

# Vehicle specifications as per requirements
VEHICLE_MAX_RANGE_MILES = float(os.getenv("VEHICLE_MAX_RANGE_MILES", "500.0"))
VEHICLE_FUEL_ECONOMY_MPG = float(os.getenv("VEHICLE_FUEL_ECONOMY_MPG", "10.0"))

# Maximum off-route distance for a gas station to be considered on the route (in miles)
FUEL_STATION_SEARCH_RADIUS_MILES = float(os.getenv("FUEL_STATION_SEARCH_RADIUS_MILES", "10.0"))
