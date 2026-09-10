(() => {
  const card = document.getElementById('todayGameCard');
  const feature = document.getElementById('todayGameFeature');
  if (!card && !feature) return;

  const hide = () => {
    if (card) card.style.display = 'none';
    if (feature) feature.classList.add('hidden');
  };

  fetch('/api/today-game', { headers: { 'Accept': 'application/json' } })
    .then(response => response.ok ? response.json() : null)
    .then(data => {
      if (!data || !data.enabled) {
        hide();
        return;
      }

      if (card) {
        const title = card.querySelector('[data-today-game-title]');
        const link = card.querySelector('[data-today-game-link]');
        if (title) title.textContent = data.title;
        if (link) link.href = data.cafe_url;
        card.style.display = '';
      }

      if (feature) {
        const title = feature.querySelector('[data-today-game-feature-title]');
        const link = feature.querySelector('[data-today-game-feature-link]');
        const image = feature.querySelector('[data-today-game-image]');
        if (title) title.textContent = data.title;
        if (link) link.href = data.cafe_url;
        if (image && data.image_url) {
          image.src = data.image_url;
          image.alt = `${data.title} 대표 이미지`;
          image.addEventListener('error', () => {
            image.style.display = 'none';
            const cover = image.parentElement;
            if (cover) cover.classList.add('image-error');
          }, { once: true });
        }
        feature.classList.remove('hidden');
      }
    })
    .catch(() => hide());
})();
