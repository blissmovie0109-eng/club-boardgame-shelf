(() => {
  const openBtn = document.getElementById('firstPlayerOpen');
  const modal = document.getElementById('firstPlayerModal');
  const closeBtn = document.getElementById('firstPlayerClose');
  const arena = document.getElementById('touchArena');
  const pointsLayer = document.getElementById('touchPoints');
  const guideTitle = document.getElementById('touchGuideTitle');
  const guideText = document.getElementById('touchGuideText');
  const countdownEl = document.getElementById('touchCountdown');
  const winnerEl = document.getElementById('touchWinner');
  const resetBtn = document.getElementById('touchReset');
  const numberButtons = document.getElementById('playerNumberButtons');
  const numberResult = document.getElementById('numberPickResult');
  if (!openBtn || !modal || !arena) return;

  let locked = false;
  let countdownTimer = null;
  let stableTouchIds = [];
  let latestTouches = [];

  function openModal() {
    modal.classList.remove('hidden');
    document.body.classList.add('first-player-opened');
    resetTouchPicker();
  }

  function closeModal() {
    modal.classList.add('hidden');
    document.body.classList.remove('first-player-opened');
    resetTouchPicker();
  }

  function clearCountdown() {
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = null;
    countdownEl.classList.add('hidden');
    countdownEl.textContent = '';
  }

  function resetTouchPicker() {
    locked = false;
    stableTouchIds = [];
    latestTouches = [];
    clearCountdown();
    pointsLayer.innerHTML = '';
    winnerEl.classList.add('hidden');
    resetBtn.classList.add('hidden');
    guideTitle.textContent = '2명 이상 손가락을 올려주세요';
    guideText.textContent = '손가락이 모이면 자동으로 추첨합니다.';
  }

  function renderTouches(touches) {
    const rect = arena.getBoundingClientRect();
    const existing = new Map([...pointsLayer.children].map(el => [el.dataset.touchId, el]));
    const active = new Set();
    touches.forEach((touch, index) => {
      const id = String(touch.identifier);
      active.add(id);
      let el = existing.get(id);
      if (!el) {
        el = document.createElement('div');
        el.className = 'touch-point';
        el.dataset.touchId = id;
        el.textContent = index + 1;
        pointsLayer.appendChild(el);
      }
      el.style.left = `${touch.clientX - rect.left}px`;
      el.style.top = `${touch.clientY - rect.top}px`;
    });
    existing.forEach((el, id) => {
      if (!active.has(id) && !locked) el.remove();
    });
  }

  function sameTouchSet(touches) {
    if (touches.length !== stableTouchIds.length) return false;
    const ids = [...touches].map(t => t.identifier).sort((a, b) => a - b);
    return ids.every((id, i) => id === stableTouchIds[i]);
  }

  function beginCountdown(touches) {
    clearCountdown();
    stableTouchIds = [...touches].map(t => t.identifier).sort((a, b) => a - b);
    let count = 3;
    countdownEl.textContent = count;
    countdownEl.classList.remove('hidden');
    guideTitle.textContent = `${touches.length}명 감지됨`;
    guideText.textContent = '그대로 손가락을 유지해 주세요.';
    countdownTimer = setInterval(() => {
      if (!sameTouchSet(latestTouches)) {
        clearCountdown();
        stableTouchIds = [];
        if (!locked) {
          guideTitle.textContent = latestTouches.length >= 2 ? `${latestTouches.length}명 감지됨` : '2명 이상 손가락을 올려주세요';
          guideText.textContent = '모두 올리면 다시 추첨을 시작합니다.';
        }
        return;
      }
      count -= 1;
      if (count > 0) {
        countdownEl.textContent = count;
      } else {
        clearCountdown();
        chooseTouchWinner();
      }
    }, 700);
  }

  function chooseTouchWinner() {
    if (latestTouches.length < 2) return;
    locked = true;
    const winnerTouch = latestTouches[Math.floor(Math.random() * latestTouches.length)];
    [...pointsLayer.children].forEach(el => {
      if (el.dataset.touchId === String(winnerTouch.identifier)) {
        el.classList.add('is-winner');
        el.textContent = '선!';
      } else {
        el.classList.add('is-loser');
      }
    });
    guideTitle.textContent = '선이 정해졌어요!';
    guideText.textContent = '손가락을 떼도 결과가 유지됩니다.';
    winnerEl.classList.remove('hidden');
    resetBtn.classList.remove('hidden');
    if (navigator.vibrate) navigator.vibrate([80, 50, 160]);
  }

  function handleTouches(event) {
    event.preventDefault();
    if (locked) return;
    latestTouches = [...event.touches];
    renderTouches(latestTouches);
    if (latestTouches.length < 2) {
      clearCountdown();
      stableTouchIds = [];
      guideTitle.textContent = latestTouches.length === 1 ? '한 명 더 올려주세요' : '2명 이상 손가락을 올려주세요';
      guideText.textContent = '손가락이 모이면 자동으로 추첨합니다.';
      return;
    }
    if (!countdownTimer && !sameTouchSet(latestTouches)) beginCountdown(latestTouches);
    else if (!countdownTimer && stableTouchIds.length === 0) beginCountdown(latestTouches);
  }

  function pickByCount(count) {
    const picked = Math.floor(Math.random() * count) + 1;
    numberResult.classList.remove('hidden');
    numberResult.innerHTML = `<span>${count}명 중 이번 선은</span><b>${picked}번 플레이어!</b><button type="button" data-repick="${count}">다시 뽑기</button>`;
    if (navigator.vibrate) navigator.vibrate(100);
  }

  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  resetBtn.addEventListener('click', resetTouchPicker);
  modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal(); });

  ['touchstart', 'touchmove', 'touchend', 'touchcancel'].forEach(type => {
    arena.addEventListener(type, handleTouches, {passive:false});
  });

  numberButtons?.addEventListener('click', event => {
    const button = event.target.closest('button[data-count]');
    if (!button) return;
    pickByCount(Number(button.dataset.count));
  });
  numberResult?.addEventListener('click', event => {
    const button = event.target.closest('button[data-repick]');
    if (!button) return;
    pickByCount(Number(button.dataset.repick));
  });
})();
