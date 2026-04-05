"""
Regal Cinemas scraper (Village at the Peaks, Longmont).
Uses Playwright to bypass Cloudflare and hit the internal showtimes API.
"""

import asyncio
import json
import time
import requests
from datetime import date, timedelta, datetime

THEATER_CODE = "1673"
THEATER_NAME = "Regal Longmont"
API_URL = "https://www.regmovies.com/api/getShowtimes"
THEATER_PAGE = "https://www.regmovies.com/theatres/regal-village-at-the-peaks-rpx-1673"

HEADERS = {
    "User-Agent": "FAB-MovieTracker/1.0 (personal project; films-around-boulder)"
}


def scrape():
    """Return a list of showtime dicts for Regal Longmont."""
    print(f"[Regal] Fetching showtimes via Playwright...")
    return asyncio.run(_scrape_async())


async def _scrape_async():
    from playwright.async_api import async_playwright

    results = []
    today = date.today()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # First load the theater page to get past Cloudflare
        try:
            await page.goto(THEATER_PAGE, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"[Regal] Initial page load error (continuing): {e}")

        # Now hit the API for each date
        for offset in range(10):
            show_date = today + timedelta(days=offset)
            date_str = show_date.strftime("%m-%d-%Y")

            try:
                resp = await page.evaluate(f"""
                    fetch('{API_URL}?theatres={THEATER_CODE}&date={date_str}')
                        .then(r => r.json())
                        .catch(e => ({{ error: e.message }}))
                """)

                if resp and not resp.get("error") and resp.get("shows"):
                    day_results = _parse_shows(resp["shows"])
                    results.extend(day_results)
                    print(f"[Regal] {show_date}: {len(day_results)} showings")
                elif resp and resp.get("error"):
                    print(f"[Regal] Error for {show_date}: {resp['error']}")

            except Exception as e:
                print(f"[Regal] Error fetching {show_date}: {e}")

            if offset > 0:
                await page.wait_for_timeout(150)

        await browser.close()

    print(f"[Regal] Scraped {len(results)} total showings")
    return results


def _parse_shows(shows):
    """Parse the Regal API shows array into showtime dicts."""
    results = []

    for show in shows:
        films = show.get("Film", [])
        for film in films:
            title = film.get("Title", "")
            if not title:
                continue

            performances = film.get("Performances", [])
            for perf in performances:
                if perf.get("StopSales"):
                    continue

                showtime_str = perf.get("CalendarShowTime", "")
                if not showtime_str:
                    continue

                try:
                    dt = datetime.fromisoformat(showtime_str)
                    date_iso = dt.strftime("%Y-%m-%d")
                    time_formatted = dt.strftime("%-I:%M %p")
                except (ValueError, TypeError):
                    continue

                # Detect format from PerformanceGroup and attributes
                fmt = _detect_format(perf)

                # Build ticket URL
                perf_id = perf.get("PerformanceId", "")
                ticket_url = f"https://www.regmovies.com/theatres/regal-village-at-the-peaks-rpx-1673"

                results.append({
                    "title": title,
                    "director": None,
                    "year": None,
                    "theater": THEATER_NAME,
                    "date": date_iso,
                    "time": time_formatted,
                    "url": ticket_url,
                    "format": fmt,
                    "special": None,
                })

    return results


def _detect_format(perf):
    """Detect screening format from performance attributes."""
    group = (perf.get("PerformanceGroup") or "").lower()
    attrs = [a.lower() for a in perf.get("PerformanceAttributes", [])]
    attrs_str = " ".join(attrs)

    if "rpx" in group or "rpx" in attrs_str:
        return "RPX"
    if "imax" in group or "imax" in attrs_str:
        return "IMAX"
    if "4dx" in group or "4dx" in attrs_str:
        return "4DX"
    if "3d" in attrs_str or "reald" in attrs_str:
        return "3D"
    if "screenx" in group:
        return "ScreenX"
    return "Standard"


if __name__ == "__main__":
    results = scrape()
    print(json.dumps(results[:5], indent=2))
    print(f"\nTotal: {len(results)}")
