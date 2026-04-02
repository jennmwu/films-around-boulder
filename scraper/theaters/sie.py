"""
SIE FilmCenter (Denver Film) scraper.
Uses Playwright to load the Eventive schedule page and intercept
the API response which requires a frontend token.

Data structure:
- films: list of {id, name, poster_image, ...}
- shows_by_day: {date_str: {film_id: {venue_name: [{id, start_time, start_time_label}]}}}
"""

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta

SCHEDULE_URL = "https://denverfilm.eventive.org/schedule"
THEATER_NAME = "SIE FilmCenter"
EVENT_BUCKET = "5ed7cb60eb909700905eb9e4"

# Denver timezone offset (MDT = UTC-6, MST = UTC-7)
DENVER_OFFSET = timedelta(hours=-6)

# Skip non-movie events
SKIP_WORDS = ["watch party", "trivia", "fundraiser", "gala", "reception", "workshop", "brightest night"]


def scrape():
    """Return a list of showtime dicts for SIE FilmCenter."""
    print(f"[SIE] Loading schedule via Playwright...")
    return asyncio.run(_scrape_async())


async def _scrape_async():
    from playwright.async_api import async_playwright

    upcoming_data = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        async def on_response(response):
            nonlocal upcoming_data
            url = response.url
            if f"event_buckets/{EVENT_BUCKET}/upcoming" in url and response.status == 200:
                try:
                    body = await response.text()
                    upcoming_data = json.loads(body)
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await page.goto(SCHEDULE_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[SIE] Navigation error: {e}")

        await browser.close()

    if not upcoming_data:
        print("[SIE] Could not capture Eventive API response")
        return []

    return _parse_upcoming(upcoming_data)


def _parse_upcoming(data):
    """Parse the Eventive upcoming response into showtime dicts."""
    # Build film ID -> name/metadata map
    films = data.get("films", [])
    film_map = {}
    for f in films:
        film_map[f["id"]] = {
            "name": f.get("name", ""),
            "poster": f.get("poster_image") or f.get("cover_image"),
            "description": f.get("short_description", ""),
        }

    print(f"[SIE] Found {len(films)} films")

    # Parse shows_by_day
    # Structure: {date: {film_id: {venue_name: [screening]}}}
    shows_by_day = data.get("shows_by_day", {})
    results = []

    for day_str, day_films in shows_by_day.items():
        if not isinstance(day_films, dict):
            continue

        for film_id, venues in day_films.items():
            if not isinstance(venues, dict):
                continue

            film_info = film_map.get(film_id, {})
            title = film_info.get("name", "")

            if not title:
                continue

            # Skip non-movie events
            if any(skip in title.lower() for skip in SKIP_WORDS):
                continue

            for venue_name, screenings in venues.items():
                if not isinstance(screenings, list):
                    continue

                for sc in screenings:
                    start_time = sc.get("start_time")
                    start_label = sc.get("start_time_label", "")
                    screening_id = sc.get("id", "")

                    if not start_time:
                        continue

                    # Convert UTC start_time to Denver local time
                    try:
                        dt_utc = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                        dt_local = dt_utc + DENVER_OFFSET
                        date_iso = dt_local.strftime("%Y-%m-%d")
                        time_formatted = dt_local.strftime("%-I:%M %p")
                    except (ValueError, TypeError):
                        continue

                    # Build ticket URL
                    ticket_url = f"https://denverfilm.eventive.org/schedule/{screening_id}"

                    results.append({
                        "title": title,
                        "director": None,
                        "year": None,
                        "theater": THEATER_NAME,
                        "date": date_iso,
                        "time": time_formatted,
                        "url": ticket_url,
                        "format": "Standard",
                        "special": None,
                    })

    print(f"[SIE] Scraped {len(results)} showings")
    return results


if __name__ == "__main__":
    results = scrape()
    print(json.dumps(results, indent=2))
