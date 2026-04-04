"""
Alamo Drafthouse scraper (Denver area: Sloans Lake, Westminster, Littleton).
Uses Alamo's internal REST API - no browser automation needed.
API endpoints discovered at drafthouse.com/s/mother/v2/
"""

import requests
import json
from datetime import datetime

SCHEDULE_API = "https://drafthouse.com/s/mother/v2/schedule/venue"

VENUES = [
    {"slug": "sloans-lake", "name": "Alamo Sloans Lake"},
    {"slug": "westminster", "name": "Alamo Westminster"},
    {"slug": "littleton", "name": "Alamo Littleton"},
]

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}

# Skip non-movie presentations
SKIP_TYPES = {"party", "brunch", "feast", "karaoke", "singalong", "trivia", "bingo"}


def scrape():
    """Return a list of showtime dicts for all Denver Alamo Drafthouse locations."""
    results = []
    for venue in VENUES:
        try:
            venue_results = _scrape_venue(venue)
            results.extend(venue_results)
        except Exception as e:
            print(f"[Alamo] Error scraping {venue['name']}: {e}")
    return results


def _scrape_venue(venue):
    """Scrape showtimes for a single Alamo Drafthouse venue."""
    slug = venue["slug"]
    name = venue["name"]

    print(f"[Alamo] Fetching schedule for {name}")
    url = f"{SCHEDULE_API}/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", {})

    presentations = data.get("presentations", [])
    sessions = data.get("sessions", [])

    print(f"[Alamo] {name}: {len(presentations)} presentations, {len(sessions)} sessions")

    # Build a map from presentation slug to show info
    pres_map = {}
    for p in presentations:
        pres_slug = p.get("slug")
        show = p.get("show", {})
        pres_map[pres_slug] = {
            "title": show.get("title", ""),
            "certification": show.get("certification"),
            "poster": _get_poster(show),
            "slug": show.get("slug"),
            "format_slugs": p.get("formatSlugs", []),
            "attributes": p.get("presentationAttributeSlugs", []),
        }

    # Process sessions
    results = []
    for s in sessions:
        if s.get("status") != "ONSALE" and s.get("status") != "ON_SALE":
            # Also allow sessions that are nearly sold out
            if s.get("status") not in ("ALMOST_SOLD_OUT", "ALMOSTSOLDOUT"):
                continue

        pres_slug = s.get("presentationSlug")
        pres = pres_map.get(pres_slug, {})
        title = pres.get("title", "")

        if not title:
            continue

        # Skip non-movie events
        slug_lower = (pres_slug or "").lower()
        title_lower = title.lower()
        if any(skip in slug_lower or skip in title_lower for skip in SKIP_TYPES):
            continue

        # Parse showtime
        show_time_clt = s.get("showTimeClt", "")
        if not show_time_clt:
            continue

        try:
            dt = datetime.fromisoformat(show_time_clt)
            date_iso = dt.strftime("%Y-%m-%d")
            time_formatted = dt.strftime("%-I:%M %p")
        except (ValueError, TypeError):
            continue

        # Detect format
        fmt = _detect_format(s, pres)

        # Build ticket URL
        session_id = s.get("sessionId", "")
        ticket_url = f"https://drafthouse.com/denver/show/{pres.get('slug', pres_slug)}"

        results.append({
            "title": title,
            "director": None,  # Alamo API doesn't include director
            "year": None,
            "theater": name,
            "date": date_iso,
            "time": time_formatted,
            "url": ticket_url,
            "format": fmt,
            "special": _detect_special(pres),
        })

    print(f"[Alamo] {name}: {len(results)} showings")
    return results


def _get_poster(show):
    """Extract poster URL from show data."""
    posters = show.get("posterImages", [])
    if posters:
        return posters[0].get("uri")
    return None


def _detect_format(session, pres):
    """Detect screening format from session and presentation data."""
    attrs = session.get("sessionAttributeSlugs", [])
    format_slugs = pres.get("format_slugs", [])
    all_slugs = " ".join(attrs + format_slugs).lower()

    if "imax" in all_slugs:
        return "IMAX"
    if "35mm" in all_slugs:
        return "35mm"
    if "70mm" in all_slugs:
        return "70mm"
    if "dolby" in all_slugs:
        return "Dolby"
    if "3d" in all_slugs:
        return "3D"
    return "Standard"


def _detect_special(pres):
    """Detect special event attributes."""
    attrs = pres.get("attributes", [])
    attrs_str = " ".join(attrs).lower()

    if "terror-tuesday" in attrs_str or "weird-wednesday" in attrs_str:
        return "Special Screening"
    if "movie-party" in attrs_str:
        return "Movie Party"
    if "brunch" in attrs_str:
        return "Brunch"
    return None


if __name__ == "__main__":
    results = scrape()
    print(json.dumps(results, indent=2))
