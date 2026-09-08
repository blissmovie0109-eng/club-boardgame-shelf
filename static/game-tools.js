(() => {
  const pickerTools = document.querySelector('.picker-tools');
  if (!pickerTools) return;

  pickerTools.classList.add('game-tools-ready');
  if (!document.querySelector('#gameToolsOpen')) {
    const buttonMarkup = `<button id="gameToolsOpen" class="game-tools-open" type="button"><span class="score-orb">📊</span><span><b>점수판 · 팀 나누기(수동)</b><small>팀/개인 점수 + 수동 팀 구성</small></span></button>`;
    const randomButton = pickerTools.querySelector('#randomPick');
    if (randomButton) randomButton.insertAdjacentHTML('beforebegin', buttonMarkup);
    else pickerTools.insertAdjacentHTML('beforeend', buttonMarkup);
  }

  if (!document.querySelector('#gameToolsModal')) {
    document.body.insertAdjacentHTML('beforeend', `
      <div id="gameToolsModal" class="game-tools-modal hidden" role="dialog" aria-modal="true" aria-labelledby="gameToolsTitle">
        <div class="game-tools-shell">
          <button id="gameToolsClose" class="game-tools-close" type="button" aria-label="게임 도구 닫기">×</button>
          <div class="game-tools-heading">
            <span class="game-tools-kicker">BOARD GAME TOOL</span>
            <h2 id="gameToolsTitle">📊 점수판 · 팀 나누기(수동)</h2>
            <p>팀 게임은 팀별로, 파티게임은 개인별로 점수를 기록해보세요.</p>
          </div>
          <div class="game-tools-tabs" role="tablist">
            <button type="button" class="active" data-game-tool-tab="score" role="tab" aria-selected="true">점수판</button>
            <button type="button" data-game-tool-tab="team" role="tab" aria-selected="false">팀 나누기(수동)</button>
          </div>
          <section class="game-tool-panel" data-game-tool-panel="score">
            <div class="game-tool-toolbar">
              <div class="game-tool-toolbar-copy"><h3>점수판</h3><p>팀 게임 또는 개인 점수판으로 사용할 수 있습니다.</p></div>
              <div class="game-tool-actions">
                <div class="score-mode-tabs" role="group" aria-label="점수판 방식">
                  <button type="button" class="active" data-score-mode="team">팀</button>
                  <button type="button" data-score-mode="individual">개인</button>
                </div>
                <label id="scoreCountLabel">팀 수 <select id="scoreCount"></select></label>
                <button id="scoreReset" class="game-tool-secondary" type="button">점수 0으로</button>
              </div>
            </div>
            <div id="scoreBoard" class="score-board"></div>
          </section>
          <section class="game-tool-panel hidden" data-game-tool-panel="team">
            <div class="game-tool-toolbar">
              <div class="game-tool-toolbar-copy"><h3>팀 나누기(수동)</h3><p>참가자 이름을 입력한 뒤 균등하게 섞고, 원하는 사람은 다른 팀으로 옮길 수 있습니다.</p></div>
            </div>
            <div class="team-split-input">
              <label class="team-member-field">참가자 이름 <textarea id="teamMemberInput" placeholder="예: 민수, 지영, 철수\n또는 한 줄에 한 명씩 입력"></textarea></label>
              <div class="team-split-side">
                <label>팀 수 <select id="splitTeamCount">${[2,3,4,5,6].map((n) => `<option value="${n}">${n}팀</option>`).join('')}</select></label>
                <button id="splitTeams" class="game-tool-primary" type="button">🎲 팀 나누기</button>
              </div>
            </div>
            <div id="splitEmpty" class="split-empty">참가자 이름을 입력하고 팀 나누기를 눌러주세요.</div>
            <div id="splitResult" class="split-result hidden"></div>
            <div class="apply-split-row"><button id="applySplitToScore" class="game-tool-primary hidden" type="button">이 팀으로 점수판 시작 →</button></div>
          </section>
        </div>
      </div>`);
  }

  const openButton = document.querySelector('#gameToolsOpen');
  const modal = document.querySelector('#gameToolsModal');
  if (!openButton || !modal) return;

  const closeButton = modal.querySelector('#gameToolsClose');
  const tabButtons = [...modal.querySelectorAll('[data-game-tool-tab]')];
  const panels = [...modal.querySelectorAll('[data-game-tool-panel]')];
  const scoreBoard = modal.querySelector('#scoreBoard');
  const scoreCount = modal.querySelector('#scoreCount');
  const scoreCountLabel = modal.querySelector('#scoreCountLabel');
  const scoreReset = modal.querySelector('#scoreReset');
  const scoreModeButtons = [...modal.querySelectorAll('[data-score-mode]')];
  const memberInput = modal.querySelector('#teamMemberInput');
  const splitTeamCount = modal.querySelector('#splitTeamCount');
  const splitButton = modal.querySelector('#splitTeams');
  const splitResult = modal.querySelector('#splitResult');
  const splitEmpty = modal.querySelector('#splitEmpty');
  const applySplit = modal.querySelector('#applySplitToScore');

  const STORAGE_KEY = 'kiribo-game-tools-v2';
  const MIN_TEAMS = 2;
  const MAX_TEAMS = 6;
  const MAX_INDIVIDUALS = 12;

  const defaultEntry = (index, mode) => ({ name: mode === 'individual' ? `${index + 1}번` : `${index + 1}팀`, score: 0, members: [] });

  let state = {
    scoreMode: 'team',
    scoreEntries: Array.from({ length: 2 }, (_, index) => defaultEntry(index, 'team')),
    splitTeamCount: 2,
    splitTeamNames: ['1팀', '2팀'],
    splitAssignments: [],
    memberDraft: '',
  };

  function clampCount(value, min, max) {
    const count = Number(value) || min;
    return Math.max(min, Math.min(max, count));
  }

  function escapeHtml(value = '') {
    return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }

  function countOptions(mode) {
    const max = mode === 'individual' ? MAX_INDIVIDUALS : MAX_TEAMS;
    return Array.from({ length: max - MIN_TEAMS + 1 }, (_, i) => i + MIN_TEAMS);
      
  }

  function ensureScoreEntries(count, mode = state.scoreMode) {
    const max = mode === 'individual' ? MAX_INDIVIDUALS : MAX_TEAMS;
    const target = clampCount(count, MIN_TEAMS, max);
    const next = state.scoreEntries.slice(0, target).map((entry, index) => ({
      name: String(entry?.name || defaultEntry(index, mode).name).slice(0, 30),
      score: Number.isFinite(Number(entry?.score)) ? Number(entry.score) : 0,
      members: Array.isArray(entry?.members) ? entry.members.map((name) => String(name).slice(0, 40)).filter(Boolean) : [],
    }));
    while (next.length < target) next.push(defaultEntry(next.length, mode));
    if (mode === 'individual') next.forEach((entry, index) => { if (!entry.name || /팀$/.test(entry.name)) entry.name = `${index + 1}번`; entry.members = []; });
    state.scoreEntries = next;
    return target;
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || typeof saved !== 'object') return;
      state.scoreMode = saved.scoreMode === 'individual' ? 'individual' : 'team';
      const savedEntries = Array.isArray(saved.scoreEntries) ? saved.scoreEntries : (Array.isArray(saved.scoreTeams) ? saved.scoreTeams : null);
      if (savedEntries) {
        state.scoreEntries = savedEntries.slice(0, MAX_INDIVIDUALS).map((entry, index) => ({
          name: String(entry?.name || `${index + 1}${state.scoreMode === 'individual' ? '번' : '팀'}`).slice(0, 30),
          score: Number.isFinite(Number(entry?.score)) ? Number(entry.score) : 0,
          members: Array.isArray(entry?.members) ? entry.members.map((name) => String(name).slice(0, 40)).filter(Boolean) : [],
        }));
      }
      ensureScoreEntries(state.scoreEntries.length || 2, state.scoreMode);
      state.splitTeamCount = clampCount(saved.splitTeamCount || 2, MIN_TEAMS, MAX_TEAMS);
      state.splitTeamNames = Array.isArray(saved.splitTeamNames) ? saved.splitTeamNames.slice(0, state.splitTeamCount).map((name, index) => String(name || `${index + 1}팀`).slice(0, 30)) : [];
      while (state.splitTeamNames.length < state.splitTeamCount) state.splitTeamNames.push(`${state.splitTeamNames.length + 1}팀`);
      state.splitAssignments = Array.isArray(saved.splitAssignments) ? saved.splitAssignments.slice(0, state.splitTeamCount).map((team) => Array.isArray(team) ? team.map((member, memberIndex) => ({ id: String(member?.id || `saved-${Date.now()}-${memberIndex}-${Math.random()}`), name: String(member?.name || '').slice(0, 40) })).filter((member) => member.name) : []) : [];
      state.memberDraft = String(saved.memberDraft || '').slice(0, 2000);
    } catch (error) {
      console.warn('게임 도구 상태를 불러오지 못했습니다.', error);
    }
  }

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (error) { console.warn('게임 도구 상태를 저장하지 못했습니다.', error); }
  }

  function setActiveTab(name) {
    tabButtons.forEach((button) => {
      const active = button.dataset.gameToolTab === name;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    panels.forEach((panel) => panel.classList.toggle('hidden', panel.dataset.gameToolPanel !== name));
  }

  function renderScoreCountOptions() {
    const max = state.scoreMode === 'individual' ? MAX_INDIVIDUALS : MAX_TEAMS;
    const current = clampCount(state.scoreEntries.length || 2, MIN_TEAMS, max);
    scoreCount.innerHTML = countOptions(state.scoreMode).map((n) => `<option value="${n}">${n}${state.scoreMode === 'individual' ? '명' : '팀'}</option>`).join('');
    scoreCount.value = String(current);
    scoreCountLabel.firstChild.textContent = state.scoreMode === 'individual' ? '인원 수 ' : '팀 수 ';
  }

  function renderScoreBoard() {
    ensureScoreEntries(state.scoreEntries.length || 2, state.scoreMode);
    scoreModeButtons.forEach((button) => button.classList.toggle('active', button.dataset.scoreMode === state.scoreMode));
    renderScoreCountOptions();
    scoreBoard.innerHTML = state.scoreEntries.map((entry, index) => {
      const members = state.scoreMode === 'team'
        ? (entry.members.length ? `<div class="score-team-members">${entry.members.map((name) => `<span>${escapeHtml(name)}</span>`).join('')}</div>` : '<div class="score-team-members muted-members">팀원을 나누면 여기에 표시됩니다.</div>')
        : '';
      return `<article class="score-team-card" data-score-entry="${index}">
        <div class="score-team-heading">
          <span class="team-number">${state.scoreMode === 'individual' ? `PLAYER ${index + 1}` : `TEAM ${index + 1}`}</span>
          <input class="score-team-name" data-score-entry-name="${index}" value="${escapeHtml(entry.name)}" maxlength="30" aria-label="${state.scoreMode === 'individual' ? `${index + 1}번 선수 이름` : `${index + 1}팀 이름`}">
        </div>
        ${members}
        <div class="score-value-row">
          <button type="button" data-score-delta="-5" aria-label="5점 빼기">−5</button>
          <button type="button" data-score-delta="-1" aria-label="1점 빼기">−1</button>
          <input class="score-value" data-score-value="${index}" type="number" step="1" value="${Number(entry.score)}" aria-label="${escapeHtml(entry.name)} 점수">
          <button type="button" data-score-delta="1" aria-label="1점 더하기">+1</button>
          <button type="button" data-score-delta="5" aria-label="5점 더하기">+5</button>
        </div>
      </article>`;
    }).join('');
  }

  function switchScoreMode(mode) {
    state.scoreMode = mode === 'individual' ? 'individual' : 'team';
    const current = state.scoreEntries.length || 2;
    ensureScoreEntries(Math.min(current, state.scoreMode === 'individual' ? MAX_INDIVIDUALS : MAX_TEAMS), state.scoreMode);
    renderScoreBoard();
    saveState();
  }

  function resizeScoreEntries(count) {
    ensureScoreEntries(count, state.scoreMode);
    renderScoreBoard();
    saveState();
  }

  function ensureSplitArrays(count) {
    const target = clampCount(count, MIN_TEAMS, MAX_TEAMS);
    state.splitTeamCount = target;
    state.splitTeamNames = state.splitTeamNames.slice(0, target);
    while (state.splitTeamNames.length < target) state.splitTeamNames.push(`${state.splitTeamNames.length + 1}팀`);
    if (state.splitAssignments.length) {
      const allMembers = state.splitAssignments.flat();
      state.splitAssignments = Array.from({ length: target }, () => []);
      allMembers.forEach((member, index) => state.splitAssignments[index % target].push(member));
    }
  }

  function parseMembers() {
    return String(memberInput.value || '').split(/[\n,]+/).map((name) => name.trim()).filter(Boolean).slice(0, 60);
  }

  function shuffle(items) {
    const next = [...items];
    for (let index = next.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(Math.random() * (index + 1));
      [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
    }
    return next;
  }

  function splitMembers() {
    const names = parseMembers();
    const teamCount = clampCount(splitTeamCount.value, MIN_TEAMS, MAX_TEAMS);
    ensureSplitArrays(teamCount);
    if (names.length < teamCount) {
      splitEmpty.textContent = `팀 수보다 참가자가 적습니다. 최소 ${teamCount}명을 입력해주세요.`;
      splitEmpty.classList.remove('hidden');
      splitResult.classList.add('hidden');
      applySplit.classList.add('hidden');
      return;
    }
    const members = shuffle(names).map((name, index) => ({ id: `member-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`, name }));
    state.splitAssignments = Array.from({ length: teamCount }, () => []);
    members.forEach((member, index) => state.splitAssignments[index % teamCount].push(member));
    state.memberDraft = memberInput.value;
    renderSplitResult();
    saveState();
  }

  function renderSplitResult() {
    splitTeamCount.value = String(state.splitTeamCount);
    memberInput.value = state.memberDraft;
    if (!state.splitAssignments.length) {
      splitResult.classList.add('hidden');
      applySplit.classList.add('hidden');
      splitEmpty.textContent = '참가자 이름을 입력하고 팀 나누기를 눌러주세요.';
      splitEmpty.classList.remove('hidden');
      return;
    }
    splitEmpty.classList.add('hidden');
    splitResult.classList.remove('hidden');
    applySplit.classList.remove('hidden');
    splitResult.innerHTML = state.splitAssignments.map((members, teamIndex) => {
      const options = state.splitTeamNames.map((teamName, optionIndex) => `<option value="${optionIndex}"${optionIndex === teamIndex ? ' selected' : ''}>${escapeHtml(teamName)}</option>`).join('');
      const memberRows = members.length
        ? members.map((member) => `<div class="split-member-row"><span class="split-member-name">${escapeHtml(member.name)}</span><label>이동 <select data-move-member="${escapeHtml(member.id)}" data-from-team="${teamIndex}">${options}</select></label></div>`).join('')
        : '<div class="split-no-members">배정된 사람이 없습니다.</div>';
      return `<article class="split-team-card" data-split-team="${teamIndex}"><div class="split-team-title"><span class="team-number">TEAM ${teamIndex + 1}</span><input data-split-team-name="${teamIndex}" value="${escapeHtml(state.splitTeamNames[teamIndex])}" maxlength="30" aria-label="${teamIndex + 1}팀 이름"><b>${members.length}명</b></div><div class="split-member-list">${memberRows}</div></article>`;
    }).join('');
  }

  function moveMember(memberId, fromTeam, toTeam) {
    const source = state.splitAssignments[fromTeam];
    if (!source || !state.splitAssignments[toTeam]) return;
    const memberIndex = source.findIndex((member) => member.id === memberId);
    if (memberIndex < 0) return;
    const [member] = source.splice(memberIndex, 1);
    state.splitAssignments[toTeam].push(member);
    renderSplitResult();
    saveState();
  }

  function applySplitToScoreboard() {
    state.scoreMode = 'team';
    state.scoreEntries = state.splitAssignments.map((members, index) => ({ name: state.splitTeamNames[index] || `${index + 1}팀`, score: 0, members: members.map((member) => member.name) }));
    renderScoreBoard();
    saveState();
    setActiveTab('score');
  }

  function openModal() {
    modal.classList.remove('hidden');
    document.body.classList.add('game-tools-opened');
    renderScoreBoard();
    renderSplitResult();
    closeButton.focus();
  }

  function closeModal() {
    modal.classList.add('hidden');
    document.body.classList.remove('game-tools-opened');
    openButton.focus();
  }

  loadState();
  renderScoreBoard();
  renderSplitResult();

  openButton.addEventListener('click', openModal);
  closeButton.addEventListener('click', closeModal);
  modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal(); });

  tabButtons.forEach((button) => button.addEventListener('click', () => setActiveTab(button.dataset.gameToolTab)));
  scoreModeButtons.forEach((button) => button.addEventListener('click', () => switchScoreMode(button.dataset.scoreMode)));
  scoreCount.addEventListener('change', () => resizeScoreEntries(scoreCount.value));
  scoreReset.addEventListener('click', () => { state.scoreEntries.forEach((entry) => { entry.score = 0; }); renderScoreBoard(); saveState(); });

  scoreBoard.addEventListener('click', (event) => {
    const button = event.target.closest('[data-score-delta]');
    if (!button) return;
    const card = button.closest('[data-score-entry]');
    const index = Number(card?.dataset.scoreEntry);
    if (!Number.isInteger(index) || !state.scoreEntries[index]) return;
    state.scoreEntries[index].score += Number(button.dataset.scoreDelta || 0);
    const input = card.querySelector('[data-score-value]');
    if (input) input.value = String(state.scoreEntries[index].score);
    saveState();
  });

  scoreBoard.addEventListener('input', (event) => {
    const nameInput = event.target.closest('[data-score-entry-name]');
    if (nameInput) {
      const index = Number(nameInput.dataset.scoreEntryName);
      if (state.scoreEntries[index]) { state.scoreEntries[index].name = nameInput.value.slice(0, 30); saveState(); }
      return;
    }
    const scoreInput = event.target.closest('[data-score-value]');
    if (scoreInput) {
      const index = Number(scoreInput.dataset.scoreValue);
      if (state.scoreEntries[index]) { state.scoreEntries[index].score = Number(scoreInput.value) || 0; saveState(); }
    }
  });

  splitButton.addEventListener('click', splitMembers);
  splitTeamCount.addEventListener('change', () => { ensureSplitArrays(splitTeamCount.value); renderSplitResult(); saveState(); });
  memberInput.addEventListener('input', () => { state.memberDraft = memberInput.value; saveState(); });
  splitResult.addEventListener('change', (event) => {
    const move = event.target.closest('[data-move-member]');
    if (move) moveMember(move.dataset.moveMember, Number(move.dataset.fromTeam), Number(move.value));
    const teamName = event.target.closest('[data-split-team-name]');
    if (teamName) { state.splitTeamNames[Number(teamName.dataset.splitTeamName)] = teamName.value.slice(0, 30); saveState(); }
  });
  splitResult.addEventListener('input', (event) => {
    const teamName = event.target.closest('[data-split-team-name]');
    if (teamName) { state.splitTeamNames[Number(teamName.dataset.splitTeamName)] = teamName.value.slice(0, 30); saveState(); }
  });
  applySplit.addEventListener('click', applySplitToScoreboard);
})();
