"""
Dairy Arts Center (Boedecker Theater) scraper, Boulder.
Uses the WordPress REST API (The Events Calendar / Tribe plugin).
Filters by the "Cinema" category to get film screenings only.
"""

import re
import html
import requests
from datetime import datetime

API_URL = "https://thedairy.org/wp-json/tribe/events/v1/events"
THEATER_NAME = "Dairy Arts Center"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}

# Skip non-movie event keywords
SKIP_WORDS = ["oscar party", "cinema club meeting", "fundraiser", "gala"]


def scrape():
    """Return a list of showtime dicts for Dairy Arts Center cinema screenings."""
    print(f"[Dairy] Fetching cinema events from {API_URL}")

    all_events = []
    page = 1
    today = datetime.now().strftime("%Y-%m-%d")

    while True:
        params = {
            "categories": "cinema",
            "per_page": 50,
            "page": page,
            "start_date": today,
        }
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            break

        data = resp.json()
        events = data.get("events", [])
        all_events.extend(events)

        if len(events) < 50:
            break
        page += 1

    print(f"[Dairy] Found {len(all_events)} cinema events")

    results = []
    for event in all_events:
        try:
            showtime = _parse_event(event)
            if showtime:
                results.append(showtime)
        except Exception as e:
            print(f"[Dairy] Error parsing event: {e}")

    print(f"[Dairy] Scraped {len(results)} showings")
    return results


def _parse_event(event):
    """Parse a single WordPress event into a showtime dict."""
    raw_title = event.get("title", "")
    title = html.unescape(raw_title)

    # Skip non-movie events
    if any(skip in title.lower() for skip in SKIP_WORDS):
        return None

    # Clean title: remove date range suffixes like "| Mar 11-14"
    title = re.sub(r"\s*\|\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\d\-\.]+$", "", title)
    title = re.sub(r"\s*[-–]\s*Sold Out!?\s*$", "", title, flags=re.IGNORECASE)
    title = title.strip()

    if not title:
        return None

    # Parse start date/time
    start_date = event.get("start_date", "")
    if not start_date:
        return None

    try:
        dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        date_iso = dt.strftime("%Y-%m-%d")
        time_formatted = dt.strftime("%-I:%M %p")
    except ValueError:
        return None

    # Get event URL
    url = event.get("url", "https://thedairy.org/cinema/")

    # Detect special attributes from categories
    categories = [c.get("name", "") for c in event.get("categories", [])]
    special = None
    if "Cinema Special Events" in categories:
        special = "Special Event"

    # Check for subtitle/CC info
    fmt = "Standard"
    if "Subtitled" in categories:
        fmt = "Subtitled"

    return {
        "title": title,
        "director": None,  # Dairy API doesn't include director
        "year": None,
        "theater": THEATER_NAME,
        "date": date_iso,
        "time": time_formatted,
        "url": url,
        "format": fmt,
        "special": special,
    }


if __name__ == "__main__":
    import json
    results = scrape()
    print(json.dumps(results, indent=2))
