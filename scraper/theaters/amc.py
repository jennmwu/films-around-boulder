"""
AMC Theatres scraper (Flatiron Crossing 14, Westminster Promenade 24).
Uses Playwright to extract showtime data from the Next.js server-rendered pages.
"""

import asyncio
import json
import re
from datetime import date, timedelta, datetime

VENUES = [
    {
        "id": 52,
        "slug": "amc-flatiron-crossing-14",
        "name": "AMC Flatiron Crossing",
        "market": "denver",
    },
    {
        "id": 92,
        "slug": "amc-westminster-promenade-24",
        "name": "AMC Westminster",
        "market": "denver",
    },
]

BASE_URL = "https://www.amctheatres.com/movie-theatres"


def scrape():
    """Return a list of showtime dicts for AMC theaters."""
    results = []
    for venue in VENUES:
        try:
            venue_results = asyncio.run(_scrape_venue(venue))
            results.extend(venue_results)
        except Exception as e:
            print(f"[AMC] Error scraping {venue['name']}: {e}")
    return results


async def _scrape_venue(venue):
    from playwright.async_api import async_playwright

    name = venue["name"]
    slug = venue["slug"]
    market = venue["market"]
    results = []

    print(f"[AMC] Fetching showtimes for {name}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        today = date.today()

        for offset in range(14):
            show_date = today + timedelta(days=offset)
            date_str = show_date.strftime("%Y-%m-%d")
            url = f"{BASE_URL}/{market}/{slug}/showtimes/all/{date_str}"

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Extract showtime data from the rendered page
                day_results = await page.evaluate(f"""
                    (() => {{
                        const results = [];
                        // Find all movie showtime blocks
                        const movieBlocks = document.querySelectorAll('[data-testid="showtime-movie-container"], .ShowtimesByTheatre-movie, .Showtimes-movie');

                        if (movieBlocks.length === 0) {{
                            // Try Next.js __NEXT_DATA__
                            const nextData = document.getElementById('__NEXT_DATA__');
                            if (nextData) {{
                                try {{
                                    const data = JSON.parse(nextData.textContent);
                                    // Navigate the props tree to find showtimes
                                    const props = data?.props?.pageProps;
                                    if (props?.showtimes) {{
                                        for (const movie of (props.showtimes || [])) {{
                                            const title = movie.name || movie.title || '';
                                            for (const showtime of (movie.showtimes || [])) {{
                                                results.push({{
                                                    title: title,
                                                    time: showtime.showDateTimeLocal || showtime.showDateTime || '',
                                                    format: showtime.premiumFormat || showtime.format || 'Standard',
                                                    url: showtime.purchaseUrl || showtime.ticketUrl || '',
                                                }});
                                            }}
                                        }}
                                        return results;
                                    }}
                                }} catch(e) {{}}
                            }}
                        }}

                        // DOM extraction fallback
                        movieBlocks.forEach(block => {{
                            const titleEl = block.querySelector('h3, h2, [class*="MovieTitle"], [class*="movie-name"]');
                            const title = titleEl ? titleEl.textContent.trim() : '';
                            if (!title) return;

                            const showtimeLinks = block.querySelectorAll('a[href*="ticket"], a[class*="Showtime"], button[class*="Showtime"]');
                            showtimeLinks.forEach(link => {{
                                const timeText = link.textContent.trim();
                                const href = link.getAttribute('href') || '';
                                const formatEl = link.closest('[class*="format"]') || link.parentElement;
                                const formatText = formatEl ? formatEl.getAttribute('data-format') || '' : '';

                                results.push({{
                                    title: title,
                                    time: timeText,
                                    format: formatText || 'Standard',
                                    url: href.startsWith('http') ? href : 'https://www.amctheatres.com' + href,
                                }});
                            }});
                        }});

                        return results;
                    }})()
                """)

                if day_results:
                    for r in day_results:
                        parsed = _parse_result(r, name, date_str)
                        if parsed:
                            results.append(parsed)
                    print(f"[AMC] {name} {show_date}: {len(day_results)} showings")
                else:
                    print(f"[AMC] {name} {show_date}: no data found")

            except Exception as e:
                print(f"[AMC] Error for {name} {show_date}: {e}")

            if offset > 0:
                await page.wait_for_timeout(500)

        await browser.close()

    print(f"[AMC] {name}: {len(results)} total showings")
    return results


def _parse_result(r, theater_name, fallback_date):
    """Parse a raw showtime result into our standard format."""
    title = r.get("title", "").strip()
    if not title:
        return None

    time_raw = r.get("time", "")
    date_iso = fallback_date
    time_formatted = ""

    # Try parsing ISO datetime
    if "T" in time_raw:
        try:
            dt = datetime.fromisoformat(time_raw.replace("Z", "+00:00"))
            date_iso = dt.strftime("%Y-%m-%d")
            time_formatted = dt.strftime("%-I:%M %p")
        except (ValueError, TypeError):
            pass

    # Try parsing time string like "7:30pm" or "7:30 PM"
    if not time_formatted and time_raw:
        clean = re.sub(r"[^\d:apmAPM\s]", "", time_raw).strip()
        for fmt in ["%I:%M %p", "%I:%M%p", "%I:%M"]:
            try:
                t = datetime.strptime(clean, fmt)
                time_formatted = t.strftime("%-I:%M %p")
                break
            except ValueError:
                continue

    if not time_formatted:
        return None

    # Detect format
    fmt_raw = r.get("format", "Standard")
    fmt = _detect_format(fmt_raw)

    url = r.get("url", f"https://www.amctheatres.com")

    return {
        "title": title,
        "director": None,
        "year": None,
        "theater": theater_name,
        "date": date_iso,
        "time": time_formatted,
        "url": url,
        "format": fmt,
        "special": None,
    }


def _detect_format(fmt_str):
    """Normalize AMC format strings."""
    f = fmt_str.lower() if fmt_str else ""
    if "imax" in f:
        return "IMAX"
    if "dolby" in f:
        return "Dolby Cinema"
    if "prime" in f:
        return "PRIME"
    if "3d" in f or "reald" in f:
        return "3D"
    return "Standard"


if __name__ == "__main__":
    results = scrape()
    print(json.dumps(results[:5], indent=2))
    print(f"\nTotal: {len(results)}")
