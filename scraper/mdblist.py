"""
MDbList enrichment module.
Fetches IMDb, Rotten Tomatoes, and Letterboxd ratings.
Requires MDBLIST_API_KEY environment variable.
"""

import os
import json
import time
import requests
from pathlib import Path

API_BASE = "https://api.mdblist.com"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}

CACHE_PATH = Path(__file__).parent / ".mdblist_cache.json"


def get_api_key():
    key = os.environ.get("MDBLIST_API_KEY", "")
    if not key:
        print("[MDbList] Warning: MDBLIST_API_KEY not set. Skipping ratings.")
    return key


def load_cache():
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_cache(cache):
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        print(f"[MDbList] Warning: could not save cache: {e}")


def enrich_ratings(movies):
    """Add IMDb, RT, and Letterboxd ratings to movies with IMDB IDs."""
    api_key = get_api_key()
    if not api_key:
        return

    cache = load_cache()

    # Collect unique IMDB IDs
    imdb_ids = {}
    for m in movies:
        imdb_id = m.get("imdb_id")
        if imdb_id and imdb_id not in imdb_ids:
            imdb_ids[imdb_id] = m["title"]

    print(f"[MDbList] Enriching ratings for {len(imdb_ids)} unique films...")

    lookups = 0
    cache_hits = 0

    for imdb_id, title in sorted(imdb_ids.items(), key=lambda x: x[1]):
        if imdb_id in cache:
            cache_hits += 1
            continue

        try:
            resp = requests.get(
                f"{API_BASE}/imdb/movie/{imdb_id}",
                params={"apikey": api_key},
                headers=HEADERS,
                timeout=10,
            )

            if resp.status_code == 429:
                time.sleep(2)
                resp = requests.get(
                    f"{API_BASE}/imdb/movie/{imdb_id}",
                    params={"apikey": api_key},
                    headers=HEADERS,
                    timeout=10,
                )

            if resp.status_code == 200:
                data = resp.json()
                ratings_list = data.get("ratings", [])
                ratings = {}
                for r in ratings_list:
                    if r.get("value") is not None:
                        ratings[r["source"]] = r["value"]

                cache[imdb_id] = {
                    "imdb": ratings.get("imdb"),
                    "rt": ratings.get("tomatoes"),
                    "letterboxd": ratings.get("letterboxd"),
                    "metacritic": ratings.get("metacritic"),
                }
                lookups += 1
            else:
                print(f"[MDbList] {resp.status_code} for {title} ({imdb_id})")
                cache[imdb_id] = {}

        except Exception as e:
            print(f"[MDbList] Error for {title}: {e}")
            cache[imdb_id] = {}

        if lookups % 20 == 0 and lookups > 0:
            time.sleep(1)

    print(f"[MDbList] {cache_hits} cache hits, {lookups} API lookups")

    # Apply to movies
    enriched = 0
    for m in movies:
        imdb_id = m.get("imdb_id")
        if not imdb_id:
            continue
        ratings = cache.get(imdb_id, {})
        m["imdb_rating"] = ratings.get("imdb")
        m["rt_score"] = ratings.get("rt")
        m["letterboxd_rating"] = ratings.get("letterboxd")
        if any([m["imdb_rating"], m["rt_score"], m["letterboxd_rating"]]):
            enriched += 1

    print(f"[MDbList] {enriched} films with at least one rating")

    save_cache(cache)
