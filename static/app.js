const search = document.querySelector('#search');
const cards = [...document.querySelectorAll('.collection-card')];
const visibleCount = document.querySelector('#visibleCount');
const empty = document.querySelector('#empty');
const locationFilter = document.querySelector('#locationFilter');
const weightFilter = document.querySelector('#weightFilter');
const randomPick = document.querySelector('#randomPick');
const randomResult = document.querySelector('#randomResult');
const grid = document.querySelector('#grid');
let sortMode = 'weight';
let players = 0;

function cardMatches(card) {
  const q = (search?.value || '').trim().toLowerCase();
  const location = (locationFilter?.value || '').trim().toLowerCase();
  const weightBand = Number(weightFilter?.value || 0);
  const titleOk = !q || card.dataset.title.includes(q);
  const locationOk = !location || card.dataset.location === location;
  const minp = Number(card.dataset.minp || 0);
  const maxp = Number(card.dataset.maxp || 0);
  const playerOk = !players || (players === 6 ? maxp >= 6 : minp > 0 && minp <= players && maxp >= players);
  const weight = Number(card.dataset.weight || 0);
  let weightOk = true;
  if (weightBand) {
    if (!weight) weightOk = false;
    else if (weightBand === 4) weightOk = weight >= 4 && weight <= 5;
    else weightOk = weight >= weightBand && weight < weightBand + 1;
  }
  return titleOk && locationOk && playerOk && weightOk;
}

function clearRandomHighlight() {
  cards.forEach(card => card.classList.remove('random-selected'));
}

function applyFilters() {
  let shown = 0;
  cards.forEach(card => {
    const ok = cardMatches(card);
    card.classList.toggle('hidden', !ok);
    if (ok) shown++;
  });
  if (visibleCount) visibleCount.textContent = shown;
  if (empty) empty.classList.toggle('hidden', shown !== 0);
  clearRandomHighlight();
  if (randomResult) randomResult.classList.add('hidden');
}

function applySort() {
  if (!grid) return;
  const sorted = [...cards].sort((a, b) => {
    if (sortMode === 'name') return a.dataset.title.localeCompare(b.dataset.title, 'ko');
    const aw = Number(a.dataset.weight || 99);
    const bw = Number(b.dataset.weight || 99);
    if (aw !== bw) return aw - bw;
    return a.dataset.title.localeCompare(b.dataset.title, 'ko');
  });
  sorted.forEach(card => grid.appendChild(card));
}

function pickRandomGame() {
  const candidates = cards.filter(card => !card.classList.contains('hidden') && cardMatches(card));
  clearRandomHighlight();

  if (!candidates.length) {
    if (randomResult) {
      randomResult.textContent = '조건에 맞는 게임이 없어요. 인원이나 웨이트 조건을 조금 넓혀보세요.';
      randomResult.classList.remove('hidden');
    }
    return;
  }

  const picked = candidates[Math.floor(Math.random() * candidates.length)];
  picked.classList.add('random-selected');
  const title = picked.querySelector('h2')?.textContent?.trim() || '게임';
  const weight = Number(picked.dataset.weight || 0);
  const minp = picked.dataset.minp;
  const maxp = picked.dataset.maxp;

  if (randomResult) {
    const facts = [];
    if (minp && maxp) facts.push(`${minp}${minp !== maxp ? `~${maxp}` : ''}명`);
    if (weight) facts.push(`웨이트 ${weight.toFixed(2)}`);
    randomResult.innerHTML = `🎲 오늘의 선택: <b>${title}</b>${facts.length ? ` · ${facts.join(' · ')}` : ''}`;
    randomResult.classList.remove('hidden');
  }

  picked.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

search?.addEventListener('input', applyFilters);
locationFilter?.addEventListener('change', applyFilters);
weightFilter?.addEventListener('change', applyFilters);
randomPick?.addEventListener('click', pickRandomGame);

document.querySelectorAll('.sort-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.sort-btn').forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  sortMode = btn.dataset.sort;
  applySort();
}));

document.querySelectorAll('#playerFilters .filter-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('#playerFilters .filter-btn').forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  players = Number(btn.dataset.players || 0);
  applyFilters();
}));

applySort();
applyFilters();
