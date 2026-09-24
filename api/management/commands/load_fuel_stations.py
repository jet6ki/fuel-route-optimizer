"""
Django management command to enrich raw fuel-price data with US city coordinates
and save the result to data/fuel_stations.csv.

Usage:
    python manage.py load_fuel_stations
"""

import csv
import io
import urllib.request
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

US_CITIES_URL = "https://raw.githubusercontent.com/kelvins/US-Cities-Database/main/csv/us_cities.csv"

# Known city coordinate corrections for municipal variations in dataset
US_CITY_ALIASES = {
    ("PORT WENTWORTH", "GA"): (32.1494, -81.1632),
    ("ELIZABETHPORT", "NJ"): (40.6640, -74.2107),
    ("BROOKPARK", "OH"): (41.3989, -81.8251),
    ("EVERGREEN", "AL"): (31.4338, -86.9547),
    ("HENRICO", "VA"): (37.5407, -77.4360),
    ("UNIVERSITY PARK", "IL"): (41.4428, -87.6978),
}


class Command(BaseCommand):
    help = "Enrich raw fuel prices CSV with latitude/longitude coordinates and save to data/fuel_stations.csv"

    def handle(self, *args, **options):
        raw_csv_path = settings.BASE_DIR / "data" / "fuel-prices-for-be-assessment.csv"
        output_csv_path = settings.BASE_DIR / "data" / "fuel_stations.csv"

        if not raw_csv_path.exists():
            self.stderr.write(self.style.ERROR(f"Raw CSV not found at {raw_csv_path}"))
            return

        self.stdout.write("Fetching US cities geographic coordinates database...")
        req = urllib.request.Request(US_CITIES_URL, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode("utf-8")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch US cities database: {e}"))
            return

        city_reader = csv.DictReader(io.StringIO(data))
        city_coords = {
            (r["CITY"].strip().upper(), r["STATE_CODE"].strip().upper()): (
                float(r["LATITUDE"]),
                float(r["LONGITUDE"]),
            )
            for r in city_reader
        }
        self.stdout.write(f"Loaded {len(city_coords)} US city reference points.")

        out_rows = []
        skipped_count = 0

        with open(raw_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = row["City"].strip().upper()
                state = row["State"].strip().upper()
                key = (city, state)

                coords = US_CITY_ALIASES.get(key) or city_coords.get(key)
                if coords:
                    out_rows.append({
                        "station_id": row["OPIS Truckstop ID"].strip(),
                        "name": row["Truckstop Name"].strip(),
                        "address": row["Address"].strip(),
                        "city": row["City"].strip(),
                        "state": state,
                        "rack_id": row.get("Rack ID", "").strip(),
                        "retail_price": float(row["Retail Price"].strip()),
                        "latitude": coords[0],
                        "longitude": coords[1],
                    })
                else:
                    skipped_count += 1

        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "station_id",
                    "name",
                    "address",
                    "city",
                    "state",
                    "rack_id",
                    "retail_price",
                    "latitude",
                    "longitude",
                ],
            )
            writer.writeheader()
            writer.writerows(out_rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully wrote {len(out_rows)} enriched fuel stations to {output_csv_path}."
            )
        )
        if skipped_count:
            self.stdout.write(
                f"Skipped {skipped_count} non-US or unmapped entries."
            )
