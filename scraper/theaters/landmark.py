"""
Landmark Theatres scraper (Mayan Theatre, Denver).
Uses Landmark's internal REST API - no browser automation needed.
API endpoints discovered at landmarktheatres.com/api/gatsby-source-boxofficeapi/
"""

import requests
import json
from datetime import datetime, timedelta

BASE_API = "https://www.landmarktheatres.com/api/gatsby-source-boxofficeapi"

# Landmark Mayan Theatre, Denver
THEATERS = [
    {"id": "X02AK", "name": "Landmark Mayan", "timeZone": "America/Denver"},
]

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}


def scrape():
    """Return a list of showtime dicts for Landmark theaters."""
    results = []
    for theater in THEATERS:
        try:
            theater_results = _scrape_theater(theater)
            results.extend(theater_results)
        except Exception as e:
            print(f"[Landmark] Error scraping {theater['name']}: {e}")
    return results


def _scrape_theater(theater):
    """Scrape showtimes for a single Landmark theater."""
    theater_id = theater["id"]
    theater_name = theater["name"]

    # Get schedule for the next 2 weeks
    now = datetime.now()
    from_date = now.strftime("%Y-%m-%dT07:00:00")
    to_date = (now + timedelta(days=14)).strftime("%Y-%m-%dT07:00:00")

    print(f"[Landmark] Fetching schedule for {theater_name} ({theater_id})")
    schedule_url = f"{BASE_API}/schedule"
    schedule_params = {
        "from": from_date,
        "to": to_date,
        "theaters": json.dumps({"id": theater_id, "timeZone": theater["timeZone"]}, separators=(",", ":")),
    }
    resp = requests.get(schedule_url, params=schedule_params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    schedule_data = resp.json()

    theater_schedule = schedule_data.get(theater_id, {}).get("schedule", {})
    if not theater_schedule:
        print(f"[Landmark] No schedule data for {theater_name}")
        return []

    # Collect all movie IDs
    movie_ids = list(theater_schedule.keys())
    print(f"[Landmark] Found {len(movie_ids)} movies in schedule")

    # Fetch movie details in batches of 10
    movies_map = {}
    for i in range(0, len(movie_ids), 10):
        batch = movie_ids[i:i + 10]
        movies_map.update(_fetch_movies(batch))

    # Build showtime entries
    results = []
    for movie_id, dates in theater_schedule.items():
        movie = movies_map.get(movie_id, {})
        title = movie.get("title", f"Unknown ({movie_id})")

        # Get director from the movie details
        director = None
        directors_data = movie.get("directors", {})
        if isinstance(directors_data, dict):
            nodes = directors_data.get("nodes", [])
            if nodes:
                director = nodes[0].get("fullName")
        # Fallback: try direction field
        if not director:
            direction = movie.get("direction")
            if direction:
                if isinstance(direction, list):
                    director = direction[0] if direction else None
                elif isinstance(direction, str):
                    director = direction.split(",")[0].strip()

        # Get year from release date
        year = None
        release_date = movie.get("releaseDate")
        if release_date:
            try:
                year = int(release_date[:4])
            except (ValueError, TypeError):
                pass

        for date_str, showtimes in dates.items():
            for st in showtimes:
                if st.get("isExpired"):
                    continue

                starts_at = st.get("startsAt", "")
                if not starts_at:
                    continue

                try:
                    dt = datetime.fromisoformat(starts_at)
                    date_iso = dt.strftime("%Y-%m-%d")
                    time_formatted = dt.strftime("%-I:%M %p")
                except (ValueError, TypeError):
                    continue

                # Detect format from tags
                tags = st.get("tags", [])
                fmt = _detect_format(tags)

                # Build ticket URL
                ticket_url = None
                ticketing = st.get("data", {}).get("ticketing", [])
                for t in ticketing:
                    if t.get("provider") == "default" and t.get("type") == "DESKTOP":
                        urls = t.get("urls", [])
                        if urls:
                            ticket_url = urls[0]
                            break

                if not ticket_url:
                    ticket_url = f"https://www.landmarktheatres.com/denver/mayan-theatre"

                results.append({
                    "title": title,
                    "director": director,
                    "year": year,
                    "theater": theater_name,
                    "date": date_iso,
                    "time": time_formatted,
                    "url": ticket_url,
                    "format": fmt,
                    "special": None,
                })

    print(f"[Landmark] {theater_name}: {len(results)} showings")
    return results


def _fetch_movies(movie_ids):
    """Fetch movie details from the Landmark API."""
    if not movie_ids:
        return {}

    url = f"{BASE_API}/movies"
    params = [("basic", "false"), ("castingLimit", "3")]
    for mid in movie_ids:
        params.append(("ids", mid))

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        movies = resp.json()
        return {m["id"]: m for m in movies}
    except Exception as e:
        print(f"[Landmark] Error fetching movie details: {e}")
        return {}


def _detect_format(tags):
    """Detect screening format from Landmark tags."""
    tag_str = " ".join(tags).lower()

    if "imax" in tag_str:
        return "IMAX"
    if "35mm" in tag_str or "film.35mm" in tag_str:
        return "35mm"
    if "70mm" in tag_str:
        return "70mm"
    if "dolby" in tag_str:
        return "Dolby"
    if "3d" in tag_str:
        return "3D"
    return "Standard"


if __name__ == "__main__":
    results = scrape()
    print(json.dumps(results, indent=2))
