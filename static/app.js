const search = document.querySelector('#search');
const cards = [...document.querySelectorAll('.collection-card')];
const visibleCount = document.querySelector('#visibleCount');
const empty = document.querySelector('#empty');
const locationFilter = document.querySelector('#locationFilter');
const grid = document.querySelector('#grid');
let sortMode = 'weight';

function applyFilters() {
  const q = (search?.value || '').trim().toLowerCase();
  const location = (locationFilter?.value || '').trim().toLowerCase();
  let shown = 0;
  cards.forEach(card => {
    const titleOk = !q || card.dataset.title.includes(q);
    const locationOk = !location || card.dataset.location === location;
    const ok = titleOk && locationOk;
    card.classList.toggle('hidden', !ok);
    if (ok) shown++;
  });
  if (visibleCount) visibleCount.textContent = shown;
  if (empty) empty.classList.toggle('hidden', shown !== 0);
}

function applySort() {
  if (!grid) return;
  const sorted = [...cards].sort((a, b) => {
    if (sortMode === 'name') {
      return a.dataset.title.localeCompare(b.dataset.title, 'ko');
    }
    const aw = Number(a.dataset.weight || 99);
    const bw = Number(b.dataset.weight || 99);
    if (aw !== bw) return aw - bw;
    return a.dataset.title.localeCompare(b.dataset.title, 'ko');
  });
  sorted.forEach(card => grid.appendChild(card));
}

search?.addEventListener('input', applyFilters);
locationFilter?.addEventListener('change', applyFilters);
document.querySelectorAll('.sort-btn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.sort-btn').forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  sortMode = btn.dataset.sort;
  applySort();
}));

applySort();
applyFilters();
