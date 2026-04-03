"""
TMDB (The Movie Database) enrichment module.
Searches for movie metadata (poster, synopsis, genres, etc.) and caches results.
Requires TMDB_API_KEY environment variable.
"""

import os
import re
import json
import time
import requests
from pathlib import Path

API_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"
POSTER_SIZE = "w342"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}

# Cache persists in the repo for CI runs
CACHE_PATH = Path(__file__).parent / ".tmdb_cache.json"

# Manual overrides for films TMDB can't match or matches wrong
OVERRIDES_PATH = Path(__file__).parent / "overrides.json"

# TMDB genre ID -> name mapping (these are stable)
GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western",
}


def get_api_key():
    """Get TMDB API key from environment."""
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        print("[TMDB] Warning: TMDB_API_KEY not set. Skipping enrichment.")
    return key


def load_cache():
    """Load cached TMDB results."""
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_cache(cache):
    """Save TMDB cache to disk."""
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        print(f"[TMDB] Warning: could not save cache: {e}")


def load_overrides():
    """Load manual overrides for title -> TMDB data mapping.

    Format: {"title_lowercase": {"year": 1966, "director": "Vera Chytilova", "genres": "Comedy, Drama"}}
    Fields in overrides take priority over TMDB results.
    """
    if OVERRIDES_PATH.exists():
        try:
            with open(OVERRIDES_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def normalize_title(title):
    """Normalize a movie title for TMDB search."""
    t = title.strip()
    # Remove year in parentheses: "The Bride! (2026)" -> "The Bride!"
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", t)
    # Remove common suffixes
    t = re.sub(r"\s*\|\s*Oscars?.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\d+(?:st|nd|rd|th)\s+Anniversary\s*$", "", t, flags=re.IGNORECASE)
    # Remove trailing punctuation that might confuse search
    t = re.sub(r"[!?]+$", "", t).strip()
    # Remove theater-specific prefixes
    t = re.sub(r"^MEMBERS\s+ONLY\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Staff Pick:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Sie/Saw:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Members\s+Sneak\s+Preview\s*[-\u2013]\s*", "", t, flags=re.IGNORECASE)
    # Remove format suffixes like "(Subtitled)" or "(IMAX)"
    t = re.sub(r"\s*\((?:Subtitled|IMAX|3D|Dolby|35mm|70mm)\)\s*$", "", t, flags=re.IGNORECASE)
    # Remove "3D" suffix
    t = re.sub(r"\s+3D\s*$", "", t, flags=re.IGNORECASE)
    return t.strip()


def _resolve_genres(genre_ids):
    """Convert TMDB genre IDs to comma-separated names."""
    names = [GENRE_MAP.get(gid) for gid in (genre_ids or [])]
    return ", ".join(n for n in names if n)


def enrich_movies(movies):
    """Add TMDB metadata to a list of movie dicts.

    Modifies movies in-place, adding:
    - poster_url, synopsis, genres, tmdb_id, year (if missing), director
    """
    api_key = get_api_key()
    if not api_key:
        return

    cache = load_cache()
    overrides = load_overrides()

    # Collect unique titles with any existing year hint from scrapers
    title_years = {}
    for m in movies:
        t = m["title"]
        if t not in title_years and m.get("year"):
            title_years[t] = m["year"]

    unique_titles = set(m["title"] for m in movies)
    print(f"[TMDB] Enriching {len(unique_titles)} unique titles...")

    results_map = {}
    lookups = 0
    cache_hits = 0

    for title in sorted(unique_titles):
        normalized = normalize_title(title)
        cache_key = normalized.lower()

        if cache_key in cache:
            results_map[title] = cache[cache_key]
            cache_hits += 1
            continue

        # Search TMDB with year hint if available
        year_hint = title_years.get(title)
        tmdb_data = _search_movie(api_key, normalized, title, year_hint)
        cache[cache_key] = tmdb_data
        results_map[title] = tmdb_data
        lookups += 1

        if lookups % 30 == 0:
            time.sleep(1)

    print(f"[TMDB] {cache_hits} cache hits, {lookups} API lookups")

    # Apply results to all movies
    enriched = 0
    for m in movies:
        tmdb = results_map.get(m["title"], {})
        override = overrides.get(m["title"].lower(), {})

        # Poster
        if tmdb.get("poster_path"):
            m["poster_url"] = f"{IMAGE_BASE}/{POSTER_SIZE}{tmdb['poster_path']}"
            enriched += 1
        else:
            m["poster_url"] = None

        # Synopsis
        m["synopsis"] = tmdb.get("overview", "")

        # Genres (from TMDB or override)
        m["genres"] = override.get("genres") or tmdb.get("genres", "")

        # TMDB ID
        m["tmdb_id"] = tmdb.get("id")

        # Year: override > scraper > TMDB
        if override.get("year"):
            m["year"] = override["year"]
        elif not m.get("year") and tmdb.get("release_year"):
            m["year"] = tmdb["release_year"]

        # Director: override > scraper > TMDB (TMDB doesn't have director in search,
        # but overrides can fill it)
        if override.get("director") and not m.get("director"):
            m["director"] = override["director"]

        # Rating (TMDB vote_average, 0-10 scale)
        if tmdb.get("vote_average") and tmdb["vote_average"] > 0:
            m["rating"] = round(tmdb["vote_average"], 1)
        else:
            m["rating"] = None

    print(f"[TMDB] Enriched {enriched}/{len(movies)} showings with posters")

    # Fetch details (runtime, director) for movies with TMDB IDs
    _fetch_details(api_key, movies, cache)

    save_cache(cache)


def _fetch_details(api_key, movies, cache):
    """Fetch runtime and director from TMDB movie details API.
    Uses a detail cache keyed by TMDB ID to avoid re-fetching.
    """
    # Collect unique TMDB IDs that need details
    needs_detail = {}
    for m in movies:
        tmdb_id = m.get("tmdb_id")
        if not tmdb_id:
            continue
        detail_key = f"_detail_{tmdb_id}"
        if detail_key in cache:
            detail = cache[detail_key]
        else:
            needs_detail[tmdb_id] = detail_key

    if not needs_detail:
        print(f"[TMDB] All details cached")
    else:
        print(f"[TMDB] Fetching details for {len(needs_detail)} movies...")
        fetched = 0
        for tmdb_id, detail_key in needs_detail.items():
            try:
                resp = requests.get(
                    f"{API_BASE}/movie/{tmdb_id}",
                    params={"api_key": api_key, "append_to_response": "credits"},
                    headers=HEADERS,
                    timeout=10,
                )
                if resp.status_code == 429:
                    time.sleep(2)
                    resp = requests.get(
                        f"{API_BASE}/movie/{tmdb_id}",
                        params={"api_key": api_key, "append_to_response": "credits"},
                        headers=HEADERS,
                        timeout=10,
                    )
                if resp.status_code == 200:
                    d = resp.json()
                    # Extract director from credits
                    director = None
                    for crew in d.get("credits", {}).get("crew", []):
                        if crew.get("job") == "Director":
                            director = crew.get("name")
                            break
                    cache[detail_key] = {
                        "runtime": d.get("runtime"),
                        "director": director,
                        "imdb_id": d.get("imdb_id"),
                    }
                    fetched += 1
                if fetched % 30 == 0:
                    time.sleep(1)
            except Exception as e:
                print(f"[TMDB] Error fetching detail for {tmdb_id}: {e}")

        print(f"[TMDB] Fetched {fetched} movie details")

    # Apply details to movies
    for m in movies:
        tmdb_id = m.get("tmdb_id")
        if not tmdb_id:
            continue
        detail = cache.get(f"_detail_{tmdb_id}", {})
        if detail.get("runtime"):
            m["runtime"] = detail["runtime"]
        if detail.get("director") and not m.get("director"):
            m["director"] = detail["director"]
        if detail.get("imdb_id"):
            m["imdb_id"] = detail["imdb_id"]


def _search_movie(api_key, query, original_title, year_hint=None):
    """Search TMDB for a movie by title. Returns best match data or empty dict."""
    try:
        params = {
            "api_key": api_key,
            "query": query,
            "include_adult": "false",
        }
        if year_hint:
            params["year"] = year_hint

        resp = requests.get(
            f"{API_BASE}/search/movie",
            params=params,
            headers=HEADERS,
            timeout=10,
        )

        if resp.status_code == 429:
            time.sleep(2)
            resp = requests.get(
                f"{API_BASE}/search/movie",
                params=params,
                headers=HEADERS,
                timeout=10,
            )

        if resp.status_code != 200:
            print(f"[TMDB] Search failed for '{query}': HTTP {resp.status_code}")
            return {}

        results = resp.json().get("results", [])

        # If year hint gave no results, retry without it
        if not results and year_hint:
            del params["year"]
            resp = requests.get(
                f"{API_BASE}/search/movie",
                params=params,
                headers=HEADERS,
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])

        if not results:
            print(f"[TMDB] No results for '{query}'")
            return {}

        best = _pick_best_match(results, query, original_title)
        if not best:
            return {}

        release_date = best.get("release_date", "")
        release_year = None
        if release_date and len(release_date) >= 4:
            try:
                release_year = int(release_date[:4])
            except ValueError:
                pass

        return {
            "id": best.get("id"),
            "title": best.get("title"),
            "overview": best.get("overview", ""),
            "poster_path": best.get("poster_path"),
            "release_date": release_date,
            "release_year": release_year,
            "vote_average": best.get("vote_average"),
            "popularity": best.get("popularity"),
            "genres": _resolve_genres(best.get("genre_ids", [])),
        }

    except Exception as e:
        print(f"[TMDB] Error searching '{query}': {e}")
        return {}


def _pick_best_match(results, query, original_title):
    """Pick the best matching result from TMDB search results."""
    query_lower = query.lower().strip()
    original_lower = original_title.lower().strip()

    scored = []
    for r in results[:10]:
        title = r.get("title", "").lower()
        original = r.get("original_title", "").lower()
        score = 0

        # Exact match
        if title == query_lower or title == original_lower:
            score += 100
        elif original == query_lower or original == original_lower:
            score += 90
        # Title starts with query or vice versa
        elif title.startswith(query_lower) or query_lower.startswith(title):
            score += 50
        # Partial match
        elif query_lower in title or title in query_lower:
            score += 30

        # Boost popular results (capped)
        popularity = r.get("popularity", 0)
        score += min(popularity / 10, 20)

        # Boost results with posters
        if r.get("poster_path"):
            score += 10

        # Boost recent films slightly
        release_date = r.get("release_date", "")
        if release_date:
            try:
                year = int(release_date[:4])
                if year >= 2024:
                    score += 8
                elif year >= 2020:
                    score += 5
            except ValueError:
                pass

        if score > 0:
            scored.append((score, r))

    if not scored:
        return results[0] if results else None

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
