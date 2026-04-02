# Films Around Boulder (FAB) - Build Context

## What This Is
A movie showtime aggregator for Boulder/Denver area theaters. Static site hosted on GitHub Pages, with Python scrapers that pull from 7 theater sources and TMDB for metadata. Automated via GitHub Actions.

**Live site:** jennmwu.github.io/films-around-boulder
**Repo:** github.com/jennmwu/films-around-boulder

## Architecture

```
docs/           <- Static frontend (served by GitHub Pages)
  index.html    <- Single page app
  app.js        <- All frontend logic (filters, date nav, rendering)
  style.css     <- Dark theme, marquee, responsive
  movies.json   <- Scraped data (auto-generated, committed by CI)
  site.json     <- Banner config (edit manually to show/hide banners)

scraper/        <- Python scrapers
  main.py       <- Orchestrator: runs all scrapers, TMDB enrichment, categorization, writes movies.json
  tmdb.py       <- TMDB API enrichment (posters, year, director, genres, ratings)
  overrides.json <- Manual fixes for films TMDB misidentifies
  .tmdb_cache.json <- Persisted TMDB cache (committed to repo for CI)
  theaters/
    ifs.py      <- Boulder International Film Series (HTML scraping)
    cinemark.py <- Cinemark Century Boulder (HTML scraping, same-day only)
    landmark.py <- Landmark Mayan Theatre (REST API)
    alamo.py    <- Alamo Drafthouse Sloans Lake + Westminster (REST API)
    dairy.py    <- Dairy Arts Center / Boedecker (WordPress REST API)
    sie.py      <- SIE FilmCenter / Denver Film (Playwright + Eventive API)
    biff.py     <- Boulder International Film Festival (Eventive REST API)

.github/workflows/
  scrape.yml    <- Runs twice daily (8am/4pm Mountain), commits updated data
```

## TMDB API Key
- Key (v3): `4eb892d1a5ffee6bf9159c3cf71b398a`
- Read token: `eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI0ZWI4OTJkMWE1ZmZlZTZiZjkxNTljM2NmNzFiMzk4YSIsIm5iZiI6MTc3NTE2NDc2NC40Miwic3ViIjoiNjljZWRkNWMxYzNjNGI4NGQ5OWExMzkzIiwic2NvcGVzIjpbImFwaV9yZWFkIl0sInZlcnNpb24iOjF9.ajjkS3nMza46pF4ESRtxe7quCXLhVg1_FRf8NT03Edw`
- Docs: https://developer.themoviedb.org/docs/getting-started
- Must be added as GitHub repo secret `TMDB_API_KEY` for CI runs
- For local runs: `TMDB_API_KEY=4eb892d1a5ffee6bf9159c3cf71b398a python3 scraper/main.py`

## Current State (as of April 2, 2026)

### What's working:
- All 7 scrapers run and produce data
- TMDB enrichment works (761/794 showings got posters on last run)
- Categories: New Release, Independent, Classic, Back in Theaters, Festival
- Multi-category support (a film can be both Independent + Classic)
- Date-by-date pagination with scrollable date strip
- By Location view (grouped by theater)
- Collapsible filter drawer (theaters + categories)
- Configurable banner via site.json
- GitHub Actions workflow written but needs TMDB_API_KEY secret added to repo
- Footer with tagline placeholder

### What needs to be built next (in priority order):

#### 1. Add TMDB API key to GitHub Secrets
Go to github.com/jennmwu/films-around-boulder/settings/secrets/actions
Add secret: Name=`TMDB_API_KEY`, Value=`4eb892d1a5ffee6bf9159c3cf71b398a`

#### 2. Poster images on movie cards
TMDB enrichment already stores `poster_url` in movies.json. The frontend needs to render them. Design goal: poster thumbnail on the left, title/meta/showtimes on the right. Makes the wall of text much more scannable. Keep it responsive (stack on mobile).

#### 3. TMDB rating display + sort by rating
TMDB stores `vote_average` (0-10 scale) in the cache. Need to:
- Pass it through to movies.json (tmdb.py already stores it in cache, just needs to apply it to movies)
- Display it on cards (small badge)
- Add a sort option (by rating vs alphabetical)

#### 4. Letterboxd scores
Letterboxd has NO public API. Options:
- Scrape letterboxd.com/film/{slug}/  (they don't block it aggressively but it's against ToS)
- Use the TMDB rating as a proxy (it correlates well with Letterboxd for most films)
- Could add a link to the Letterboxd page for each film using TMDB's external_ids endpoint
Recommendation: Display TMDB rating, link to Letterboxd page. Don't scrape Letterboxd scores.

#### 5. Rotten Tomatoes scores
RT has NO public API (shut down years ago). Options:
- OMDb API (free tier, 1000 requests/day) returns RT scores. Would need a second API key.
- Scraping RT directly (fragile, they actively block scrapers)
Recommendation: Add OMDb as a secondary enrichment source if RT scores are important.

#### 6. Cinemark future dates
Current Cinemark scraper only gets same-day showtimes (server-rendered HTML). Need to research:
- Whether Cinemark has a hidden API (check network tab on their site)
- Alternative: use a headless browser to click through date tabs
- This is why April 9th shows no Cinemark data

#### 7. Featured/pinned movies
Jenn wants to pin "site maker's faves" to the top. Design:
- Add a `featured` array to site.json with movie titles
- Frontend renders a "Jenn's Picks" section above the regular listings
- Could include a short blurb per pick

#### 8. Footer / About section
Current footer has a tagline placeholder. Jenn wants:
- A photo of herself
- Contact email
- Updated copy (see below)

Footer copy (approved direction):
"I <3 watching movies on the big screen, and nothing breaks my heart more than missing the chance to catch something great in person, to laugh and cry and gasp with a room full of strangers. So I built Films Around Boulder to keep track of what's playing across Boulder and the Front Range, for myself, my friends, and for you too."

#### 9. Design improvements for scannability
The list is long and hard to skim. Ideas discussed:
- Poster cards (biggest win, see #2 above)
- Collapsible cards (tap to expand showtimes)
- Grid layout instead of list
- Start with poster cards, see how it feels

### How to run locally:
```bash
# Install Python deps (one time)
pip3 install -r scraper/requirements.txt
pip3 install playwright && playwright install chromium

# Run scraper with TMDB
TMDB_API_KEY=4eb892d1a5ffee6bf9159c3cf71b398a python3 scraper/main.py

# Serve the frontend
npx serve docs -l 8080
```

### How the categorization works:
- **Festival**: has "BIFF" in special field
- **Independent**: only plays at indie venues (IFS, SIE, Dairy, Mayan)
- **Classic**: TMDB year 20+ years ago
- **Back in Theaters**: TMDB year 2-20 years ago
- **New Release**: current year at wide-release venues, or no year data at non-indie venues
- Categories are non-exclusive (a film can be Independent + Classic)
- Client-side fallback in app.js mirrors the Python logic for when movies.json lacks categories

### Key design decisions:
- Dark theme with gold accent, movie theater marquee aesthetic
- Sticky header: nav bar + date strip only (filters collapse behind drawer)
- One day at a time in date view (reduces overwhelm)
- Category filters are secondary (behind Filters button)
- Banner is configurable via site.json, dismissible per session
- 14-day scrape window
- TMDB cache committed to repo so CI doesn't re-fetch known titles

### Owner
Jenn Wu (jennmwu on GitHub). Director of Product at Solv Health. This is a personal side project. Warm, direct communication style. Cares about design quality and user experience. Will push back on things that feel too noisy or cluttered.
