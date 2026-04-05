"""
FAB Movie Tracker - Main scraper orchestrator.
Runs all theater scrapers, combines results, and writes docs/movies.json.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Add scraper dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from theaters import ifs, cinemark, landmark, alamo, dairy, sie, biff, amc
import tmdb
import mdblist


SCRAPERS = [
    ("IFS", ifs.scrape),
    ("Cinemark", cinemark.scrape),
    ("Landmark", landmark.scrape),
    ("Alamo", alamo.scrape),
    ("Dairy", dairy.scrape),
    ("SIE", sie.scrape),
    ("BIFF", biff.scrape),
    # ("Regal", regal.scrape),  # TODO: Cloudflare blocks direct API; Playwright too slow for CI
    # ("AMC", amc.scrape),  # TODO: slow Playwright scraper, needs optimization
]

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "docs", "movies.json"
)


def _run_one(name, scrape_fn):
    """Run a single scraper and return (name, results, elapsed)."""
    t0 = time.time()
    try:
        results = scrape_fn()
        elapsed = time.time() - t0
        print(f"[{name}] {len(results)} showings in {elapsed:.1f}s")
        return results
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[{name}] ERROR after {elapsed:.1f}s: {e}")
        return []


def run():
    t_start = time.time()
    all_movies = []

    print(f"Running {len(SCRAPERS)} scrapers in parallel...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_run_one, name, fn): name for name, fn in SCRAPERS}
        for future in as_completed(futures):
            results = future.result()
            all_movies.extend(results)

    print(f"\nAll scrapers done in {time.time() - t_start:.1f}s ({len(all_movies)} total showings)")

    # Filter to today through 45 days out
    # IFS and SIE publish full semester schedules far in advance;
    # multiplexes (Cinemark, Regal, Alamo) self-limit to ~14 days so
    # extending the window here doesn't add noise for them.
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d")
    all_movies = [m for m in all_movies if today <= m["date"] <= cutoff]

    # Sort by date, then time (convert to 24h for proper ordering)
    def sort_key(m):
        try:
            t = datetime.strptime(m["time"], "%I:%M %p")
            time_24h = t.strftime("%H:%M")
        except ValueError:
            time_24h = m["time"]
        return (m["date"], time_24h, m["title"])

    all_movies.sort(key=sort_key)

    # Normalize titles for consistency
    for m in all_movies:
        m["title"] = _normalize_title(m["title"])

    # Enrich with TMDB metadata (posters, synopsis, etc.)
    try:
        tmdb.enrich_movies(all_movies)
    except Exception as e:
        print(f"WARNING: TMDB enrichment failed: {e}")

    # Apply manual overrides (works even without TMDB key)
    _apply_overrides(all_movies)

    # Enrich with MDbList ratings (IMDb, RT, Letterboxd)
    try:
        mdblist.enrich_ratings(all_movies)
    except Exception as e:
        print(f"WARNING: MDbList enrichment failed: {e}")

    # Categorize movies
    _categorize_movies(all_movies)

    # Build output
    output = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "movies": all_movies,
    }

    # Write to docs/movies.json
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Done! Wrote {len(all_movies)} showings to {OUTPUT_PATH}")
    print(f"{'='*50}")


OVERRIDES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "overrides.json"
)


def _apply_overrides(movies):
    """Apply manual overrides for year, director, genres from overrides.json."""
    if not os.path.exists(OVERRIDES_PATH):
        return
    try:
        with open(OVERRIDES_PATH) as f:
            overrides = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    applied = 0
    for m in movies:
        ov = overrides.get(m["title"].lower(), {})
        if not ov:
            continue
        # Overrides always win (they're manual corrections)
        if ov.get("year"):
            m["year"] = ov["year"]
        if ov.get("director"):
            m["director"] = ov["director"]
        if ov.get("genres"):
            m["genres"] = ov["genres"]
        applied += 1

    if applied:
        print(f"Overrides applied to {applied} showings")


INDIE_VENUES = {
    "Boulder IFS", "SIE FilmCenter", "Dairy Arts Center", "Landmark Mayan",
}

WIDE_VENUES = {
    "Cinemark Boulder", "Alamo Sloans Lake", "Alamo Westminster",
    "Regal Longmont", "AMC Flatiron Crossing", "AMC Westminster",
}


def _categorize_movies(movies):
    """Assign categories (plural) to each movie. A film can belong to multiple.

    Categories: Festival, New Release, Independent, Back in Theaters, Classic
    """
    current_year = datetime.now().year

    # First pass: group by title to see which venues each film plays at
    title_venues = {}
    title_specials = {}
    title_year = {}
    for m in movies:
        t = m["title"]
        if t not in title_venues:
            title_venues[t] = set()
            title_specials[t] = set()
            title_year[t] = None
        title_venues[t].add(m["theater"])
        if m.get("special"):
            title_specials[t].add(m["special"])
        if m.get("year") and not title_year[t]:
            title_year[t] = m["year"]

    # Second pass: assign categories (non-exclusive)
    title_categories = {}
    for title in title_venues:
        venues = title_venues[title]
        specials = title_specials[title]
        year = title_year[title]
        cats = []

        is_biff = any("BIFF" in s for s in specials)
        is_indie_only = all(
            v in INDIE_VENUES or v.startswith("BIFF") for v in venues
        )

        if is_biff:
            cats.append("Festival")
        if is_indie_only:
            cats.append("Independent")
        if year:
            age = current_year - year
            if age >= 20:
                cats.append("Classic")
            elif age >= 2:
                cats.append("Back in Theaters")
            else:
                cats.append("New Release")
        else:
            # No year data: default based on venue
            if not is_indie_only and not is_biff:
                cats.append("New Release")

        if not cats:
            cats.append("New Release")

        title_categories[title] = cats

    # Apply to all movies
    cat_counts = {}
    for m in movies:
        m["categories"] = title_categories.get(m["title"], ["New Release"])
        for c in m["categories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1

    print(f"Categories: {cat_counts}")


def _normalize_title(title):
    """Clean up movie titles for consistency across theaters."""
    import re

    title = title.strip()
    title = " ".join(title.split())

    # Strip "X presents: Film Title" → "Film Title"
    # Catches: "Cinema Youth Advisory Board presents: ..."
    #          "The North Face Presents: ..."
    title = re.sub(r'^.+?\bpresents:\s+', '', title, flags=re.IGNORECASE)

    # Strip trailing qualifiers added by theaters
    # e.g. "Over Your Dead Body - Early Access", "Faces Of Death - Early Access"
    title = re.sub(r'\s*[-–]\s*(Early Access|Sneak Peek|Members Only Screening|Fan Event|Special Screening|Advance Screening)$', '', title, flags=re.IGNORECASE)

    return title.strip()


if __name__ == "__main__":
    run()
