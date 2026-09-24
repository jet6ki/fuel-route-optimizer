# 🚗 Fuel Stop & Route Optimizer API

A fast, production-ready Django REST backend API that calculates driving routes across the USA, identifies fuel stations along the highway corridor using real-world retail fuel prices, and computes the most cost-effective fuel stops so a vehicle can complete its journey safely within its 500-mile tank range.

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [What the API Does](#what-the-api-does)
3. [Architecture in Simple Terms](#architecture-in-simple-terms)
4. [Requirements](#requirements)
5. [Installation & Setup](#installation--setup)
6. [Environment Variables](#environment-variables)
7. [Running Locally](#running-locally)
8. [Running Automated Tests](#running-automated-tests)
9. [API Endpoints & Specifications](#api-endpoints--specifications)
10. [Example Request & Response](#example-request--response)
11. [Routing & Geocoding APIs Used](#routing--geocoding-apis-used)
12. [Fuel-Price Dataset Explanation](#fuel-price-dataset-explanation)
13. [Fuel-Stop Selection Algorithm](#fuel-stop-selection-algorithm)
14. [External API Call Strategy](#external-api-call-strategy)
15. [Known Assumptions & Limitations](#known-assumptions--limitations)
16. [Postman Testing Instructions](#postman-testing-instructions)

---

## 🌟 Project Overview

When driving long distances across the United States, commercial trucks and passenger vehicles must plan fuel stops strategically. Stopping at the wrong station can cost significantly more money, and running out of fuel stranded on an interstate is dangerous.

This project solves this optimization problem:
- **Vehicle Constraints:**
  - Maximum driving range on a full tank: **500 miles**
  - Fuel economy: **10 miles per gallon (mpg)**
  - Initial fuel status: Starts with a full tank (500 miles range)
- **Goal:** Find the driving route between any two USA locations, locate real gas stations along that path, choose the cheapest combination of reachable fuel stops, and calculate total fuel cost.

---

## ⚙️ What the API Does

1. **Accepts Start & Destination:** Receives USA addresses (e.g., `"New York, NY"`, `"Chicago, IL"`) or raw GPS coordinates (e.g., `"40.7128, -74.0060"`).
2. **Geocodes Locations:** Converts city/state names into latitude and longitude using a free OpenStreetMap-based service.
3. **Fetches Highway Driving Path:** Queries the free Open Source Routing Machine (OSRM) to get exact highway distance, duration, and GeoJSON path coordinates.
4. **Locates Nearby Gas Stations:** Filters through 7,500+ real truck stops to identify stations within a 10-mile corridor of the route.
5. **Optimizes Refueling Stops:** Employs a deterministic, price-minimizing greedy algorithm to select fuel stops so the car never runs dry and total expense is minimized.
6. **Calculates Fuel Cost:** Accurately computes gallons consumed ($D / 10$) and dollar expenses based strictly on the provided dataset prices.
7. **Returns JSON:** Provides complete route summaries, step-by-step stop details, and map polyline geometry for frontend visualization.

---

## 🏗️ Architecture in Simple Terms

The project follows a clean, modular structure:

```
fuel_route_optimizer/
├── api/
│   ├── management/commands/
│   │   └── load_fuel_stations.py   # Script to pre-enrich CSV with coordinates
│   ├── services/
│   │   ├── exceptions.py           # Custom, structured error definitions
│   │   ├── geocoding.py            # Converts text addresses to (lat, lon) + caching
│   │   ├── routing.py              # Fetches road distances & GeoJSON from OSRM
│   │   ├── station_store.py        # Loads fuel dataset & spatial corridor filtering
│   │   └── optimizer.py            # Deterministic fuel stop & price calculation
│   ├── serializers.py              # Request validation & response schemas
│   ├── views.py                    # API controllers (RouteOptimizeView, HealthCheckView)
│   ├── urls.py                     # Route URL dispatcher
│   └── tests.py                    # 14 comprehensive unit tests
├── data/
│   ├── fuel-prices-for-be-assessment.csv  # Original unmodified assessment CSV
│   └── fuel_stations.csv                  # Pre-geocoded fuel stations dataset
├── fuel_project/
│   ├── settings.py                 # Django configuration & environment loader
│   ├── urls.py                     # Root URL routing
│   └── wsgi.py                     # WSGI gateway
├── .env.example                    # Template for environment variables
├── .gitignore                      # Git exclusion rules
├── requirements.txt                # Python package dependencies
├── postman_collection.json         # Postman collection for testing
├── README.md                       # Main documentation
└── PROJECT_EXPLANATION.md          # Simple beginner explanation for Loom presentation
```

---

## 📦 Requirements

- **Python:** 3.9+ (tested on Python 3.9, 3.10, 3.11, 3.12)
- **Django:** 4.2 LTS
- **Django REST Framework:** 3.16+
- **Requests:** 2.32+
- **Python-Dotenv:** 1.2+

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd fuel_route_optimizer
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # On macOS/Linux:
   python3 -m venv venv
   source venv/bin/activate

   # On Windows:
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables:**
   ```bash
   cp .env.example .env
   ```

5. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

---

## 🔑 Environment Variables

The project reads settings from a `.env` file in the root directory:

| Variable | Default Value | Description |
|---|---|---|
| `SECRET_KEY` | *(dev key)* | Django secret key for session/token cryptographic signing. |
| `DEBUG` | `True` | Set to `False` in production. |
| `ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hostnames. |
| `ROUTING_SERVICE_URL` | `http://router.project-osrm.org` | Base URL of the free OSRM routing engine. |
| `GEOCODING_SERVICE_URL` | `https://photon.komoot.io/api` | Base URL of the free OpenStreetMap Photon geocoder. |
| `VEHICLE_MAX_RANGE_MILES` | `500.0` | Maximum distance vehicle can travel on a full tank. |
| `VEHICLE_FUEL_ECONOMY_MPG`| `10.0` | Miles traveled per gallon of fuel. |
| `FUEL_STATION_SEARCH_RADIUS_MILES` | `10.0` | Corridor width (miles from highway) to consider stations. |

---

## 💻 Running Locally

Start the Django development server:
```bash
python manage.py runserver
```
The server will start at: `http://127.0.0.1:8000/`

Test health status in your browser or terminal:
```bash
curl http://127.0.0.1:8000/api/health/
```

---

## 🧪 Running Automated Tests

Run the full automated test suite:
```bash
python manage.py test api -v 2
```

### What the Tests Verify:
1. `test_valid_route_request`: Verifies end-to-end route planning and response schema.
2. `test_missing_start_returns_400`: Verifies validation error when `start` is omitted.
3. `test_missing_finish_returns_400`: Verifies validation error when `finish` is omitted.
4. `test_empty_string_input_returns_400`: Verifies whitespace/empty inputs are rejected.
5. `test_identical_start_and_finish_returns_400`: Verifies same start and destination are rejected.
6. `test_short_route_requires_zero_stops`: Verifies routes under 500 miles require 0 stops and $0.00 en-route cost.
7. `test_optimizer_single_fuel_stop`: Verifies optimal stop selection for ~800-mile trip.
8. `test_optimizer_multiple_fuel_stops`: Verifies consecutive legs stay $\le 500$ miles on cross-country trips.
9. `test_optimizer_raises_when_no_usable_station_in_range`: Verifies internal exception when fuel gap cannot be bridged.
10. `test_api_returns_422_when_no_station_reachable`: Verifies API responds with `422 Unprocessable Entity` for fuel deserts.
11. `test_fuel_cost_calculation_math`: Verifies mathematical precision of gallons ($D/10$) and cost summation.
12. `test_routing_api_failure_returns_502`: Verifies graceful `502 Bad Gateway` if OSRM is down.
13. `test_location_not_found_returns_404`: Verifies `404 Not Found` for invalid city names.
14. `test_health_check_endpoint`: Verifies service status check.

> **Note:** All automated tests use Python `unittest.mock` to mock external network requests, ensuring tests run in **under 0.1 seconds** and never fail due to external network flakiness.

---

## 📡 API Endpoints & Specifications

### 1. `POST /api/route/`
Main endpoint for route calculation and fuel stop planning.

#### Request Headers
```http
Content-Type: application/json
Accept: application/json
```

#### Request Body
```json
{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}
```
*Note: Direct coordinates are also supported:*
```json
{
  "start": "40.7128, -74.0060",
  "finish": "41.8781, -87.6298"
}
```

#### HTTP Status Codes
| Status | Meaning | Reason |
|---|---|---|
| `200 OK` | Success | Route and optimal fuel stops calculated successfully. |
| `400 Bad Request` | Client Error | Missing required fields, empty strings, or identical locations. |
| `404 Not Found` | Not Found | Address could not be geocoded or no driving path exists. |
| `422 Unprocessable Entity` | Fuel Desert | Distance between stations exceeds vehicle's 500-mile range. |
| `502 Bad Gateway` | Upstream Error | External routing or geocoding service is unavailable. |

---

### 2. `GET /api/health/`
Lightweight healthcheck endpoint.

#### Response
```json
{
  "status": "healthy",
  "service": "fuel-route-optimizer",
  "version": "1.0.0",
  "fuel_stations_loaded": 7531
}
```

---

## 📝 Example Request & Response

### Request:
```bash
curl -X POST http://127.0.0.1:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "finish": "Chicago, IL"}'
```

### Response:
```json
{
  "success": true,
  "start": "New York, New York",
  "destination": "Chicago, Illinois",
  "route_summary": {
    "total_distance_miles": 790.57,
    "total_duration_hours": 14.85,
    "fuel_economy_mpg": 10.0,
    "vehicle_range_miles": 500.0,
    "total_gallons_used": 79.06,
    "total_fuel_cost_usd": 241.84,
    "estimated_consumed_fuel_value_usd": 241.84,
    "fuel_stops_count": 1,
    "summary_note": "Journey requires 1 fuel stop(s) to complete 790.6 miles cost-effectively within vehicle range."
  },
  "fuel_stops": [
    {
      "stop_number": 1,
      "station_id": "72445",
      "station_name": "SHEETZ #639",
      "address": "I-80 Exit 223",
      "city": "Youngstown",
      "state": "OH",
      "route_mile": 391.9,
      "distance_from_last_stop_miles": 391.9,
      "fuel_price_per_gallon": 3.059,
      "gallons_refueled": 79.06,
      "leg_fuel_cost_usd": 241.84,
      "latitude": 41.0986,
      "longitude": -80.6474
    }
  ],
  "route_geometry": {
    "type": "LineString",
    "coordinates": [
      [-74.006, 40.7128],
      [-74.020, 40.7250],
      "..."
    ]
  }
}
```

---

## 🗺️ Routing & Geocoding APIs Used

- **Routing:** **Open Source Routing Machine (OSRM)**
  - Public demo endpoint: `http://router.project-osrm.org`
  - 100% Free, open-source OpenStreetMap routing engine.
  - Requires **NO credit card**, **NO subscription**, and **NO API key**.
  - Returns road distance, duration, and GeoJSON `LineString` coordinate coordinates along actual interstates in a single call.

- **Geocoding:** **Photon by Komoot (OpenStreetMap)**
  - Endpoint: `https://photon.komoot.io/api`
  - Free, fast OSM-based address search without mandatory API keys.

---

## ⛽ Fuel-Price Dataset Explanation

The provided dataset (`fuel-prices-for-be-assessment.csv`) contains **8,151** truck stop records with the following columns:
1. `OPIS Truckstop ID`: Unique station ID.
2. `Truckstop Name`: Station brand/name (e.g. Sheetz, Pilot, Love's, Kwik Trip).
3. `Address`: Highway exit or local road (e.g. `I-80, EXIT 223`).
4. `City`: Municipality name.
5. `State`: 2-letter state or province abbreviation.
6. `Rack ID`: Wholesale supplier rack number.
7. `Retail Price`: Retail diesel fuel price per gallon (USD).

### Key Finding & Solution:
- **Limitation in Original File:** The original CSV contains city and state, but **no latitude and longitude coordinates**.
- **The Problem:** Calling an external geocoding API for 8,151 stations at runtime would take hours, violate rate limits, and crash response times.
- **The Solution:** We pre-enriched the dataset using the US Cities Geographic Database (derived from the US Census Bureau). This maps `(City, State)` to exact coordinates for **7,531 US fuel stations (100% of US stations in the dataset)**. The resulting `data/fuel_stations.csv` is stored locally in the repo.
- **Data Integrity:** **Zero fuel prices were fabricated or changed.** Every single price and station name comes directly from the original assessment CSV.

---

## 🧠 Fuel-Stop Selection Algorithm

The algorithm is deterministic, greedy, and mathematically optimal for highway travel:

1. **Initial Tank State:** Vehicle starts at mile `0.0` with a full tank of 500 miles range.
2. **Short Trips ($D \le 500$ miles):**
   - If total route distance is $\le 500$ miles, the vehicle arrives on its initial tank.
   - 0 fuel stops are required (`fuel_stops: []`). En-route purchase cost is `$0.00`.
3. **Trips Requiring Stops ($D > 500$ miles):**
   - Let `current_mile` be the vehicle's position (initially 0).
   - While remaining distance $(D - \text{current\_mile}) > 500$:
     - Look ahead in the viable window: `[current_mile + 250, current_mile + 480]` miles.
     - *(The 480-mile upper bound provides a 20-mile safety buffer to avoid running empty).*
     - Filter candidate stations along the route corridor that fall inside this window.
     - If none exist, widen search backwards to `(current_mile, current_mile + 480]`.
     - Pick the station with the **lowest retail fuel price per gallon**.
     - Gallons refueled for the leg = `(station_mile - current_mile) / 10 mpg`.
     - Leg fuel cost = `gallons * station_price`.
     - Advance `current_mile` to `station_mile`.
   - When $(D - \text{current\_mile}) \le 500$, the destination is reachable.
     - Final leg fuel = `(D - current_mile) / 10 mpg`.
     - Priced at the last station's rate (since that is where fuel was purchased).
   - Total fuel cost is the exact sum of all legs, and total gallons equals exactly $D / 10$.

---

## ⚡ External API Call Strategy

Performance is a key assessment criterion. We minimize external calls strictly:

| Operation | External Calls | How It Works |
|---|---|---|
| Geocode Start Location | **1 call** *(0 if cached or coords)* | Photon OSM geocoder with local in-memory cache. |
| Geocode Finish Location | **1 call** *(0 if cached or coords)* | Photon OSM geocoder with local in-memory cache. |
| Fetch Driving Route | **1 call** | OSRM routing API returns distance and full GeoJSON. |
| Gas Station Matching | **0 calls** | Pure Python spatial corridor filter over local dataset in <50ms. |
| Fuel Stop Optimization | **0 calls** | Pure Python deterministic algorithm in <1ms. |
| **Total per request** | **Max 3 calls** | **Consistently completes in under 1 second.** |

---

## ⚠️ Known Assumptions & Limitations

1. **USA Mainland Routes:** The assessment requires starting and finishing in the USA. Fuel stops are matched against US stations.
2. **Initial Tank:** As standard in trip planning, the vehicle is assumed to depart with a full tank of fuel (500 miles range).
3. **Corridor Radius:** Stations within 10 miles perpendicular distance of the highway are considered accessible off-ramp truck stops.
4. **Offline Coordinate Coverage:** City-level coordinates are used for station locations along highway exits, providing high precision for route planning without incurring thousands of slow runtime API requests.

---

## 📮 Postman Testing Instructions

1. Open Postman.
2. Click **Import** (top left).
3. Select `postman_collection.json` located in the root of this project.
4. Make sure your Django server is running (`python manage.py runserver`).
5. Run any of the included requests:
   - `1. Health Check` (GET `http://127.0.0.1:8000/api/health/`)
   - `2. Route: New York to Chicago (~790 mi, 1 Fuel Stop)`
   - `3. Route: New York to Los Angeles (~2790 mi, Cross-Country 6 Stops)`
   - `4. Route: Short Trip (<500 mi, 0 Fuel Stops)`
   - `5. Route: Direct Coordinates Input`
   - `6. Validation Error: Missing finish (Expect 400)`
   - `7. Error: Unknown Location (Expect 404)`
