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
};

let data = null;
let siteConfig = null;
let activeView = 'date';
let activeFilters = null;
let activeCategories = null;
let activeDate = null;
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
    activeFilters.size === theaters.length ? activeFilters.clear() : (activeFilters = new Set(theaters));
    syncFilterChips(theaters);
    refreshAndRender();
  });
  theaters.forEach(t => {
    const chip = addChip(container, shortName(t), 'filter-chip active', () => {
      activeFilters.has(t) ? activeFilters.delete(t) : activeFilters.add(t);
      syncFilterChips(theaters);
      refreshAndRender();
    });
    chip.dataset.theater = t;
  });
}

function syncFilterChips(theaters) {
  document.querySelectorAll('#filters .filter-chip').forEach(chip => {
    if (!chip.dataset.theater) chip.classList.toggle('active', activeFilters.size === theaters.length);
    else chip.classList.toggle('active', activeFilters.has(chip.dataset.theater));
  });
}

// ===================== CATEGORY FILTERS =====================

function renderCategoryFilters(categories) {
  const container = document.getElementById('category-filters');
  container.innerHTML = '';
  const ordered = ALL_CATEGORIES.filter(c => categories.includes(c));
  addChip(container, 'All', 'cat-chip active', () => {
    activeCategories.size === ordered.length ? activeCategories.clear() : (activeCategories = new Set(ordered));
    syncCatChips(ordered);
    refreshAndRender();
  });
  ordered.forEach(cat => {
    const chip = addChip(container, cat, 'cat-chip active', () => {
      activeCategories.has(cat) ? activeCategories.delete(cat) : activeCategories.add(cat);
      syncCatChips(ordered);
      refreshAndRender();
    });
    chip.dataset.category = cat;
    chip.style.setProperty('--cat-color', CATEGORY_COLORS[cat] || '#FFA400');
  });
}

function syncCatChips(categories) {
  document.querySelectorAll('#category-filters .cat-chip').forEach(chip => {
    if (!chip.dataset.category) chip.classList.toggle('active', activeCategories.size === categories.length);
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
    if (a) a.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
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

function refreshAndRender() {
  const filtered = getFilteredMovies();
  const dates = [...new Set(filtered.map(m => m.date))].sort();
  if (dates.length > 0 && !dates.includes(activeDate)) activeDate = dates[0];
  renderDateNav(); renderView(); updateFilterBadge();
}

function renderView() {
  const main = document.getElementById('main');
  const filtered = getFilteredMovies();
  if (filtered.length === 0) { main.innerHTML = '<div class="empty-state">Nothing playing with those filters.</div>'; return; }

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

  // Ratings: IMDb, RT, Letterboxd
  const hasRatings = s.imdb_rating || s.rt_score || s.letterboxd_rating;
  if (hasRatings) {
    html += '<div class="detail-ratings">';
    if (s.imdb_rating) html += `<span class="rating-pill rating-imdb">IMDb ${s.imdb_rating}</span>`;
    if (s.rt_score) html += `<span class="rating-pill rating-rt">RT ${s.rt_score}%</span>`;
    if (s.letterboxd_rating) html += `<span class="rating-pill rating-lb">LB ${s.letterboxd_rating}</span>`;
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

function renderShowtimeRows(showings, groupKey) {
  const grouped = groupBy(showings, groupKey);
  let html = '';
  Object.keys(grouped).sort().forEach(key => {
    const times = grouped[key];
    const label = groupKey === 'theater' ? esc(key) : formatShortDate(key);
    html += '<div class="showtime-row">';
    html += `<span class="${groupKey === 'theater' ? 'theater-name' : 'schedule-date'}">${label}</span>`;
    html += '<span class="times">';
    times.forEach(t => {
      html += `<a href="${esc(t.url)}" target="_blank" rel="noopener" class="time-chip">${esc(t.time)}</a>`;
      if (t.format && t.format !== 'Standard') html += `<span class="tag tag-format">${esc(t.format)}</span>`;
    });
    html += '</span></div>';
  });
  return html;
}

// ===================== BY DATE (poster grid) =====================

function renderByDate(container, movies) {
  const byTitle = groupBy(movies, 'title');
  const titles = Object.keys(byTitle).sort();

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
    else html += `<div class="grid-poster grid-poster-placeholder">${esc(title.slice(0, 2).toUpperCase())}</div>`;
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

  Object.keys(byTheater).sort().forEach(theater => {
    const theaterMovies = byTheater[theater];
    const byTitle = groupBy(theaterMovies, 'title');
    const titles = Object.keys(byTitle).sort();
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
      else html += `<div class="grid-poster grid-poster-placeholder">${esc(title.slice(0, 2).toUpperCase())}</div>`;
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
    item.addEventListener('click', () => {
      const title = item.dataset.title;
      expandedTitle = expandedTitle === title ? null : title;
      renderView();
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
      renderView();
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
    'BIFF': 'BIFF', 'BIFF @ CEN': 'BIFF CEN', 'BIFF @ BT': 'BIFF BT',
    'BIFF @ FC': 'BIFF FC', 'BIFF @ GC': 'BIFF GC', 'BIFF @ LONG': 'BIFF Long',
    'BIFF @ Rembrandt Yard': 'BIFF RY'
  };
  return map[theater] || theater;
}

init();
