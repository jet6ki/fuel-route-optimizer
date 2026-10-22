# Fuel Route Optimizer

> Plans highway driving routes across the US, locates fuel stations along the corridor, and picks the cheapest places to refuel so a vehicle with a 500-mile tank never runs dry.

**Live Demo:** [fuel-route-optimizer-app.vercel.app](https://fuel-route-optimizer-app.vercel.app/)  
**Mirror:** [truck-route-fuel.vercel.app](https://truck-route-fuel.vercel.app/)

---

## What is this?

This is a Django REST backend (paired with an interactive Leaflet frontend) built for a commercial fleet routing problem:

You have a truck traveling between two US locations. It has a **500-mile range** on a full tank, gets **10 miles per gallon**, and starts the journey with a full tank. Gas prices vary widely between states and exits.

Given any origin and destination, this service:
1. Calculates the highway driving path via OSRM.
2. Identifies gas stations from a real-world ~7,500 station dataset within a 10-mile corridor of the route.
3. Finds the cheapest reachable combination of stops to make the trip safely without running out of fuel.
4. Returns the route summary, turn-by-turn stop details, leg fuel costs, and an interactive map deep link.

---

## Quick Start

```bash
# 1. Clone & enter
git clone https://github.com/jet6ki/fuel-route-optimizer.git
cd fuel-route-optimizer

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies & env
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate

# 4. Start the server
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser to test the UI, or hit the health check:
```bash
curl http://127.0.0.1:8000/api/health/
```

---

## How it works under the hood

### 1. The Dataset & The "Zero External API" Solution
The original assessment file (`fuel-prices-for-be-assessment.csv`) had 8,151 truck stops with company names, addresses, and fuel prices, but **no GPS coordinates**.

Querying a geocoder for 8,000 stations on every route request at runtime would be a non-starter (rate limits, 30+ second response times).

To solve this properly:
- I pre-enriched the dataset offline using US Census city centroids into `data/fuel_stations.csv` (7,531 valid US stations).
- When Django boots, all stations load into memory in about 15ms.
- When a route comes in, corridor filtering projects stations onto the highway path using pure Python Haversine math in ~35ms.
- **Result:** zero external API calls for gas stations.

### 2. The Optimizer Algorithm
Why a greedy window search instead of heavy graph algorithms like Dijkstra?

Highway driving moves in a single forward direction along a route. You start with a full tank (500 miles range):
- **Trips under 500 miles (e.g. NY to Philadelphia, 94 mi):** Zero stops needed. The truck finishes on its starting tank ($0.00 en-route cost).
- **Trips over 500 miles (e.g. NY to Chicago, 790 mi):** The truck cannot make it in one go. It searches for stations in a forward window between `current_mile + 250` and `current_mile + 480` (leaving a 20-mile safety buffer so the driver never runs dry).
- Within that window, it picks the station with the lowest retail price per gallon (`min(stations, key=price)`), breaking ties by choosing the furthest station to maximize forward progress.
- It calculates gallons refueled for the leg (`distance / 10 mpg`), advances the odometer, and repeats until the destination is within range.

This runs in $O(N)$ microseconds and avoids the memory and graph construction overhead of dynamic programming on thousands of points.

### 3. External API Budget
External calls are strictly minimized:
- **Geocoding:** Photon (OpenStreetMap) for start and destination. Cached in-memory so repeated lookups take 0ms.
- **Routing:** 1 call to OSRM (`router.project-osrm.org`) which returns distance, duration, and GeoJSON geometry all in one shot.
- **Station Search & Math:** 0 calls (local memory).
- **Total:** Max 3 calls per request. No API keys or credit cards needed.

---

## API Usage

### Endpoint: `POST /api/route/`
Accepts city/state names or raw GPS coordinates:

```bash
curl -X POST http://127.0.0.1:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{
    "start": "New York, NY",
    "finish": "Chicago, IL"
  }'
```

*(Also supports GET requests with query parameters: `GET /api/route/?start=New+York%2C+NY&finish=Chicago%2C+IL`)*

### Sample Response:
```json
{
  "success": true,
  "start": "New York, NY",
  "destination": "Chicago, IL",
  "map_url": "http://127.0.0.1:8000/?start=New+York%2C+NY&finish=Chicago%2C+IL",
  "route_summary": {
    "total_distance_miles": 790.51,
    "total_duration_hours": 14.84,
    "fuel_economy_mpg": 10.0,
    "vehicle_range_miles": 500.0,
    "total_gallons_used": 79.05,
    "total_fuel_cost_usd": 241.81,
    "fuel_stops_count": 1,
    "summary_note": "Journey requires 1 fuel stop(s) to complete 790.5 miles cost-effectively within vehicle range."
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
      "gallons_refueled": 79.05,
      "leg_fuel_cost_usd": 241.81,
      "latitude": 41.0986,
      "longitude": -80.6474
    }
  ],
  "route_geometry": {
    "type": "LineString",
    "coordinates": [[-74.006, 40.712], [-74.02, 40.725], "..."]
  }
}
```

### Endpoint: `GET /api/health/`
```json
{
  "status": "healthy",
  "service": "fuel-route-optimizer",
  "version": "1.0.0",
  "fuel_stations_loaded": 7531
}
```

---

## Testing

Run the test suite:
```bash
python manage.py test api -v 2
```

All 15 tests pass in ~0.05 seconds. External HTTP requests are mocked with `unittest.mock`, so tests run completely offline with no network flakiness.

Coverage includes:
- Valid routing and expected JSON schema (POST and GET)
- Input validation: missing fields, empty strings, identical start and destination (400 Bad Request)
- Short trips under 500 miles (0 stops, $0.00 cost)
- Multi-stop cross-country journeys (every leg strictly $\le$ 500 miles)
- Fuel desert detection (422 Unprocessable Entity when station gap exceeds 500 miles)
- Math precision on gallons ($D / 10$) and cost summation
- Geocoding failure handling (404 Not Found)
- External routing engine failure handling (502 Bad Gateway)

---

## Postman & Visualizer

A ready-to-import Postman collection is included: [`postman_collection.json`](postman_collection.json).

It includes test requests for all valid and error cases. 

**Postman Visualizer:** When you send any route request in Postman, click the **Visualize** tab next to *Pretty / Raw*. The collection has an embedded Leaflet script that renders an interactive route map with clickable fuel pins directly inside Postman's response window.

---

## Project Structure

```
fuel_route_optimizer/
├── api/
│   ├── services/
│   │   ├── geocoding.py       # Photon OSM wrapper with local cache
│   │   ├── routing.py         # OSRM highway path & geometry
│   │   ├── station_store.py   # In-memory station store & 10-mile corridor filter
│   │   └── optimizer.py       # Deterministic greedy fuel stop selector
│   ├── serializers.py         # DRF input/output schemas & validation
│   ├── views.py               # RouteOptimizeView and HealthCheckView
│   └── tests.py               # 15 automated unit tests
├── data/
│   ├── fuel-prices-for-be-assessment.csv  # Original raw dataset
│   └── fuel_stations.csv      # Pre-geocoded station dataset
├── demo.html                  # Interactive Leaflet map UI
├── postman_collection.json    # Postman collection with Visualizer
└── manage.py
```

---

## Assumptions & Tradeoffs

- **Starting fuel:** Vehicle is assumed to depart with a full tank (500 miles range).
- **Corridor radius:** Stations within 10 miles perpendicular distance of the highway are considered accessible off-ramp stops.
- **City-level coordinates for stations:** Since the assessment dataset lacked coordinates, stations are indexed to their municipality coordinates. For cross-country highway route planning, this provides accurate corridor matching without incurring thousands of slow runtime API requests.
- **Geographic scope:** Continental United States only.
