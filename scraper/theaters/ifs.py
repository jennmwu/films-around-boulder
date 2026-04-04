"""
Boulder International Film Series (IFS) scraper.
Scrapes the schedule page for event links, then each detail page for date/time/venue.
IFS is a simple server-rendered PHP site - no JS needed.
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://internationalfilmseries.com"
SCHEDULE_URL = f"{BASE_URL}/schedule.php"
THEATER_NAME = "Boulder IFS"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}


def scrape():
    """Return a list of showtime dicts for IFS."""
    print(f"[IFS] Fetching schedule from {SCHEDULE_URL}")
    resp = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    event_links = _extract_event_links(soup)
    print(f"[IFS] Found {len(event_links)} events on schedule page")

    results = []
    for url in event_links:
        try:
            detail = _scrape_event_detail(url)
            if detail:
                results.append(detail)
        except Exception as e:
            print(f"[IFS] Error scraping {url}: {e}")

    print(f"[IFS] Scraped {len(results)} showings")
    return results


def _extract_event_links(soup):
    """Pull all event detail links from the schedule page."""
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Event links look like /spring-2026/11477/redline
        if re.match(r"/(spring|fall|summer)-\d{4}/\d+/", href):
            full_url = BASE_URL + href if href.startswith("/") else href
            if full_url not in seen:
                seen.add(full_url)
                links.append(full_url)

    return links


def _scrape_event_detail(url):
    """Scrape a single event detail page for showtime info."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text(" ", strip=True)

    # Title is in an h4 tag
    title_tag = soup.find("h4")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)

    # Clean up title prefixes
    title = re.sub(r"^\(SOLD OUT!\)\s*", "", title)
    title = re.sub(r"^\(CANCELLED\)\s*", "", title)

    # Skip non-movie events (parties, receptions, etc.)
    skip_words = ["reception", "party", "fundraiser", "gala"]
    if any(w in title.lower() for w in skip_words):
        return None

    # Date/time pattern: "Mon March 23, 7:30 PM" or "Fri March 27, 10:30 PM"
    date_match = re.search(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+"
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2})"
        r",?\s*(\d{1,2}:\d{2}\s*[APap][Mm])",
        text
    )
    if not date_match:
        return None

    date_str = date_match.group(1)  # "March 23"
    time_str = date_match.group(2).strip()  # "7:30 PM"

    # Parse date - assume current year context
    current_year = datetime.now().year
    try:
        parsed_date = datetime.strptime(f"{date_str} {current_year}", "%B %d %Y")
        date_iso = parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return None

    # Format time consistently
    try:
        parsed_time = datetime.strptime(time_str, "%I:%M %p")
        time_formatted = parsed_time.strftime("%-I:%M %p")
    except ValueError:
        time_formatted = time_str

    # Check for special attributes -- IFS uses plain text like "Lulu Wang in person!"
    # Try to extract the person's name so we can show "Filmmaker Q&A: Lulu Wang"
    special = None
    text_lower = text.lower()
    if (
        "in person" in text_lower
        or "filmmaker in attendance" in text_lower
        or "director in attendance" in text_lower
        or re.search(r"q\s*&\s*a", text_lower)
    ):
        # Try to extract "Name in person" — look for up to 5 capitalized words before "in person"
        # then strip film title words and role words to isolate the actual person's name
        person_match = re.search(
            r'([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){0,4})\s+in\s+(?:person|attendance)',
            text
        )
        ROLE_WORDS = {
            'Director', 'Directors', 'Filmmaker', 'Filmmakers', 'Editor', 'Editors',
            'Producer', 'Producers', 'Writer', 'Writers', 'Actor', 'Actress', 'Archivist',
            'Cinematographer', 'Composer', 'Screenwriter',
        }
        person_name = None
        if person_match:
            title_words = set(re.sub(r"[^a-zA-Z\s]", "", title).split())
            parts = person_match.group(1).split()
            while parts and (parts[0] in ROLE_WORDS or parts[0] in title_words):
                parts.pop(0)
            if parts and len(parts) <= 4:
                person_name = ' '.join(parts)
        if person_name:
            special = f"Filmmaker Q&A: {person_name}"
        else:
            special = "Filmmaker Q&A"
    elif "free admission" in text_lower or "free screening" in text_lower:
        special = "Free Admission"

    if not special:
        for img in soup.find_all("img", alt=True):
            alt = img.get("alt", "").lower()
            if "filmmaker" in alt or "q & a" in alt or "q&a" in alt:
                special = "Filmmaker Q&A"
            elif "free" in alt:
                special = "Free Admission"

    # Check for format - look specifically in the metadata line, not the whole page
    # IFS metadata format: "Country, Year, in Language, Runtime min"
    fmt = "Standard"
    meta_match = re.search(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}"
        r",?\s*\d{1,2}:\d{2}\s*[APap][Mm]\s*,\s*(.+?)(?:Director|Cast|$)",
        text, re.DOTALL
    )
    if meta_match:
        meta_text = meta_match.group(1)
        if "35mm" in meta_text.lower() or "35 mm" in meta_text.lower():
            fmt = "35mm"
        elif "16mm" in meta_text.lower():
            fmt = "16mm"

    # Also check CSS classes on schedule page links for format hints
    # (the schedule page marks 35mm films with a class)

    # Director - be more precise, stop at common delimiters
    director = None
    dir_match = re.search(
        r"Director[s]?:\s*([^,\n]+?)(?:\s*,\s*(?:Screenplay|Writer|Story|Cast|Producer|Novel|Musical|Book|Script|Adaptation|Characters|Original|Director:|remind)|\s*$)",
        text
    )
    if dir_match:
        director = dir_match.group(1).strip()
        # Clean up any trailing junk
        director = re.sub(r"\s*(recommend|remind|save|<|>|IFS tickets).*", "", director).strip()
        if len(director) > 80 or not director:
            director = None

    # Year - try multiple patterns
    year = None
    # Pattern: "Country, YYYY, in Language" or "Country, YYYY, Runtime"
    year_match = re.search(r"(?:,\s*|^)(\d{4})(?:\s*,|\s*min)", text)
    if year_match:
        y = int(year_match.group(1))
        if 1900 <= y <= 2030:
            year = y

    return {
        "title": title,
        "director": director,
        "year": year,
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
