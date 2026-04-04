const INDIE_THEATERS = [
  'Boulder IFS', 'SIE FilmCenter', 'Landmark Mayan', 'Dairy Arts Center'
];

const ALL_CATEGORIES = [
  'New Release', 'Independent', 'Back in Theaters', 'Classic', 'Festival'
];

const CATEGORY_COLORS = {
  'New Release': '#FFA400',
  'Independent': '#e07c4f',
  'Back in Theaters': '#7b8fd4',
  'Classic': '#b07cc3',
  'Festival': '#4fc9a0',
};

const THEATER_URLS = {
  'Boulder IFS': 'https://internationalfilmseries.com',
  'SIE FilmCenter': 'https://denverfilm.org',
  'Landmark Mayan': 'https://www.landmarktheatres.com/denver/mayan-theatre',
  'Alamo Sloans Lake': 'https://drafthouse.com/denver/theater/sloans-lake',
  'Alamo Westminster': 'https://drafthouse.com/denver/theater/westminster',
  'Cinemark Boulder': 'https://www.cinemark.com/theatres/co-boulder/century-boulder',
  'Dairy Arts Center': 'https://thedairy.org/cinema/',
  'BIFF': 'https://biff1.com',
  'Regal Longmont': 'https://www.regmovies.com/theatres/regal-village-at-the-peaks-rpx-1673',
  'AMC Flatiron Crossing': 'https://www.amctheatres.com/movie-theatres/denver/amc-flatiron-crossing-14',
  'AMC Westminster': 'https://www.amctheatres.com/movie-theatres/denver/amc-westminster-promenade-24',
};

// Distance from downtown Boulder (miles, approximate driving)
const THEATER_DISTANCE = {
  'Boulder IFS': 0,
  'Dairy Arts Center': 0.5,
  'Cinemark Boulder': 1,
  'AMC Flatiron Crossing': 13,
  'Regal Longmont': 15,
  'Alamo Westminster': 18,
  'AMC Westminster': 20,
  'Landmark Mayan': 28,
  'SIE FilmCenter': 30,
  'Alamo Sloans Lake': 35,
};

const SORT_OPTIONS = [
  { key: 'recommended', label: 'Recommended' },
  { key: 'alpha', label: 'A-Z' },
  { key: 'year', label: 'Newest' },
  { key: 'oldest', label: 'Oldest' },
];

let data = null;
let siteConfig = null;
let activeView = 'date';
let activeFilters = null;
let activeCategories = null;
let activeDate = null;
let activeSort = 'recommended';
let drawerOpen = false;
let expandedTitle = null;

async function init() {
  const [moviesResp, siteResp] = await Promise.all([
    fetch('movies.json'),
    fetch('site.json').catch(() => null)
  ]);
  data = await moviesResp.json();
  if (siteResp && siteResp.ok) siteConfig = await siteResp.json();

  ensureCategories(data.movies);

  document.getElementById('updated').textContent =
    'Updated ' + formatDate(new Date(data.last_updated));

  const theaters = [...new Set(data.movies.map(m => m.theater))].sort();
  activeFilters = new Set(theaters);
  renderFilters(theaters);

  const catSet = new Set();
  data.movies.forEach(m => (m.categories || []).forEach(c => catSet.add(c)));
  activeCategories = new Set(catSet);
  renderCategoryFilters([...catSet]);

  const dates = [...new Set(data.movies.map(m => m.date))].sort();
  if (dates.length > 0) {
    const today = new Date().toISOString().slice(0, 10);
    activeDate = dates.includes(today) ? today : dates[0];
  }

  document.getElementById('filter-toggle').addEventListener('click', () => {
    drawerOpen = !drawerOpen;
    document.getElementById('filter-drawer').classList.toggle('hidden', !drawerOpen);
    updateFilterBadge();
  });

  renderBanner();

  // Marquee click: reset to home (unfiltered, By Date, today)
  document.getElementById('marquee-home').addEventListener('click', (e) => {
    e.preventDefault();
    const allTheaters = [...new Set(data.movies.map(m => m.theater))];
    activeFilters = new Set(allTheaters);
    const allCats = new Set();
    data.movies.forEach(m => (m.categories || []).forEach(c => allCats.add(c)));
    activeCategories = new Set(allCats);
    activeView = 'date';
    const today = new Date().toISOString().slice(0, 10);
    const dates = [...new Set(data.movies.map(m => m.date))].sort();
    activeDate = dates.includes(today) ? today : dates[0];
    activeSort = 'recommended';
    expandedTitle = null;
    drawerOpen = false;
    document.getElementById('filter-drawer').classList.add('hidden');
    document.getElementById('sort-select').value = 'recommended';
    document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.toggle-btn[data-view="date"]').classList.add('active');
    syncFilterChips(allTheaters);
    renderDateNav();
    renderView();
    updateFilterBadge();
    window.scrollTo(0, 0);
  });

  document.getElementById('sort-select').addEventListener('change', (e) => {
    activeSort = e.target.value;
    expandedTitle = null;
    renderView();
  });

  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeView = btn.dataset.view;
      expandedTitle = null;
      renderDateNav();
      renderView();
    });
  });

  renderDateNav();
  renderView();
  updateFilterBadge();
}

// ===================== BANNER =====================

function renderBanner() {
  const banner = document.getElementById('banner');
  const text = document.getElementById('banner-text');
  const closeBtn = document.getElementById('banner-close');
  const msg = siteConfig?.banner;
  if (!msg || sessionStorage.getItem('fab-banner-dismissed')) {
    banner.classList.add('hidden');
    return;
  }
  text.innerHTML = msg;
  banner.classList.remove('hidden');
  closeBtn.addEventListener('click', () => {
    banner.classList.add('hidden');
    sessionStorage.setItem('fab-banner-dismissed', '1');
  });
}

// ===================== FILTER BADGE =====================

function updateFilterBadge() {
  const btn = document.getElementById('filter-toggle');
  const allTheaters = [...new Set(data.movies.map(m => m.theater))];
  const allCats = new Set();
  data.movies.forEach(m => (m.categories || []).forEach(c => allCats.add(c)));
  const count = (activeFilters.size < allTheaters.length ? 1 : 0) + (activeCategories.size < allCats.size ? 1 : 0);
  btn.textContent = count > 0 ? `Filters (${count})` : 'Filters';
  btn.classList.toggle('has-filters', count > 0);
}

// ===================== THEATER FILTERS =====================

function renderFilters(theaters) {
  const container = document.getElementById('filters');
  container.innerHTML = '';
  addChip(container, 'All', 'filter-chip active', () => {
    activeFilters = new Set(theaters);
    syncFilterChips(theaters);
    refreshAndRender();
  });
  theaters.forEach(t => {
    const chip = addChip(container, shortName(t), 'filter-chip', () => {
      // Single-select: if already the only one selected, go back to All
      if (activeFilters.size === 1 && activeFilters.has(t)) {
        activeFilters = new Set(theaters);
      } else {
        activeFilters = new Set([t]);
      }
      syncFilterChips(theaters);
      refreshAndRender();
    });
    chip.dataset.theater = t;
  });
}

function syncFilterChips(theaters) {
  const isAll = activeFilters.size === theaters.length;
  document.querySelectorAll('#filters .filter-chip').forEach(chip => {
    if (!chip.dataset.theater) chip.classList.toggle('active', isAll);
    else chip.classList.toggle('active', activeFilters.has(chip.dataset.theater));
  });
}

// ===================== CATEGORY FILTERS =====================

function renderCategoryFilters(categories) {
  const container = document.getElementById('category-filters');
  container.innerHTML = '';
  const ordered = ALL_CATEGORIES.filter(c => categories.includes(c));
  addChip(container, 'All', 'cat-chip active', () => {
    activeCategories = new Set(ordered);
    syncCatChips(ordered);
    refreshAndRender();
  });
  ordered.forEach(cat => {
    const chip = addChip(container, cat, 'cat-chip', () => {
      // Single-select: if already the only one selected, go back to All
      if (activeCategories.size === 1 && activeCategories.has(cat)) {
        activeCategories = new Set(ordered);
      } else {
        activeCategories = new Set([cat]);
      }
      syncCatChips(ordered);
      refreshAndRender();
    });
    chip.dataset.category = cat;
    chip.style.setProperty('--cat-color', CATEGORY_COLORS[cat] || '#FFA400');
  });
}

function syncCatChips(categories) {
  const isAll = activeCategories.size === categories.length;
  document.querySelectorAll('#category-filters .cat-chip').forEach(chip => {
    if (!chip.dataset.category) chip.classList.toggle('active', isAll);
    else chip.classList.toggle('active', activeCategories.has(chip.dataset.category));
  });
}

function addChip(container, text, className, onClick) {
  const chip = document.createElement('button');
  chip.className = className;
  chip.textContent = text;
  chip.addEventListener('click', onClick);
  container.appendChild(chip);
  return chip;
}

// ===================== DATE NAVIGATION =====================

function renderDateNav() {
  const container = document.getElementById('date-nav');
  if (activeView !== 'date') { container.innerHTML = ''; container.style.display = 'none'; return; }
  container.style.display = '';
  const filtered = getFilteredMovies();
  const dates = [...new Set(filtered.map(m => m.date))].sort();
  if (dates.length === 0) { container.innerHTML = ''; return; }
  if (!dates.includes(activeDate)) activeDate = dates[0];

  // If the strip already exists with the same dates, just swap the active class
  // to avoid the layout-shift bounce caused by re-rendering the whole strip.
  const existingChips = container.querySelectorAll('.date-chip');
  const existingDates = [...existingChips].map(c => c.dataset.date);
  const sameStrip = existingDates.length === dates.length && dates.every((d, i) => d === existingDates[i]);

  if (sameStrip) {
    existingChips.forEach(chip => {
      chip.classList.toggle('active', chip.dataset.date === activeDate);
    });
    return;
  }

  // Full re-render (first load or filter changed the set of dates)
  let html = '<div class="date-strip">';
  dates.forEach(date => {
    const d = new Date(date + 'T12:00:00');
    html += `<button class="date-chip ${date === activeDate ? 'active' : ''}" data-date="${date}">`;
    html += `<span class="date-chip-day">${esc(getDayLabel(date))}</span>`;
    html += `<span class="date-chip-num">${d.toLocaleDateString('en-US', { month: 'short' })} ${d.getDate()}</span>`;
    html += '</button>';
  });
  html += '</div>';
  container.innerHTML = html;
  container.querySelectorAll('.date-chip').forEach(chip => {
    chip.addEventListener('click', () => { activeDate = chip.dataset.date; expandedTitle = null; renderDateNav(); renderView(); });
  });
  requestAnimationFrame(() => {
    const a = container.querySelector('.date-chip.active');
    if (a) a.scrollIntoView({ behavior: 'instant', block: 'nearest', inline: 'center' });
  });
}

function getDayLabel(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  const dNorm = new Date(d); dNorm.setHours(12, 0, 0, 0);
  if (dNorm.getTime() === today.getTime()) return 'Today';
  if (dNorm.getTime() === tomorrow.getTime()) return 'Tmrw';
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

// ===================== RENDERING =====================

function getFilteredMovies() {
  return data.movies.filter(m => {
    if (!activeFilters.has(m.theater)) return false;
    return (m.categories || ['New Release']).some(c => activeCategories.has(c));
  });
}

function sortTitles(titles, byTitle) {
  if (activeSort === 'alpha') {
    return titles.sort();
  }
  if (activeSort === 'year') {
    return titles.sort((a, b) => {
      const ya = byTitle[a][0]?.year || 0;
      const yb = byTitle[b][0]?.year || 0;
      return yb - ya || a.localeCompare(b);
    });
  }
  if (activeSort === 'oldest') {
    return titles.sort((a, b) => {
      const ya = byTitle[a][0]?.year || 9999;
      const yb = byTitle[b][0]?.year || 9999;
      return ya - yb || a.localeCompare(b);
    });
  }
  // Recommended: prioritize indie/classic/back-in-theaters + higher Letterboxd, then new releases
  return titles.sort((a, b) => {
    const sa = getRecommendedScore(byTitle[a]);
    const sb = getRecommendedScore(byTitle[b]);
    return sb - sa || a.localeCompare(b);
  });
}

function getRecommendedScore(showings) {
  const s = showings[0];
  const cats = s.categories || [];
  let score = 0;

  // Letterboxd is the primary signal (0-5 scale, heavy weight)
  if (s.letterboxd_rating) score += s.letterboxd_rating * 20;
  else if (s.imdb_rating) score += s.imdb_rating * 6;

  // Category boosts (smaller than ratings, act as tiebreakers)
  if (cats.includes('Classic')) score += 15;
  if (cats.includes('Back in Theaters')) score += 12;
  if (cats.includes('Independent')) score += 10;
  if (cats.includes('Festival')) score += 15;

  // Penalize pure new releases with no ratings (likely blockbusters with no critical consensus yet)
  if (cats.length === 1 && cats[0] === 'New Release' && !s.letterboxd_rating && !s.imdb_rating) {
    score -= 20;
  }

  // Small boost for having a poster
  if (s.poster_url) score += 2;
  return score;
}

function refreshAndRender() {
  const filtered = getFilteredMovies();
  const dates = [...new Set(filtered.map(m => m.date))].sort();
  if (dates.length > 0 && !dates.includes(activeDate)) activeDate = dates[0];
  renderDateNav(); renderView(); updateFilterBadge();
}

let lastRenderedView = null;
let lastRenderedDate = null;

function renderView(expandOnly) {
  const main = document.getElementById('main');
  const filtered = getFilteredMovies();
  if (filtered.length === 0) { main.innerHTML = '<div class="empty-state">Nothing playing with those filters.</div>'; return; }

  // If only expanding/collapsing a card, do a targeted DOM update instead of full re-render
  if (expandOnly && lastRenderedView === activeView && lastRenderedDate === activeDate) {
    updateExpandState(main);
    return;
  }

  lastRenderedView = activeView;
  lastRenderedDate = activeDate;

  if (activeView === 'date') {
    const dayMovies = filtered.filter(m => m.date === activeDate);
    if (dayMovies.length === 0) { main.innerHTML = '<div class="empty-state">Nothing playing this day.</div>'; return; }
    renderByDate(main, dayMovies);
  } else {
    renderByLocation(main, filtered);
  }

  if (expandedTitle) {
    requestAnimationFrame(() => {
      const detail = main.querySelector('.grid-detail');
      if (detail) detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }
}

function updateExpandState(main) {
  // Remove existing detail panel with fade
  const existing = main.querySelector('.grid-detail');
  if (existing) existing.remove();

  // Remove expanded class from all items
  main.querySelectorAll('.grid-item.expanded, .lane-item.expanded').forEach(el => {
    el.classList.remove('expanded');
  });

  if (!expandedTitle) return;

  // Find the grid item to expand
  const targetItem = main.querySelector(`.grid-item[data-title="${CSS.escape(expandedTitle)}"], .lane-item[data-title="${CSS.escape(expandedTitle)}"]`);
  if (!targetItem) return;

  targetItem.classList.add('expanded');

  // Get showings for this title (scoped to active date in date view)
  let filtered = getFilteredMovies();
  if (activeView === 'date') filtered = filtered.filter(m => m.date === activeDate);
  const showings = filtered.filter(m => m.title === expandedTitle);
  if (showings.length === 0) return;

  const groupKey = activeView === 'date' ? 'theater' : 'date';
  const detailHtml = renderDetailPanel(showings, groupKey);

  // Insert detail panel after the item
  const wrapper = document.createElement('div');
  wrapper.innerHTML = detailHtml;
  const detailEl = wrapper.firstElementChild;
  detailEl.style.opacity = '0';
  detailEl.style.transform = 'translateY(-8px)';

  // For grid items, insert after the item in the grid
  if (targetItem.classList.contains('grid-item')) {
    targetItem.insertAdjacentElement('afterend', detailEl);
  } else {
    // Lane item: insert after the lane wrap
    const laneWrap = targetItem.closest('.location-lane-wrap');
    if (laneWrap) laneWrap.insertAdjacentElement('afterend', detailEl);
  }

  // Animate in
  requestAnimationFrame(() => {
    detailEl.style.transition = 'opacity 0.2s, transform 0.2s';
    detailEl.style.opacity = '1';
    detailEl.style.transform = 'translateY(0)';
    detailEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

// ===================== DETAIL PANEL =====================

function renderDetailPanel(showings, groupKey) {
  const s = showings[0];
  const poster = s.poster_url;
  const director = s.director;
  const synopsis = s.synopsis ? truncate(s.synopsis, 180) : '';
  const runtime = s.runtime ? `${s.runtime} min` : '';
  const year = s.year;
  const genres = s.genres;

  let html = '<div class="grid-detail"><div class="grid-detail-inner">';
  if (poster) html += `<img class="detail-poster" src="${esc(poster)}" alt="" loading="lazy">`;
  html += '<div class="detail-body">';
  html += `<div class="detail-title">${esc(s.title || showings[0].title)}</div>`;

  // Meta line: year, genres, runtime
  const metaParts = [];
  if (year) metaParts.push(year);
  if (genres) metaParts.push(genres);
  if (runtime) metaParts.push(runtime);
  if (metaParts.length) html += `<div class="detail-meta">${esc(metaParts.join(' / '))}</div>`;

  // Director
  if (director) html += `<div class="detail-director">Dir. ${esc(director)}</div>`;

  // Ratings: IMDb, RT, Letterboxd (with logos)
  const hasRatings = s.imdb_rating || s.rt_score || s.letterboxd_rating;
  if (hasRatings) {
    html += '<div class="detail-ratings">';
    if (s.imdb_rating) html += `<span class="rating-pill rating-imdb"><img class="rating-logo" src="logos/imdb.svg" alt="IMDb">${s.imdb_rating}</span>`;
    if (s.rt_score) html += `<span class="rating-pill rating-rt"><img class="rating-logo rating-logo-square" src="logos/rt.svg" alt="RT">${s.rt_score}%</span>`;
    if (s.letterboxd_rating) html += `<span class="rating-pill rating-lb"><img class="rating-logo rating-logo-square" src="logos/letterboxd.svg" alt="Letterboxd">${s.letterboxd_rating}</span>`;
    html += '</div>';
  }

  // Synopsis
  if (synopsis) html += `<div class="detail-synopsis">${esc(synopsis)}</div>`;

  // Showtimes
  html += '<div class="detail-showtimes">';
  html += renderShowtimeRows(showings, groupKey);
  html += '</div>';

  html += '</div></div></div>';
  return html;
}

function truncate(str, max) {
  if (str.length <= max) return str;
  return str.slice(0, max).replace(/\s+\S*$/, '') + '...';
}

function isTimePast(dateStr, timeStr) {
  // Only check for today's date
  const today = new Date().toISOString().slice(0, 10);
  if (dateStr !== today) return false;
  try {
    const parsed = new Date(`${dateStr} ${timeStr}`);
    return parsed < new Date();
  } catch { return false; }
}

function renderShowtimeRows(showings, groupKey) {
  const grouped = groupBy(showings, groupKey);
  let html = '';
  Object.keys(grouped).sort().forEach(key => {
    const times = grouped[key];
    const label = groupKey === 'theater' ? esc(key) : formatShortDate(key);

    // Group by format within this venue/date
    const byFormat = {};
    times.forEach(t => {
      const fmt = t.format || 'Standard';
      if (!byFormat[fmt]) byFormat[fmt] = [];
      byFormat[fmt].push(t);
    });

    Object.keys(byFormat).sort().forEach(fmt => {
      const fmtTimes = byFormat[fmt];
      const MAX_VISIBLE = 8;
      const hasMore = fmtTimes.length > MAX_VISIBLE;
      const uid = `st-${key}-${fmt}`.replace(/\W/g, '-');

      html += '<div class="showtime-row">';
      html += `<span class="${groupKey === 'theater' ? 'theater-name' : 'schedule-date'}">${label}`;
      if (fmt !== 'Standard') html += ` <span class="tag tag-format">${esc(fmt)}</span>`;
      html += '</span>';
      html += `<span class="times" id="${uid}">`;
      fmtTimes.forEach((t, i) => {
        const hiddenClass = (hasMore && i >= MAX_VISIBLE) ? ' time-hidden' : '';
        const past = isTimePast(t.date, t.time);
        if (past) {
          html += `<span class="time-chip time-past${hiddenClass}">${esc(t.time)}</span>`;
        } else {
          html += `<a href="${esc(t.url)}" target="_blank" rel="noopener" class="time-chip${hiddenClass}">${esc(t.time)}</a>`;
        }
      });
      if (hasMore) {
        html += `<button class="time-more" onclick="event.preventDefault();event.stopPropagation();var p=this.parentElement;this.style.display='none';setTimeout(function(){p.classList.add('show-all')},200)">+${fmtTimes.length - MAX_VISIBLE} more</button>`;
      }
      html += '</span></div>';
    });
  });
  return html;
}

// ===================== BY DATE (poster grid) =====================

function renderByDate(container, movies) {
  const byTitle = groupBy(movies, 'title');
  const titles = sortTitles(Object.keys(byTitle), byTitle);

  let html = `<div class="date-heading">${formatDayHeading(activeDate)}</div>`;
  html += '<div class="poster-grid">';
  titles.forEach(title => {
    const showings = byTitle[title];
    const poster = showings[0]?.poster_url;
    const year = showings[0]?.year;
    const isExpanded = expandedTitle === title;

    html += `<div class="grid-item ${isExpanded ? 'expanded' : ''}" data-title="${esc(title)}">`;
    html += '<div class="grid-poster-wrap">';
    if (poster) html += `<img class="grid-poster" src="${esc(poster)}" alt="${esc(title)}" loading="lazy">`;
    else html += `<div class="grid-poster grid-poster-placeholder"><span>${esc(title)}</span></div>`;
    html += '</div>';
    html += `<div class="grid-title">${esc(title)}</div>`;
    if (year) html += `<div class="grid-meta">${year}</div>`;
    html += '</div>';

    if (isExpanded) html += renderDetailPanel(showings, 'theater');
  });
  html += '</div>';

  container.innerHTML = html;
  attachGridListeners(container);
}

// ===================== BY LOCATION (horizontal lanes) =====================

function renderByLocation(container, movies) {
  const byTheater = groupBy(movies, 'theater');
  let html = '';

  // Sort theaters by distance from Boulder
  const theaters = Object.keys(byTheater).sort((a, b) => {
    const da = THEATER_DISTANCE[a] ?? (a.startsWith('BIFF') ? 0 : 50);
    const db = THEATER_DISTANCE[b] ?? (b.startsWith('BIFF') ? 0 : 50);
    return da - db;
  });

  theaters.forEach(theater => {
    const theaterMovies = byTheater[theater];
    const byTitle = groupBy(theaterMovies, 'title');
    const titles = sortTitles(Object.keys(byTitle), byTitle);
    const url = getTheaterUrl(theater);

    html += '<div class="location-section">';
    if (url) {
      html += `<a href="${esc(url)}" target="_blank" rel="noopener" class="location-heading">${esc(theater)}</a>`;
    } else {
      html += `<div class="location-heading">${esc(theater)}</div>`;
    }

    html += '<div class="location-lane-wrap">';
    html += '<div class="location-lane">';
    titles.forEach(title => {
      const showings = byTitle[title];
      const poster = showings[0]?.poster_url;
      const year = showings[0]?.year;
      const isExpanded = expandedTitle === title;

      html += `<div class="lane-item ${isExpanded ? 'expanded' : ''}" data-title="${esc(title)}">`;
      html += '<div class="grid-poster-wrap">';
      if (poster) html += `<img class="grid-poster" src="${esc(poster)}" alt="${esc(title)}" loading="lazy">`;
      else html += `<div class="grid-poster grid-poster-placeholder"><span>${esc(title)}</span></div>`;
      html += '</div>';
      html += `<div class="grid-title">${esc(title)}</div>`;
      if (year) html += `<div class="grid-meta">${year}</div>`;
      html += '</div>';
    });
    html += '</div></div>';

    // Expanded detail goes below the lane
    const expandedInThisLane = titles.find(t => expandedTitle === t);
    if (expandedInThisLane) {
      html += renderDetailPanel(byTitle[expandedInThisLane], 'date');
    }

    html += '</div>';
  });

  container.innerHTML = html;

  // Attach click listeners to lane items
  container.querySelectorAll('.lane-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.grid-detail') || e.target.closest('a')) return;
      const title = item.dataset.title;
      expandedTitle = expandedTitle === title ? null : title;
      renderView(true);
    });
  });
  attachGridListeners(container);
}

function getTheaterUrl(theater) {
  // Match BIFF venues
  if (theater.startsWith('BIFF')) return THEATER_URLS['BIFF'];
  return THEATER_URLS[theater] || null;
}

function attachGridListeners(container) {
  container.querySelectorAll('.grid-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.grid-detail') || e.target.closest('a')) return;
      const title = item.dataset.title;
      expandedTitle = expandedTitle === title ? null : title;
      renderView(true);
    });
  });
}

// ===================== CATEGORIZATION =====================

function ensureCategories(movies) {
  if (movies.length > 0 && movies[0].categories) return;
  const currentYear = new Date().getFullYear();
  const indieVenues = new Set(INDIE_THEATERS);
  const titleVenues = {}, titleYear = {}, titleSpecials = {};
  movies.forEach(m => {
    const t = m.title;
    if (!titleVenues[t]) { titleVenues[t] = new Set(); titleSpecials[t] = new Set(); titleYear[t] = null; }
    titleVenues[t].add(m.theater);
    if (m.special) titleSpecials[t].add(m.special);
    if (m.year && !titleYear[t]) titleYear[t] = m.year;
  });
  const titleCategories = {};
  for (const title in titleVenues) {
    const venues = titleVenues[title];
    const specials = titleSpecials[title];
    const year = titleYear[title];
    const isBiff = [...specials].some(s => s.includes('BIFF'));
    const isIndieOnly = [...venues].every(v => indieVenues.has(v) || v.startsWith('BIFF'));
    const cats = [];
    if (isBiff) cats.push('Festival');
    if (isIndieOnly) cats.push('Independent');
    if (year) { const age = currentYear - year; if (age >= 20) cats.push('Classic'); else if (age >= 2) cats.push('Back in Theaters'); else cats.push('New Release'); }
    else if (!isIndieOnly && !isBiff) cats.push('New Release');
    if (cats.length === 0) cats.push('New Release');
    titleCategories[title] = cats;
  }
  movies.forEach(m => { m.categories = titleCategories[m.title] || ['New Release']; });
}

// ===================== HELPERS =====================

function groupBy(arr, key) { return arr.reduce((a, i) => { (a[i[key]] = a[i[key]] || []).push(i); return a; }, {}); }
function esc(str) { const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
function formatDate(d) { return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }

function formatDayHeading(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  const dNorm = new Date(d); dNorm.setHours(12, 0, 0, 0);
  let label = dNorm.getTime() === today.getTime() ? 'Today' : dNorm.getTime() === tomorrow.getTime() ? 'Tomorrow' : d.toLocaleDateString('en-US', { weekday: 'long' });
  return `${label} / ${d.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}`;
}

function formatShortDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function shortName(theater) {
  const map = {
    'Boulder IFS': 'IFS', 'SIE FilmCenter': 'SIE', 'Landmark Mayan': 'Mayan',
    'Alamo Sloans Lake': 'Alamo SL', 'Alamo Westminster': 'Alamo West',
    'Cinemark Boulder': 'Cinemark', 'Dairy Arts Center': 'Dairy',
    'Regal Longmont': 'Regal', 'AMC Flatiron Crossing': 'AMC Flat',
    'AMC Westminster': 'AMC West',
    'BIFF': 'BIFF', 'BIFF @ CEN': 'BIFF CEN', 'BIFF @ BT': 'BIFF BT',
    'BIFF @ FC': 'BIFF FC', 'BIFF @ GC': 'BIFF GC', 'BIFF @ LONG': 'BIFF Long',
    'BIFF @ Rembrandt Yard': 'BIFF RY'
  };
  return map[theater] || theater;
}

init();
