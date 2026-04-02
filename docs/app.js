const INDIE_THEATERS = [
  'Boulder IFS',
  'SIE FilmCenter',
  'Landmark Mayan',
  'Dairy Arts Center'
];

const ALL_CATEGORIES = [
  'New Release',
  'Independent',
  'Back in Theaters',
  'Classic',
  'Festival'
];

const CATEGORY_COLORS = {
  'New Release': '#c9a84c',
  'Independent': '#e07c4f',
  'Back in Theaters': '#7b8fd4',
  'Classic': '#b07cc3',
  'Festival': '#4fc9a0',
};

let data = null;
let siteConfig = null;
let activeView = 'date';
let activeFilters = null;
let activeCategories = null;
let activeDate = null;
let drawerOpen = false;

async function init() {
  const [moviesResp, siteResp] = await Promise.all([
    fetch('movies.json'),
    fetch('site.json').catch(() => null)
  ]);

  data = await moviesResp.json();
  if (siteResp && siteResp.ok) {
    siteConfig = await siteResp.json();
  }

  ensureCategories(data.movies);

  // Updated timestamp in footer
  document.getElementById('updated').textContent =
    'Updated ' + formatDate(new Date(data.last_updated));

  // Theater filters
  const theaters = [...new Set(data.movies.map(m => m.theater))].sort();
  activeFilters = new Set(theaters);
  renderFilters(theaters);

  // Category filters
  const catSet = new Set();
  data.movies.forEach(m => (m.categories || []).forEach(c => catSet.add(c)));
  activeCategories = new Set(catSet);
  renderCategoryFilters([...catSet]);

  // Date navigation
  const dates = [...new Set(data.movies.map(m => m.date))].sort();
  if (dates.length > 0) {
    const today = new Date().toISOString().slice(0, 10);
    activeDate = dates.includes(today) ? today : dates[0];
  }

  // Filter drawer toggle
  const toggleBtn = document.getElementById('filter-toggle');
  const drawer = document.getElementById('filter-drawer');
  toggleBtn.addEventListener('click', () => {
    drawerOpen = !drawerOpen;
    drawer.classList.toggle('hidden', !drawerOpen);
    updateFilterBadge();
  });

  // Banner
  renderBanner();

  // View toggle
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeView = btn.dataset.view;
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

  text.textContent = msg;
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

  const theatersFiltered = activeFilters.size < allTheaters.length;
  const catsFiltered = activeCategories.size < allCats.size;
  const count = (theatersFiltered ? 1 : 0) + (catsFiltered ? 1 : 0);

  btn.textContent = count > 0 ? `Filters (${count})` : 'Filters';
  btn.classList.toggle('has-filters', count > 0);
}

// ===================== THEATER FILTERS =====================

function renderFilters(theaters) {
  const container = document.getElementById('filters');
  container.innerHTML = '';

  const allChip = document.createElement('button');
  allChip.className = 'filter-chip active';
  allChip.textContent = 'All';
  allChip.addEventListener('click', () => {
    if (activeFilters.size === theaters.length) {
      activeFilters.clear();
    } else {
      activeFilters = new Set(theaters);
    }
    syncFilterChips(theaters);
    refreshAndRender();
  });
  container.appendChild(allChip);

  theaters.forEach(theater => {
    const chip = document.createElement('button');
    chip.className = 'filter-chip active';
    chip.textContent = shortName(theater);
    chip.dataset.theater = theater;
    chip.addEventListener('click', () => {
      activeFilters.has(theater) ? activeFilters.delete(theater) : activeFilters.add(theater);
      syncFilterChips(theaters);
      refreshAndRender();
    });
    container.appendChild(chip);
  });
}

function syncFilterChips(theaters) {
  document.querySelectorAll('#filters .filter-chip').forEach(chip => {
    if (chip.textContent === 'All') {
      chip.classList.toggle('active', activeFilters.size === theaters.length);
    } else {
      chip.classList.toggle('active', activeFilters.has(chip.dataset.theater));
    }
  });
}

// ===================== CATEGORY FILTERS =====================

function renderCategoryFilters(categories) {
  const container = document.getElementById('category-filters');
  container.innerHTML = '';
  const ordered = ALL_CATEGORIES.filter(c => categories.includes(c));

  const allChip = document.createElement('button');
  allChip.className = 'cat-chip active';
  allChip.textContent = 'All';
  allChip.addEventListener('click', () => {
    if (activeCategories.size === ordered.length) {
      activeCategories.clear();
    } else {
      activeCategories = new Set(ordered);
    }
    syncCatChips(ordered);
    refreshAndRender();
  });
  container.appendChild(allChip);

  ordered.forEach(cat => {
    const chip = document.createElement('button');
    chip.className = 'cat-chip active';
    chip.textContent = cat;
    chip.dataset.category = cat;
    chip.style.setProperty('--cat-color', CATEGORY_COLORS[cat] || '#c9a84c');
    chip.addEventListener('click', () => {
      activeCategories.has(cat) ? activeCategories.delete(cat) : activeCategories.add(cat);
      syncCatChips(ordered);
      refreshAndRender();
    });
    container.appendChild(chip);
  });
}

function syncCatChips(categories) {
  document.querySelectorAll('#category-filters .cat-chip').forEach(chip => {
    if (chip.textContent === 'All') {
      chip.classList.toggle('active', activeCategories.size === categories.length);
    } else {
      chip.classList.toggle('active', activeCategories.has(chip.dataset.category));
    }
  });
}

// ===================== DATE NAVIGATION =====================

function renderDateNav() {
  const container = document.getElementById('date-nav');

  if (activeView !== 'date') {
    container.innerHTML = '';
    container.style.display = 'none';
    return;
  }
  container.style.display = '';

  const filtered = getFilteredMovies();
  const dates = [...new Set(filtered.map(m => m.date))].sort();

  if (dates.length === 0) {
    container.innerHTML = '';
    return;
  }

  if (!dates.includes(activeDate)) activeDate = dates[0];

  let html = '<div class="date-strip">';
  dates.forEach(date => {
    const d = new Date(date + 'T12:00:00');
    const dayName = getDayLabel(date);
    const monthDay = d.toLocaleDateString('en-US', { month: 'short' }) + ' ' + d.getDate();
    const isActive = date === activeDate;

    html += `<button class="date-chip ${isActive ? 'active' : ''}" data-date="${date}">`;
    html += `<span class="date-chip-day">${esc(dayName)}</span>`;
    html += `<span class="date-chip-num">${monthDay}</span>`;
    html += '</button>';
  });
  html += '</div>';
  container.innerHTML = html;

  container.querySelectorAll('.date-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      activeDate = chip.dataset.date;
      renderDateNav();
      renderView();
    });
  });

  requestAnimationFrame(() => {
    const active = container.querySelector('.date-chip.active');
    if (active) active.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
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
    const cats = m.categories || ['New Release'];
    return cats.some(c => activeCategories.has(c));
  });
}

function refreshAndRender() {
  const filtered = getFilteredMovies();
  const dates = [...new Set(filtered.map(m => m.date))].sort();
  if (dates.length > 0 && !dates.includes(activeDate)) activeDate = dates[0];
  renderDateNav();
  renderView();
  updateFilterBadge();
}

function renderView() {
  const main = document.getElementById('main');
  const filtered = getFilteredMovies();

  if (filtered.length === 0) {
    main.innerHTML = '<div class="empty-state">Nothing playing with those filters.</div>';
    return;
  }

  if (activeView === 'date') {
    const dayMovies = filtered.filter(m => m.date === activeDate);
    if (dayMovies.length === 0) {
      main.innerHTML = '<div class="empty-state">Nothing playing this day.</div>';
      return;
    }
    renderByDate(main, dayMovies);
  } else {
    renderByLocation(main, filtered);
  }
}

function getMovieMeta(showings) {
  const s = showings[0];
  const parts = [];
  if (s.director) parts.push(s.director);
  if (s.year) parts.push(s.year);
  if (s.genres) parts.push(s.genres);
  return parts.join(' / ');
}

function getPoster(showings) {
  const s = showings[0];
  return s.poster_url || null;
}

function getRating(showings) {
  const s = showings[0];
  return s.rating || null;
}

function renderMovieCard(title, showings, renderShowtimes) {
  const meta = getMovieMeta(showings);
  const poster = getPoster(showings);
  const rating = getRating(showings);

  let html = '<div class="movie-card">';
  if (poster) {
    html += '<div class="card-with-poster">';
    html += `<img class="card-poster" src="${esc(poster)}" alt="" loading="lazy">`;
    html += '<div class="card-body">';
  }

  html += `<div class="movie-title">${esc(title)}</div>`;
  if (meta || rating) {
    html += '<div class="movie-meta">';
    if (meta) html += esc(meta);
    if (rating) html += `<span class="rating-badge">${rating}</span>`;
    html += '</div>';
  }

  html += renderShowtimes();

  if (poster) html += '</div></div>';
  html += '</div>';
  return html;
}

function renderShowtimeRows(showings, groupKey) {
  const grouped = groupBy(showings, groupKey);
  let html = '';
  Object.keys(grouped).sort().forEach(key => {
    const times = grouped[key];
    html += '<div class="showtime-row">';
    html += `<span class="${groupKey === 'theater' ? 'theater-name' : 'schedule-date'}">${groupKey === 'theater' ? esc(key) : formatShortDate(key)}</span>`;
    html += '<span class="times">';
    times.forEach(t => {
      html += `<a href="${esc(t.url)}" target="_blank" rel="noopener" class="time-chip">${esc(t.time)}</a>`;
      if (t.format && t.format !== 'Standard') html += `<span class="tag tag-format">${esc(t.format)}</span>`;
      if (t.special) html += `<span class="tag tag-special">${esc(t.special)}</span>`;
    });
    html += '</span></div>';
  });
  return html;
}

function renderByDate(container, movies) {
  const byTitle = groupBy(movies, 'title');
  let html = '<div class="date-section">';
  html += `<div class="date-heading">${formatDayHeading(activeDate)}</div>`;

  Object.keys(byTitle).sort().forEach(title => {
    const showings = byTitle[title];
    html += renderMovieCard(title, showings, () => renderShowtimeRows(showings, 'theater'));
  });

  html += '</div>';
  container.innerHTML = html;
}

function renderByLocation(container, movies) {
  const byTheater = groupBy(movies, 'theater');
  let html = '';

  Object.keys(byTheater).sort().forEach(theater => {
    const theaterMovies = byTheater[theater];
    const byTitle = groupBy(theaterMovies, 'title');

    html += '<div class="location-section">';
    html += `<div class="date-heading">${esc(theater)}</div>`;

    Object.keys(byTitle).sort().forEach(title => {
      const showings = byTitle[title];
      html += renderMovieCard(title, showings, () => renderShowtimeRows(showings, 'date'));
    });
    html += '</div>';
  });

  container.innerHTML = html;
}

// ===================== CATEGORIZATION (client-side fallback) =====================

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
    if (year) {
      const age = currentYear - year;
      if (age >= 20) cats.push('Classic');
      else if (age >= 2) cats.push('Back in Theaters');
      else cats.push('New Release');
    } else if (!isIndieOnly && !isBiff) {
      cats.push('New Release');
    }
    if (cats.length === 0) cats.push('New Release');
    titleCategories[title] = cats;
  }

  movies.forEach(m => { m.categories = titleCategories[m.title] || ['New Release']; });
}

// ===================== HELPERS =====================

function groupBy(arr, key) {
  return arr.reduce((acc, item) => { const k = item[key]; if (!acc[k]) acc[k] = []; acc[k].push(item); return acc; }, {});
}

function esc(str) { const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }

function formatDate(d) {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDayHeading(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  const dNorm = new Date(d); dNorm.setHours(12, 0, 0, 0);
  let label = '';
  if (dNorm.getTime() === today.getTime()) label = 'Today';
  else if (dNorm.getTime() === tomorrow.getTime()) label = 'Tomorrow';
  else label = d.toLocaleDateString('en-US', { weekday: 'long' });
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
