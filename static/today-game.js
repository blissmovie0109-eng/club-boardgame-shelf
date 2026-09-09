(() => {
  const card = document.getElementById('todayGameCard');
  if (!card) return;
  fetch('/api/today-game', { headers: { 'Accept': 'application/json' } })
    .then(response => response.ok ? response.json() : null)
    .then(data => {
      if (!data || !data.enabled) return;
      const title = card.querySelector('[data-today-game-title]');
      const link = card.querySelector('[data-today-game-link]');
      if (title) title.textContent = data.title;
      if (link) link.href = data.cafe_url;
      card.classList.remove('hidden');
    })
    .catch(() => {});
})();
