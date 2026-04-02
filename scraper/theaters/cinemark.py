"""
Cinemark Century Boulder scraper.
Parses the server-rendered HTML for today's showtimes.
Showtime links contain ISO datetimes in the URL, making time extraction reliable.
Theater ID: 492
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse, parse_qs

THEATER_URL = "https://www.cinemark.com/theatres/co-boulder/century-boulder"
THEATER_ID = "492"
THEATER_NAME = "Cinemark Boulder"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}


def scrape():
    """Return a list of showtime dicts for Cinemark Century Boulder."""
    print(f"[Cinemark] Fetching {THEATER_URL}")
    resp = requests.get(THEATER_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = _parse_showtimes(soup)
    print(f"[Cinemark] Scraped {len(results)} showings")
    return results


def _parse_showtimes(soup):
    """Extract movie showtimes from the page HTML."""
    results = []

    # Find all ticket links - they contain the showtime data
    ticket_links = soup.find_all("a", href=re.compile(r"TicketSeatMap"))

    # Group by movie: walk up from each ticket link to find the parent movie block
    # and extract the movie title
    movies_seen = {}  # movie_slug -> title

    for link in ticket_links:
        href = link.get("href", "")
        params = _parse_ticket_url(href)
        if not params:
            continue

        showtime_iso = params.get("showtime")
        if not showtime_iso:
            continue

        # Parse the ISO datetime from the ticket URL
        try:
            dt = datetime.fromisoformat(showtime_iso)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%-I:%M %p")
        except (ValueError, TypeError):
            continue

        # Find the movie title by walking up to find the nearest h3
        title = _find_movie_title(link)
        if not title:
            continue

        # Build the full ticket URL
        ticket_url = f"https://www.cinemark.com{href}" if href.startswith("/") else href

        # Check the link text and nearby elements for format info
        fmt = _detect_format(link)

        results.append({
            "title": title,
            "director": None,  # Cinemark pages don't show director
            "year": None,
            "theater": THEATER_NAME,
            "date": date_str,
            "time": time_str,
            "url": ticket_url,
            "format": fmt,
            "special": None,
        })

    return results


def _parse_ticket_url(href):
    """Extract parameters from a Cinemark ticket URL."""
    try:
        # URL format: /TicketSeatMap/?TheaterId=492&ShowtimeId=...&Showtime=2026-03-14T16:40:00
        if "?" not in href:
            return None
        query = href.split("?", 1)[1]
        params = {}
        for part in query.split("&"):
            if "=" in part:
                key, val = part.split("=", 1)
                params[key.lower()] = val
        return params
    except Exception:
        return None


def _find_movie_title(element):
    """Walk up the DOM from a showtime link to find the movie title (h3 tag)."""
    # Walk up through parents looking for an h3 sibling or ancestor's h3
    current = element
    for _ in range(10):  # limit depth
        current = current.parent
        if current is None:
            break
        h3 = current.find("h3")
        if h3:
            # Get the text, cleaning up any nested elements
            title_link = h3.find("a")
            if title_link:
                return title_link.get_text(strip=True)
            return h3.get_text(strip=True)
    return None


def _detect_format(link):
    """Check for special format indicators near the showtime link."""
    # Check the link text and surrounding text
    text = link.get_text(strip=True).lower()
    parent_text = link.parent.get_text(" ", strip=True).lower() if link.parent else ""

    if "imax" in text or "imax" in parent_text:
        return "IMAX"
    if "3d" in text or "reald" in parent_text:
        return "3D"
    if "dolby" in text or "dolby" in parent_text:
        return "Dolby"
    if "xd" in text or "cinemark xd" in parent_text:
        return "XD"
    return "Standard"


if __name__ == "__main__":
    import json
    results = scrape()
    print(json.dumps(results, indent=2))
