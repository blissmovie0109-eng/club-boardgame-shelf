const search = document.querySelector('#search');
const visibleCount = document.querySelector('#visibleCount');
const empty = document.querySelector('#empty');
const locationFilter = document.querySelector('#locationFilter');
const weightFilter = document.querySelector('#weightFilter');
const randomPick = document.querySelector('#randomPick');
const grid = document.querySelector('#grid');
const pager = document.querySelector('#pager');
const prevPage = document.querySelector('#prevPage');
const nextPage = document.querySelector('#nextPage');
const pageInfo = document.querySelector('#pageInfo');
const todayPick = document.querySelector('#todayPick');
const todayPickCover = document.querySelector('#todayPickCover');
const todayPickTitle = document.querySelector('#todayPickTitle');
const todayPickSubtitle = document.querySelector('#todayPickSubtitle');
const todayPickFacts = document.querySelector('#todayPickFacts');
const todayPickActions = document.querySelector('#todayPickActions');

let sortMode = 'weight';
let players = 0;
let page = 1;
let pages = 1;
let searchTimer = null;
let requestToken = 0;

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function linkifyText(value = '') {
  const text = String(value || '');
  const urlPattern = /https?:\/\/[^\s<>"']+/gi;
  let result = '';
  let lastIndex = 0;

  for (const match of text.matchAll(urlPattern)) {
    result += escapeHtml(text.slice(lastIndex, match.index));
    let url = match[0];
    let trailing = '';
    while (/[),.!?;:\]\}]$/.test(url)) {
      trailing = url.slice(-1) + trailing;
      url = url.slice(0, -1);
    }
    if (url) {
      const safeUrl = escapeHtml(url);
      result += `<a class="description-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a>`;
    }
    result += escapeHtml(trailing);
    lastIndex = match.index + match[0].length;
  }
  result += escapeHtml(text.slice(lastIndex));
  return result;
}

function queryParams(extra = {}) {
  const params = new URLSearchParams();
  const q = (search?.value || '').trim();
  const location = locationFilter?.value || '';
  const weight = weightFilter?.value || '';
  if (q) params.set('q', q);
  if (location) params.set('location', location);
  if (weight) params.set('weight', weight);
  if (players) params.set('players', String(players));
  params.set('sort', sortMode);
  Object.entries(extra).forEach(([key, value]) => params.set(key, String(value)));
  return params;
}

function stars(weight) {
  if (!weight) return '<span class="muted">정보 없음</span>';
  const full = Math.max(0, Math.min(5, Math.floor(weight)));
  let html = '<span class="stars">';
  for (let i = 0; i < 5; i++) html += i < full ? '★' : '<span class="star-off">★</span>';
  html += `</span> <strong>${Number(weight).toFixed(2)}</strong>`;
  return html;
}

function actionLinks(game) {
  const links = [];
  if (game.material_url) links.push(`<a class="material-btn" href="${escapeHtml(game.material_url)}" target="_blank" rel="noopener">📄 자료</a>`);
  if (game.video_url) links.push(`<a class="video-btn" href="${escapeHtml(game.video_url)}" target="_blank" rel="noopener">🎬 영상</a>`);
  if (game.source_url?.startsWith('http')) links.push(`<a class="info-btn" href="${escapeHtml(game.source_url)}" target="_blank" rel="noopener">🔎 정보</a>`);
  return links.join('');
}

function typeBadge(game) {
  if (game.game_type === 'standalone_expansion') return '<span class="tag">🧩 독립형 확장</span>';
  return '';
}

function cardHtml(game) {
  const title = escapeHtml(game.title);
  const detailUrl = escapeHtml(game.detail_url || `/game/${game.id}`);
  const image = game.image_url
    ? `<img src="${escapeHtml(game.image_url)}" alt="${title}" loading="lazy" referrerpolicy="no-referrer">`
    : '<div class="cover-placeholder">🎲</div>';
  const cover = `<a class="cover-link" href="${detailUrl}" aria-label="${title} 상세보기"><div class="collection-cover">${image}</div></a>`;
  const playersText = game.min_players
    ? `${game.min_players}${game.max_players && game.max_players !== game.min_players ? `~${game.max_players}` : ''}명`
    : '정보 없음';
  const timeText = game.min_time
    ? `${game.min_time}${game.max_time && game.max_time !== game.min_time ? `~${game.max_time}` : ''}분`
    : '';
  const actions = actionLinks(game);
  const expansionBadge = game.expansion_count
    ? `<span class="tag expansion-count-tag">🧩 확장 ${game.expansion_count}개</span>`
    : '';
  const badges = [game.category ? `<span class="tag">${escapeHtml(game.category)}</span>` : '', typeBadge(game), expansionBadge].filter(Boolean).join(' ');
  const parentInfo = game.game_type === 'standalone_expansion' && game.parent_title
    ? `<div class="info-line">🧩 <b>본판:</b> ${escapeHtml(game.parent_title)}</div>`
    : '';

  return `<article class="collection-card" data-game-id="${game.id}">
    ${cover}
    <div class="collection-body">
      <h2><a class="game-title-link" href="${detailUrl}">${title}</a></h2>
      ${badges ? `<div class="category-row">${badges}</div>` : ''}
      ${parentInfo}
      <div class="info-line">⚖ <b>웨이트:</b> ${stars(game.difficulty)}</div>
      <div class="info-line">👥 <b>인원:</b> ${playersText}${game.best_players ? ` <span class="muted">(베스트: ${escapeHtml(game.best_players)})</span>` : ''}</div>
      ${game.recommended_players ? `<div class="info-line">👍 <b>추천:</b> ${escapeHtml(game.recommended_players)}</div>` : ''}
      ${timeText ? `<div class="info-line">⏱ <b>시간:</b> ${timeText}</div>` : ''}
      <div class="info-line location-line">📍 <b>보유 장소:</b> <span class="location-pill">${escapeHtml(game.location || '미지정')}</span></div>
      ${game.description ? `<details class="game-description"><summary>게임 설명</summary><p>${linkifyText(game.description)}</p></details>` : ''}
      ${actions ? `<div class="card-actions multi-actions">${actions}</div>` : ''}
    </div>
  </article>`;
}

async function loadGames({ resetPage = false } = {}) {
  if (resetPage) page = 1;
  const token = ++requestToken;
  grid?.classList.add('is-loading');
  try {
    const response = await fetch(`/api/games?${queryParams({ page, per_page: 48 })}`);
    if (!response.ok) throw new Error('목록을 불러오지 못했습니다.');
    const data = await response.json();
    if (token !== requestToken) return;
    page = data.page;
    pages = data.pages;
    if (visibleCount) visibleCount.textContent = data.total;
    if (grid) grid.innerHTML = data.games.map(cardHtml).join('');
    if (empty) empty.classList.toggle('hidden', data.total !== 0);
    if (pager) pager.classList.toggle('hidden', data.total === 0 || pages <= 1);
    if (pageInfo) pageInfo.textContent = `${page} / ${pages}`;
    if (prevPage) prevPage.disabled = page <= 1;
    if (nextPage) nextPage.disabled = page >= pages;
  } catch (error) {
    if (grid) grid.innerHTML = `<div class="load-error">${escapeHtml(error.message)}</div>`;
  } finally {
    grid?.classList.remove('is-loading');
  }
}

function showTodayPick(game) {
  if (!todayPick || !game) return;
  todayPickCover.innerHTML = game.image_url
    ? `<a href="${escapeHtml(game.detail_url)}"><img src="${escapeHtml(game.image_url)}" alt="${escapeHtml(game.title)}" referrerpolicy="no-referrer"></a>`
    : `<a href="${escapeHtml(game.detail_url)}"><div class="today-pick-placeholder">🎲</div></a>`;
  todayPickTitle.innerHTML = `<a class="game-title-link" href="${escapeHtml(game.detail_url)}">${escapeHtml(game.title)}</a>`;
  todayPickSubtitle.textContent = [game.subtitle, game.year ? `${game.year}년` : '', game.game_type === 'standalone_expansion' ? '독립형 확장' : ''].filter(Boolean).join(' · ');
  const facts = [];
  if (game.min_players) facts.push(`👥 ${game.min_players}${game.max_players && game.max_players !== game.min_players ? `~${game.max_players}` : ''}명`);
  if (game.difficulty) facts.push(`⚖ 웨이트 ${Number(game.difficulty).toFixed(2)}`);
  if (game.min_time) facts.push(`⏱ ${game.min_time}${game.max_time && game.max_time !== game.min_time ? `~${game.max_time}` : ''}분`);
  if (game.location) facts.push(`📍 ${game.location}`);
  if (game.expansion_count) facts.push(`🧩 확장 ${game.expansion_count}개`);
  todayPickFacts.innerHTML = facts.map(f => `<span>${escapeHtml(f)}</span>`).join('');
  todayPickActions.innerHTML = `<a class="info-btn" href="${escapeHtml(game.detail_url)}">게임 상세</a>${actionLinks(game)}`;
  todayPick.classList.remove('hidden');
  todayPick.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function pickRandomGame() {
  if (!randomPick) return;
  randomPick.disabled = true;
  randomPick.classList.add('is-spinning');
  try {
    const params = queryParams();
    params.delete('sort');
    const response = await fetch(`/api/games/random?${params}`);
    if (!response.ok) throw new Error('랜덤 게임을 고르지 못했습니다.');
    const data = await response.json();
    if (!data.game) {
      todayPick?.classList.remove('hidden');
      todayPickCover.innerHTML = '<div class="today-pick-placeholder">🤔</div>';
      todayPickTitle.textContent = '조건에 맞는 게임이 없어요';
      todayPickSubtitle.textContent = '인원이나 웨이트 조건을 조금 넓혀보세요.';
      todayPickFacts.innerHTML = '';
      todayPickActions.innerHTML = '';
      return;
    }
    showTodayPick(data.game);
  } finally {
    randomPick.disabled = false;
    randomPick.classList.remove('is-spinning');
  }
}

search?.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadGames({ resetPage: true }), 250);
});
locationFilter?.addEventListener('change', () => loadGames({ resetPage: true }));
weightFilter?.addEventListener('change', () => loadGames({ resetPage: true }));
randomPick?.addEventListener('click', pickRandomGame);
prevPage?.addEventListener('click', () => { if (page > 1) { page--; loadGames(); window.scrollTo({ top: 0, behavior: 'smooth' }); } });
nextPage?.addEventListener('click', () => { if (page < pages) { page++; loadGames(); window.scrollTo({ top: 0, behavior: 'smooth' }); } });

document.querySelectorAll('.sort-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.sort-btn').forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  sortMode = btn.dataset.sort;
  loadGames({ resetPage: true });
}));

document.querySelectorAll('#playerFilters .filter-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('#playerFilters .filter-btn').forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  players = Number(btn.dataset.players || 0);
  loadGames({ resetPage: true });
}));

loadGames();
