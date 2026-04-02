"""
Cinemark Century Boulder scraper.
Uses the Umbraco surface controller API to fetch showtimes for each date.
Supports future dates (up to 14 days out).
Theater ID: 492
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime

SHOWTIME_API = "https://www.cinemark.com/umbraco/surface/Showtimes/GetByTheaterId"
THEATER_ID = "492"
THEATER_NAME = "Cinemark Boulder"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}


def scrape():
    """Return a list of showtime dicts for Cinemark Century Boulder, 14 days out."""
    all_results = []
    today = date.today()

    for offset in range(14):
        show_date = today + timedelta(days=offset)
        date_str = show_date.isoformat()

        print(f"[Cinemark] Fetching {date_str}")
        try:
            url = f"{SHOWTIME_API}?theaterId={THEATER_ID}&showDate={date_str}"
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            results = _parse_showtimes(soup)
            all_results.extend(results)
        except Exception as e:
            print(f"[Cinemark] Error fetching {date_str}: {e}")

        if offset > 0:
            time.sleep(0.5)

    print(f"[Cinemark] Scraped {len(all_results)} showings across 14 days")
    return all_results


def _parse_showtimes(soup):
    """Extract movie showtimes from the HTML fragment."""
    results = []

    ticket_links = soup.find_all("a", href=re.compile(r"TicketSeatMap"))

    for link in ticket_links:
        href = link.get("href", "")
        params = _parse_ticket_url(href)
        if not params:
            continue

        showtime_iso = params.get("showtime")
        if not showtime_iso:
            continue

        try:
            dt = datetime.fromisoformat(showtime_iso)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%-I:%M %p")
        except (ValueError, TypeError):
            continue

        title = _find_movie_title(link)
        if not title:
            continue

        ticket_url = f"https://www.cinemark.com{href}" if href.startswith("/") else href
        fmt = _detect_format(link)

        results.append({
            "title": title,
            "director": None,
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
    """Walk up the DOM from a showtime link to find the movie title."""
    current = element
    for _ in range(10):
        current = current.parent
        if current is None:
            break
        # Check for title in img alt text (API returns poster images with "Title Poster" alt)
        img = current.find("img", alt=True)
        if img and img["alt"].endswith(" Poster"):
            return img["alt"][:-7].strip()
        # Fallback: h3 tag
        h3 = current.find("h3")
        if h3:
            title_link = h3.find("a")
            if title_link:
                return title_link.get_text(strip=True)
            return h3.get_text(strip=True)
    return None


def _detect_format(link):
    """Check for special format indicators on the showtime link."""
    # Prefer explicit data attribute from the API
    fmt = link.get("data-print-type-name", "")
    if fmt:
        if "3D" in fmt or "RealD" in fmt:
            return "3D"
        if "IMAX" in fmt:
            return "IMAX"
        if "Dolby" in fmt:
            return "Dolby"
        if "XD" in fmt:
            return "XD"

    # Fallback: check surrounding text
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
