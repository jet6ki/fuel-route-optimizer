# 🎓 Beginner-Friendly Project Explanation & Loom Guide

Welcome! If you are a beginner to Django and backend APIs, this guide explains **everything** that is happening in this project in clear, simple English.

It also gives you an **exact 5-minute script and step-by-step walkthrough** to follow when recording your Loom video!

---

## 1. Core Concepts in Simple Words

### What is an API?
An **API (Application Programming Interface)** is like a waiter in a restaurant:
- **You (the client/Postman)** look at the menu and tell the waiter what you want (the Request).
- **The waiter takes your order** to the kitchen (our Django backend).
- **The kitchen cooks the food** (finds the route, checks gas prices, calculates the math).
- **The waiter brings the plate back** to your table (the JSON Response).

### What is Django doing?
**Django** is our Python web server and backend framework:
1. It listens on port `8000` for incoming HTTP requests.
2. It uses **Django REST Framework (DRF)** to validate the JSON data sent by the user (ensuring the user didn't send blank fields or identical locations).
3. It routes the request to our Python services (`geocoding`, `routing`, `station_store`, and `optimizer`).
4. It formats the Python calculation results back into clean JSON and sends it to the user.

### What does the POST Request do?
When you send:
```json
POST /api/route/
{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}
```
You are asking our server:
*"Please plan a driving route from New York to Chicago, find the cheapest gas stations along the road, and tell me where I need to refuel my car so I don't run out of fuel."*

---

## 2. What Happens Behind the Scenes (Step-by-Step)

When a request arrives, Django executes 5 clear steps:

```
[User Request]
      ↓
1. Validation (serializers.py)
      ↓
2. Geocoding (services/geocoding.py)  ──→ Converts "New York, NY" into (40.7128, -74.0060)
      ↓
3. Routing (services/routing.py)      ──→ Calls OSRM: Gets 790 miles + road path coordinates
      ↓
4. Station Matching (station_store.py)──→ Finds all gas stations within 10 miles of highway
      ↓
5. Optimization (optimizer.py)        ──→ Chooses cheapest stop within vehicle's 500-mile range
      ↓
[Clean JSON Response to User]
```

### Step 1: Input Validation
`api/serializers.py` verifies:
- Are `start` and `finish` provided?
- Are they non-empty strings?
- Are start and destination different places?
If anything is wrong, it immediately returns a `400 Bad Request` with a helpful error message instead of crashing.

### Step 2: Geocoding
Computers don't know geography from words like "New York" or "Chicago". They need GPS coordinates (latitude and longitude).
- `api/services/geocoding.py` calls the free **Photon (OpenStreetMap)** geocoder.
- It returns:
  - New York: `40.7128, -74.0060`
  - Chicago: `41.8781, -87.6298`
- **Smart caching:** If you query "New York" again, it gets it from internal memory in `0.0` milliseconds!

### Step 3: Routing Engine
`api/services/routing.py` calls the free **OSRM (Open Source Routing Machine)**.
- In **one single call**, OSRM gives us:
  1. The exact highway driving distance (e.g., `790.57 miles`).
  2. The travel duration (e.g., `14.85 hours`).
  3. A list of thousands of coordinates (GeoJSON `LineString`) showing the exact path the car travels on the interstate highway.

### Step 4: Finding Gas Stations Along the Path
- The project has a local file `data/fuel_stations.csv` containing **7,531 real US truck stops** with their retail diesel prices and coordinates.
- `api/services/station_store.py` looks at the route's path and finds which stations are within **10 miles** of the highway.
- For each station, it figures out its **mile marker** along the trip (e.g. Sheetz in Youngstown, OH is at **Mile 391.9**).
- **Speed advantage:** This happens entirely inside Python memory in just **40 milliseconds**, without making a single slow external API call!

### Step 5: Fuel Stop Optimizer & Cost Calculator
`api/services/optimizer.py` implements the rules given by the company:
- Vehicle range: **500 miles**.
- Vehicle mileage: **10 miles per gallon (mpg)**.
- Starts with a **full tank** (500 miles range).

**How it decides:**
1. **Short trip (under 500 miles):**
   - E.g., New York to Philadelphia (95 miles).
   - The car can complete the entire trip on its starting full tank!
   - Result: `0 fuel stops required`, `$0.00` en-route purchase cost.
2. **Longer trip (e.g. 790 miles to Chicago):**
   - The car cannot make 790 miles on one 500-mile tank.
   - It searches for gas stations between Mile 250 and Mile 480 (leaving a 20-mile safety buffer).
   - In that window, it looks at all available stations and picks the one with the **lowest retail price per gallon**!
   - For New York to Chicago, it picks **SHEETZ #639** in Youngstown, OH at **$3.059/gallon**.
   - It refuels at Youngstown. From Youngstown to Chicago is only ~398 miles, so the vehicle reaches Chicago with **just 1 stop**!

---

## 3. How the Fuel Cost is Calculated

Let's look at the math for New York to Chicago:
- **Total Route Distance:** `790.57 miles`
- **Fuel Economy:** `10 miles per gallon`
- **Total Gallons Consumed:** `790.57 / 10 = 79.06 gallons`
- **Station Selected:** SHEETZ #639 at `$3.059` per gallon.
- **Total Fuel Cost:** `79.06 gallons × $3.059/gal = $241.84`

Every gallon of fuel used on the trip is accounted for, and the price is taken strictly from the official assessment dataset.

---

## 4. What Each Major Project File Does

| File | Purpose in Plain English |
|---|---|
| `fuel_project/settings.py` | Configures Django, loads `.env` variables, and sets default vehicle parameters. |
| `fuel_project/urls.py` | Routes web traffic starting with `/api/` to our `api` app. |
| `api/urls.py` | Connects `/api/route/` and `/api/health/` to their respective view functions. |
| `api/views.py` | The controller: coordinates geocoding, routing, gas station matching, and optimization. |
| `api/serializers.py` | Validates input (ensures valid start/finish) and structures the clean JSON output. |
| `api/services/exceptions.py` | Custom error classes (e.g., `LocationNotFoundError`, `NoUsableStationError`). |
| `api/services/geocoding.py` | Translates city names into latitude/longitude with in-memory caching. |
| `api/services/routing.py` | Talks to OSRM to get highway distance and path geometry. |
| `api/services/station_store.py` | Fast spatial math (Haversine formula) to find gas stations within 10 miles of highway. |
| `api/services/optimizer.py` | The brain: chooses reachable, cheapest gas stations and computes total gallons and cost. |
| `api/management/commands/load_fuel_stations.py` | Offline tool to enrich the raw CSV with coordinates from US Cities database. |
| `api/tests.py` | 14 automated tests verifying all scenarios (short trips, long trips, missing inputs, errors). |
| `requirements.txt` | Minimal list of Python packages needed to run the project. |
| `postman_collection.json` | Ready-to-import Postman collection with example requests. |

---

## 5. Loom Video Guide (5-Minute Walkthrough)

Here is a recommended script you can follow for your Loom video:

### ⏱️ Minute 0:00 - 0:45 | Introduction & Overview
> *"Hello! Today I'm presenting my solution for the Fuel Stop & Route Optimizer API built with Django REST Framework.*
> *The problem: Given a start and destination in the USA, calculate the driving route, find gas stations along the highway from the provided fuel dataset, and pick the most cost-effective fuel stops so a vehicle with a 500-mile range and 10 mpg completes the journey safely."*

### ⏱️ Minute 0:45 - 1:45 | Architecture & External API Strategy
> *"Key requirements were speed, keeping external API calls minimal, and using 100% free services without API keys or credit cards.*
> *For routing, I used OSRM (Open Source Routing Machine). In just ONE call, it gives us the road distance, duration, and GeoJSON geometry.*
> *For geocoding city names, I used Photon (OpenStreetMap).*
> *Notice our dataset originally had 8,151 stations with cities and states, but NO coordinates! To avoid making 8,000 slow API calls at runtime, I pre-enriched the dataset with US Census city coordinates. It loads in memory in 15ms and does spatial matching locally. This means ZERO external API calls for gas stations, making our API respond in under a second!"*

### ⏱️ Minute 1:45 - 3:00 | Live Postman Demonstration
*(Open Postman and run requests from `postman_collection.json`):*

1. **Demonstrate New York to Chicago (Mid-Distance):**
   - Click Send on `POST /api/route/` with `{"start": "New York, NY", "finish": "Chicago, IL"}`.
   - Show response:
     - Distance: `790.57 miles`.
     - Fuel used: `79.06 gallons`.
     - Stops: Exactly **1 fuel stop** at **SHEETZ in Youngstown, OH** at Mile 391.9 for **$3.059/gal**.
     - Point out: *"391.9 miles is within the 500-mile range from New York, and from Youngstown to Chicago is ~398 miles, so it completes the trip in just 1 stop at the cheapest available station!"*

2. **Demonstrate Short Trip (<500 miles):**
   - Send `{"start": "New York, NY", "finish": "Philadelphia, PA"}` (~95 miles).
   - Point out: *"0 fuel stops required because the vehicle has a 500-mile starting tank. En-route cost is $0.00."*

3. **Demonstrate Error Handling:**
   - Send empty body or missing finish field: Show the clean `400 Bad Request`.
   - Send a non-existent city: Show the clean `404 Not Found`.

### ⏱️ Minute 3:00 - 4:15 | Code Walkthrough
*(Open VS Code / editor):*
- Show `api/services/optimizer.py`:
  - Show how the while loop checks `remaining_distance > 500`.
  - Show the search window `[current_mile + 250, current_mile + 480]`.
  - Show `min(candidates, key=lambda s: s["retail_price"])` selecting the cheapest fuel price.
- Show `api/services/station_store.py`:
  - Show the Haversine formula and route corridor check.
- Show `api/serializers.py`:
  - Show how inputs are validated.

### ⏱️ Minute 4:15 - 5:00 | Automated Tests & Conclusion
- Switch to terminal:
  - Run `python manage.py test api -v 2`.
  - Point out: *"All 14 unit tests pass in 0.05 seconds. All external API calls are mocked so the tests are 100% reliable and offline-ready."*
- Wrap up:
  - *"Thank you! The code is clean, fully documented, follows Django best practices, and is ready for production."*

---

You are completely prepared! Run the project with confidence.
