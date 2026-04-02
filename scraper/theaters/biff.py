"""
Boulder International Film Festival (BIFF) scraper.
Uses the Eventive REST API directly - no browser automation needed.
BIFF's Eventive bucket contains films and events (screenings) with full metadata.
"""

import requests
from datetime import datetime, timezone, timedelta

API_BASE = "https://api.eventive.org"
BUCKET_ID = "69110eabe17970ca65c4dd33"
API_KEY = "ad8e7dbee349714559c1d40cbac30fc4"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)",
    "x-api-key": API_KEY,
}

THEATER_NAME = "BIFF"

# Denver timezone offset (MDT = UTC-6)
DENVER_OFFSET = timedelta(hours=-6)

# Skip non-movie events (panels, parties, etc.)
SKIP_WORDS = ["panel", "reception", "party", "gala", "awards", "ceremony", "brunch",
              "workshop", "masterclass", "industry", "networking"]


def scrape():
    """Return a list of showtime dicts for BIFF screenings."""
    print(f"[BIFF] Fetching events from Eventive API...")

    try:
        events_resp = requests.get(
            f"{API_BASE}/event_buckets/{BUCKET_ID}/events",
            headers=HEADERS,
            timeout=30,
        )
        events_resp.raise_for_status()
        events_data = events_resp.json()
    except Exception as e:
        print(f"[BIFF] Error fetching events: {e}")
        return []

    events = events_data.get("events", [])
    print(f"[BIFF] Found {len(events)} events")

    results = []
    for event in events:
        try:
            parsed = _parse_event(event)
            results.extend(parsed)
        except Exception as e:
            print(f"[BIFF] Error parsing event '{event.get('name', '?')}': {e}")

    print(f"[BIFF] Scraped {len(results)} showings")
    return results


def _parse_event(event):
    """Parse a single Eventive event into one or more showtime dicts.

    An event can contain multiple films (e.g. shorts blocks), so we return
    a list. If the event has no embedded films, we use the event name as title.
    """
    # Skip virtual-only events
    if event.get("is_virtual") and not event.get("venue"):
        return []

    # Skip non-movie events
    event_name = event.get("name", "")
    if any(skip in event_name.lower() for skip in SKIP_WORDS):
        return []

    # Parse start time
    start_time = event.get("start_time")
    if not start_time:
        return []

    try:
        dt_utc = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        dt_local = dt_utc + DENVER_OFFSET
        date_iso = dt_local.strftime("%Y-%m-%d")
        time_formatted = dt_local.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return []

    # Get venue info
    venue = event.get("venue", {})
    venue_name = venue.get("short_name") or venue.get("name", "")

    # Build ticket URL
    event_id = event.get("id", "")
    ticket_url = f"https://2026biff.eventive.org/schedule/{event_id}"

    # Get films from this event
    films = event.get("films", [])

    if not films:
        # No embedded film data, use event name as title
        # Strip program codes like "CEN1-01 " from the name
        title = _clean_title(event_name)
        if not title:
            return []

        return [{
            "title": title,
            "director": None,
            "year": None,
            "theater": _theater_name(venue_name),
            "date": date_iso,
            "time": time_formatted,
            "url": ticket_url,
            "format": "Standard",
            "special": "BIFF 2026",
        }]

    # One entry per film in the event
    results = []
    for film in films:
        title = film.get("name", "")
        if not title:
            continue

        # Get director from credits
        credits = film.get("credits", {})
        director = credits.get("director") if isinstance(credits, dict) else None

        # Get year
        details = film.get("details", {})
        year = None
        if isinstance(details, dict):
            year_str = details.get("year")
            if year_str:
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    pass

        results.append({
            "title": title,
            "director": director,
            "year": year,
            "theater": _theater_name(venue_name),
            "date": date_iso,
            "time": time_formatted,
            "url": ticket_url,
            "format": "Standard",
            "special": "BIFF 2026",
        })

    return results


def _theater_name(venue_name):
    """Format the theater name with BIFF prefix."""
    if venue_name:
        return f"BIFF @ {venue_name}"
    return THEATER_NAME


def _clean_title(name):
    """Strip program codes and clean up event names."""
    import re
    # Remove program codes like "CEN1-01 ", "BT2-03 ", "FC1-02 "
    cleaned = re.sub(r"^[A-Z]{2,4}\d*-\d+\s+", "", name)
    return cleaned.strip()


if __name__ == "__main__":
    import json
    results = scrape()
    print(json.dumps(results, indent=2))
