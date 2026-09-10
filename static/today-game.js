(() => {
  const card = document.getElementById('todayGameCard');
  const feature = document.getElementById('todayGameFeature');
  if (!card && !feature) return;

  const isAdmin = !!(card && card.querySelector('.today-game-admin'));

  const hide = () => {
    if (card) {
      // 관리 모드에서는 아직 오늘의 게임을 등록하지 않았더라도
      // 설정 버튼이 보이도록 카드 자체는 유지한다.
      if (isAdmin) {
        card.style.display = '';
        const title = card.querySelector('[data-today-game-title]');
        if (title) title.textContent = '오늘의 게임 등록하기';
      } else {
        card.style.display = 'none';
      }
    }
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
