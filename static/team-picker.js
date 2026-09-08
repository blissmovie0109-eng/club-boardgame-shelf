(() => {
  const openBtn = document.getElementById('teamPickerOpen');
  const modal = document.getElementById('teamPickerModal');
  const closeBtn = document.getElementById('teamPickerClose');
  const teamCountButtons = document.getElementById('teamCountButtons');
  const selectedCountEl = document.getElementById('selectedTeamCount');
  const arena = document.getElementById('teamTouchArena');
  const pointsLayer = document.getElementById('teamTouchPoints');
  const guideTitle = document.getElementById('teamGuideTitle');
  const guideText = document.getElementById('teamGuideText');
  const countdownEl = document.getElementById('teamCountdown');
  const resultEl = document.getElementById('teamResult');
  const resetBtn = document.getElementById('teamReset');
  const shuffleBtn = document.getElementById('teamShuffle');
  if (!openBtn || !modal || !arena) return;

  let teamCount = 2;
  let locked = false;
  let countdownTimer = null;
  let revealTimer = null;
  let stableTouchIds = [];
  let latestTouches = [];

  const TEAM_NAMES = ['A팀', 'B팀', 'C팀', 'D팀', 'E팀', 'F팀'];

  function openModal() {
    modal.classList.remove('hidden');
    document.body.classList.add('team-picker-opened');
    resetPicker();
  }

  function closeModal() {
    modal.classList.add('hidden');
    document.body.classList.remove('team-picker-opened');
    resetPicker();
  }

  function clearTimers() {
    if (countdownTimer) clearInterval(countdownTimer);
    if (revealTimer) clearInterval(revealTimer);
    countdownTimer = null;
    revealTimer = null;
    countdownEl.classList.add('hidden');
    countdownEl.textContent = '';
  }

  function resetPicker() {
    clearTimers();
    locked = false;
    stableTouchIds = [];
    latestTouches = [];
    pointsLayer.innerHTML = '';
    resultEl.innerHTML = '';
    resultEl.classList.add('hidden');
    resetBtn.classList.add('hidden');
    shuffleBtn.classList.add('hidden');
    guideTitle.textContent = '먼저 팀 수를 골라주세요';
    guideText.textContent = '2~6팀 중 원하는 팀 수를 선택하세요.';
    renderTeamButtons();
  }

  function renderTeamButtons() {
    [...teamCountButtons.querySelectorAll('button')].forEach(button => {
      button.classList.toggle('active', Number(button.dataset.count) === teamCount);
    });
    selectedCountEl.textContent = `${teamCount}팀`;
  }

  function selectTeamCount(count) {
    if (locked) return;
    teamCount = Math.max(2, Math.min(6, Number(count) || 2));
    renderTeamButtons();
    guideTitle.textContent = `${teamCount}팀으로 나눌 준비 완료!`;
    guideText.textContent = '모두 한 손가락씩 화면에 올려주세요.';
    resultEl.classList.add('hidden');
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
        el.className = 'team-touch-point';
        el.dataset.touchId = id;
        pointsLayer.appendChild(el);
      }
      el.textContent = index + 1;
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
    clearTimers();
    stableTouchIds = [...touches].map(t => t.identifier).sort((a, b) => a - b);
    let count = 3;
    countdownEl.textContent = count;
    countdownEl.classList.remove('hidden');
    guideTitle.textContent = `${touches.length}명 감지!`;
    guideText.textContent = '손가락을 그대로 유지하세요.';
    countdownTimer = setInterval(() => {
      if (!sameTouchSet(latestTouches)) {
        clearTimers();
        stableTouchIds = [];
        guideTitle.textContent = latestTouches.length >= 2 ? `${latestTouches.length}명 감지!` : '2명 이상 손가락을 올려주세요';
        guideText.textContent = '모두 올리면 다시 추첨합니다.';
        return;
      }
      count -= 1;
      if (count > 0) {
        countdownEl.textContent = count;
      } else {
        clearTimers();
        revealTeams();
      }
    }, 700);
  }

  function shuffledTeams(playerCount) {
    const ids = Array.from({ length: playerCount }, (_, i) => i + 1);
    for (let i = ids.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [ids[i], ids[j]] = [ids[j], ids[i]];
    }
    const teams = Array.from({ length: teamCount }, () => []);
    ids.forEach((player, index) => teams[index % teamCount].push(player));
    return teams;
  }

  function revealTeams() {
    if (latestTouches.length < teamCount || latestTouches.length < 2) return;
    locked = true;
    const playerCount = latestTouches.length;
    const teams = shuffledTeams(playerCount);
    const teamByPlayer = new Map();
    teams.forEach((players, teamIndex) => players.forEach(player => teamByPlayer.set(player, teamIndex)));

    const pointEls = [...pointsLayer.children];
    pointEls.forEach((el, index) => {
      el.classList.remove('is-team-result');
      el.classList.add('is-shuffling');
      el.dataset.player = String(index + 1);
    });

    guideTitle.textContent = '🎲 운명의 팀을 섞는 중...';
    guideText.textContent = '이번 판의 팀 운명은 과연?';
    let tick = 0;
    revealTimer = setInterval(() => {
      pointEls.forEach((el, index) => {
        el.textContent = TEAM_NAMES[(index + tick) % teamCount];
      });
      tick += 1;
      if (tick >= 7) {
        clearTimers();
        pointEls.forEach((el, index) => {
          const player = index + 1;
          const teamIndex = teamByPlayer.get(player);
          el.classList.remove('is-shuffling');
          el.classList.add('is-team-result', `team-${teamIndex + 1}`);
          el.textContent = TEAM_NAMES[teamIndex];
        });
        renderResult(teams);
      }
    }, 120);
  }

  function renderResult(teams) {
    resultEl.innerHTML = `<div class="team-result-heading"><span>🎉 팀 배정 완료!</span><b>${teams.flat().length}명 · ${teamCount}팀</b></div>`;
    const grid = document.createElement('div');
    grid.className = 'team-result-grid';
    teams.forEach((players, index) => {
      const card = document.createElement('article');
      card.className = `team-result-card team-result-${index + 1}`;
      card.innerHTML = `<span class="team-result-name">${TEAM_NAMES[index]}</span><strong>${players.map(player => `#${player}`).join(' · ')}</strong><small>${players.length}명</small>`;
      grid.appendChild(card);
    });
    resultEl.appendChild(grid);
    resultEl.classList.remove('hidden');
    guideTitle.textContent = '팀이 정해졌어요!';
    guideText.textContent = '마음에 안 들면 다시 섞어보세요.';
    resetBtn.classList.remove('hidden');
    shuffleBtn.classList.remove('hidden');
    if (navigator.vibrate) navigator.vibrate([70, 40, 70, 40, 180]);
  }

  function handleTouches(event) {
    event.preventDefault();
    if (locked) return;
    latestTouches = [...event.touches];
    renderTouches(latestTouches);
    if (latestTouches.length < 2) {
      clearTimers();
      stableTouchIds = [];
      guideTitle.textContent = latestTouches.length === 1 ? '한 명 더 올려주세요' : `${teamCount}팀으로 나눌 준비!`;
      guideText.textContent = '모두 한 손가락씩 올려주세요.';
      return;
    }
    if (latestTouches.length < teamCount) {
      clearTimers();
      stableTouchIds = [];
      guideTitle.textContent = `${teamCount}팀 · ${latestTouches.length}명 감지`;
      guideText.textContent = `최소 ${teamCount}명부터 팀을 나눌 수 있어요.`;
      return;
    }
    if (!countdownTimer && !sameTouchSet(latestTouches)) beginCountdown(latestTouches);
  }

  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  teamCountButtons.addEventListener('click', event => {
    const button = event.target.closest('button[data-count]');
    if (button) selectTeamCount(button.dataset.count);
  });
  resetBtn.addEventListener('click', resetPicker);
  shuffleBtn.addEventListener('click', () => {
    if (latestTouches.length >= teamCount) revealTeams();
  });
  modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal(); });
  ['touchstart', 'touchmove', 'touchend', 'touchcancel'].forEach(type => arena.addEventListener(type, handleTouches, { passive: false }));
})();
