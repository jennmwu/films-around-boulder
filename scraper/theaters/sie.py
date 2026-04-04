"""
SIE FilmCenter (Denver Film) scraper.
Uses the Eventive REST API directly -- no browser automation needed.

Auth: HTTP Basic with a public token extracted from the Eventive frontend.
The /events endpoint returns the full archive; we filter to upcoming only.
"""

import requests
from datetime import datetime, timezone, timedelta
import re

API_BASE = "https://api.eventive.org"
BUCKET_ID = "5ed7cb60eb909700905eb9e4"
# Public Basic auth token used by the Eventive frontend for denverfilm.eventive.org
AUTH_TOKEN = "Mjg1ZjU4N2I4M2U2YWIzMjZlNzM3ZTAwZDYyY2EzNzg6"

THEATER_NAME = "SIE FilmCenter"

# Denver timezone offset (MDT = UTC-6, MST = UTC-7)
DENVER_OFFSET = timedelta(hours=-6)

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)",
    "Authorization": f"Basic {AUTH_TOKEN}",
}

# Skip non-movie events
SKIP_WORDS = [
    "watch party", "trivia", "fundraiser", "gala", "reception", "workshop",
    "brightest night", "drag race", "otaku tuesdays", "networking",
    "panel", "industry", "masterclass",
]

# Prefixes to strip from film/event titles
TITLE_PREFIXES = [
    r"^Sie/Saw:\s*",
    r"^MEMBERS ONLY Staff Pick:\s*",
    r"^Members Only Staff Pick:\s*",
    r"^Staff Pick:\s*",
]


def scrape():
    """Return a list of showtime dicts for SIE FilmCenter."""
    print(f"[SIE] Fetching events from Eventive REST API...")

    try:
        resp = requests.get(
            f"{API_BASE}/event_buckets/{BUCKET_ID}/events",
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"[SIE] Error fetching events: {e}")
        return []

    print(f"[SIE] Found {len(events)} total events in archive")

    today_utc = datetime.now(timezone.utc)
    results = []

    for event in events:
        try:
            parsed = _parse_event(event, today_utc)
            results.extend(parsed)
        except Exception as e:
            print(f"[SIE] Error parsing event '{event.get('name', '?')}': {e}")

    print(f"[SIE] Scraped {len(results)} upcoming showings")
    return results


def _parse_event(event, today_utc):
    """Parse a single Eventive event into one or more showtime dicts."""
    # Filter to upcoming only
    start_time = event.get("start_time")
    if not start_time:
        return []

    try:
        dt_utc = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if dt_utc < today_utc:
            return []
        dt_local = dt_utc + DENVER_OFFSET
        date_iso = dt_local.strftime("%Y-%m-%d")
        time_formatted = dt_local.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return []

    # Skip virtual-only events
    if event.get("is_virtual") and not event.get("venue"):
        return []

    event_name = event.get("name", "")

    # Skip non-movie events
    if any(skip in event_name.lower() for skip in SKIP_WORDS):
        return []

    # Build ticket URL
    event_id = event.get("id", "")
    ticket_url = f"https://denverfilm.eventive.org/schedule/{event_id}"

    # Detect special attribute from title
    special = None
    if "members only" in event_name.lower() or "member sneak" in event_name.lower():
        special = "Members Only"

    # Use embedded film data if available
    films = event.get("films", [])

    if films:
        results = []
        for film in films:
            title = _clean_title(film.get("name", ""))
            if not title:
                continue

            credits = film.get("credits", {}) or {}
            details = film.get("details", {}) or {}

            director = credits.get("director") or None
            year = None
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
                "theater": THEATER_NAME,
                "date": date_iso,
                "time": time_formatted,
                "url": ticket_url,
                "format": "Standard",
                "special": special,
            })
        return results

    # No embedded film -- use event name as title
    title = _clean_title(event_name)
    if not title:
        return []

    return [{
        "title": title,
        "director": None,
        "year": None,
        "theater": THEATER_NAME,
        "date": date_iso,
        "time": time_formatted,
        "url": ticket_url,
        "format": "Standard",
        "special": special,
    }]


def _clean_title(name):
    """Strip program prefixes (Sie/Saw:, Members Only Staff Pick:, etc.)."""
    for pattern in TITLE_PREFIXES:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return name.strip()


if __name__ == "__main__":
    import json
    results = scrape()
    print(json.dumps(results, indent=2))
