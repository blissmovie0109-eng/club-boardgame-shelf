const search = document.querySelector('#search');
const cards = [...document.querySelectorAll('.card')];
const visibleCount = document.querySelector('#visibleCount');
const empty = document.querySelector('#empty');
let players = 0, maxTime = 0;
function filter() {
  const q = (search?.value || '').trim().toLowerCase();
  let shown = 0;
  cards.forEach(card => {
    const titleOk = !q || card.dataset.title.includes(q);
    const minp = Number(card.dataset.minp || 0), maxp = Number(card.dataset.maxp || 0);
    const playerOk = !players || (players === 6 ? maxp >= 6 : minp <= players && maxp >= players);
    const t = Number(card.dataset.maxt || 0);
    const timeOk = !maxTime || (t > 0 && t <= maxTime);
    const ok = titleOk && playerOk && timeOk;
    card.classList.toggle('hidden', !ok);
    if (ok) shown++;
  });
  if (visibleCount) visibleCount.textContent = shown;
  if (empty) empty.classList.toggle('hidden', shown !== 0);
}
search?.addEventListener('input', filter);
document.querySelectorAll('#playerFilters .chip').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('#playerFilters .chip').forEach(x => x.classList.remove('active'));
  btn.classList.add('active'); players = Number(btn.dataset.players); filter();
}));
document.querySelectorAll('#timeFilters .chip').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('#timeFilters .chip').forEach(x => x.classList.remove('active'));
  btn.classList.add('active'); maxTime = Number(btn.dataset.time); filter();
}));
document.querySelector('#randomBtn')?.addEventListener('click', () => {
  const visible = cards.filter(c => !c.classList.contains('hidden'));
  if (!visible.length) return;
  const pick = visible[Math.floor(Math.random() * visible.length)];
  visible.forEach(c => c.classList.remove('picked'));
  pick.classList.add('picked');
  pick.scrollIntoView({behavior:'smooth', block:'center'});
  setTimeout(() => pick.classList.remove('picked'), 2200);
});
