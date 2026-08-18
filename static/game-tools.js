(() => {
  const pickerTools = document.querySelector('.picker-tools');
  if (!pickerTools) return;

  pickerTools.classList.add('game-tools-ready');
  if (!document.querySelector('#gameToolsOpen')) {
    const buttonMarkup = `<button id="gameToolsOpen" class="game-tools-open" type="button"><span class="score-orb">📊</span><span><b>점수 · 팀 나누기</b><small>2~6팀 게임 도구</small></span></button>`;
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
            <h2 id="gameToolsTitle">📊 점수판 · 팀 나누기</h2>
            <p>팀을 나누고 바로 점수를 기록해보세요.</p>
          </div>
          <div class="game-tools-tabs" role="tablist">
            <button type="button" class="active" data-game-tool-tab="score" role="tab" aria-selected="true">점수판</button>
            <button type="button" data-game-tool-tab="team" role="tab" aria-selected="false">팀 나누기</button>
          </div>
          <section class="game-tool-panel" data-game-tool-panel="score">
            <div class="game-tool-toolbar">
              <div class="game-tool-toolbar-copy"><h3>점수판</h3><p>2~6팀의 이름과 점수를 자유롭게 관리합니다.</p></div>
              <div class="game-tool-actions">
                <label>팀 수 <select id="scoreTeamCount">${[2,3,4,5,6].map((n) => `<option value="${n}">${n}팀</option>`).join('')}</select></label>
                <button id="scoreReset" class="game-tool-secondary" type="button">점수 0으로</button>
              </div>
            </div>
            <div id="scoreBoard" class="score-board"></div>
          </section>
          <section class="game-tool-panel hidden" data-game-tool-panel="team">
            <div class="game-tool-toolbar">
              <div class="game-tool-toolbar-copy"><h3>팀 나누기</h3><p>균등하게 섞은 뒤 원하는 사람을 다른 팀으로 옮길 수 있습니다.</p></div>
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
  const scoreTeamCount = modal.querySelector('#scoreTeamCount');
  const scoreBoard = modal.querySelector('#scoreBoard');
  const scoreReset = modal.querySelector('#scoreReset');
  const memberInput = modal.querySelector('#teamMemberInput');
  const splitTeamCount = modal.querySelector('#splitTeamCount');
  const splitButton = modal.querySelector('#splitTeams');
  const splitResult = modal.querySelector('#splitResult');
  const splitEmpty = modal.querySelector('#splitEmpty');
  const applySplit = modal.querySelector('#applySplitToScore');

  const STORAGE_KEY = 'kiribo-game-tools-v1';
  const MIN_TEAMS = 2;
  const MAX_TEAMS = 6;

  const defaultTeam = (index) => ({ name: `${index + 1}팀`, score: 0, members: [] });

  let state = {
    scoreTeams: Array.from({ length: 2 }, (_, index) => defaultTeam(index)),
    splitTeamCount: 2,
    splitTeamNames: ['1팀', '2팀'],
    splitAssignments: [],
    memberDraft: '',
  };

  function clampTeamCount(value) {
    const count = Number(value) || MIN_TEAMS;
    return Math.max(MIN_TEAMS, Math.min(MAX_TEAMS, count));
  }

  function escapeHtml(value = '') {
    return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }

  function normalizeScoreTeams(value) {
    if (!Array.isArray(value)) return null;
    const count = clampTeamCount(value.length);
    const normalized = [];
    for (let index = 0; index < count; index += 1) {
      const source = value[index] || {};
      normalized.push({
        name: String(source.name || `${index + 1}팀`).slice(0, 30),
        score: Number.isFinite(Number(source.score)) ? Number(source.score) : 0,
        members: Array.isArray(source.members) ? source.members.map((name) => String(name).slice(0, 40)).filter(Boolean) : [],
      });
    }
    return normalized;
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || typeof saved !== 'object') return;
      const scoreTeams = normalizeScoreTeams(saved.scoreTeams);
      if (scoreTeams) state.scoreTeams = scoreTeams;
      state.splitTeamCount = clampTeamCount(saved.splitTeamCount || 2);
      state.splitTeamNames = Array.isArray(saved.splitTeamNames)
        ? saved.splitTeamNames.slice(0, state.splitTeamCount).map((name, index) => String(name || `${index + 1}팀`).slice(0, 30))
        : [];
      while (state.splitTeamNames.length < state.splitTeamCount) state.splitTeamNames.push(`${state.splitTeamNames.length + 1}팀`);
      state.splitAssignments = Array.isArray(saved.splitAssignments)
        ? saved.splitAssignments.slice(0, state.splitTeamCount).map((team) => Array.isArray(team)
            ? team.map((member, memberIndex) => ({
                id: String(member?.id || `saved-${Date.now()}-${memberIndex}-${Math.random()}`),
                name: String(member?.name || '').slice(0, 40),
              })).filter((member) => member.name)
            : [])
        : [];
      while (state.splitAssignments.length < state.splitTeamCount && state.splitAssignments.length) state.splitAssignments.push([]);
      state.memberDraft = String(saved.memberDraft || '').slice(0, 2000);
    } catch (error) {
      console.warn('게임 도구 상태를 불러오지 못했습니다.', error);
    }
  }

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
    catch (error) { console.warn('게임 도구 상태를 저장하지 못했습니다.', error); }
  }

  function setActiveTab(name) {
    tabButtons.forEach((button) => {
      const active = button.dataset.gameToolTab === name;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    panels.forEach((panel) => panel.classList.toggle('hidden', panel.dataset.gameToolPanel !== name));
  }

  function resizeScoreTeams(count) {
    const target = clampTeamCount(count);
    const next = state.scoreTeams.slice(0, target);
    while (next.length < target) next.push(defaultTeam(next.length));
    state.scoreTeams = next;
    renderScoreBoard();
    saveState();
  }

  function renderScoreBoard() {
    scoreTeamCount.value = String(state.scoreTeams.length);
    scoreBoard.innerHTML = state.scoreTeams.map((team, index) => {
      const members = team.members.length
        ? `<div class="score-team-members">${team.members.map((name) => `<span>${escapeHtml(name)}</span>`).join('')}</div>`
        : '<div class="score-team-members muted-members">팀원을 나누면 여기에 표시됩니다.</div>';
      return `<article class="score-team-card" data-score-team="${index}">
        <div class="score-team-heading">
          <span class="team-number">TEAM ${index + 1}</span>
          <input class="score-team-name" data-score-team-name="${index}" value="${escapeHtml(team.name)}" maxlength="30" aria-label="${index + 1}팀 이름">
        </div>
        ${members}
        <div class="score-value-row">
          <button type="button" data-score-delta="-5" aria-label="5점 빼기">−5</button>
          <button type="button" data-score-delta="-1" aria-label="1점 빼기">−1</button>
          <input class="score-value" data-score-value="${index}" type="number" step="1" value="${Number(team.score)}" aria-label="${escapeHtml(team.name)} 점수">
          <button type="button" data-score-delta="1" aria-label="1점 더하기">+1</button>
          <button type="button" data-score-delta="5" aria-label="5점 더하기">+5</button>
        </div>
      </article>`;
    }).join('');
  }

  function ensureSplitArrays(count) {
    const target = clampTeamCount(count);
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
    const teamCount = clampTeamCount(splitTeamCount.value);
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
    state.scoreTeams = state.splitAssignments.map((members, index) => ({
      name: state.splitTeamNames[index] || `${index + 1}팀`,
      score: 0,
      members: members.map((member) => member.name),
    }));
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
  memberInput.value = state.memberDraft;
  splitTeamCount.value = String(state.splitTeamCount);
  renderScoreBoard();
  renderSplitResult();

  openButton.addEventListener('click', openModal);
  closeButton.addEventListener('click', closeModal);
  modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal(); });
  tabButtons.forEach((button) => button.addEventListener('click', () => setActiveTab(button.dataset.gameToolTab)));
  scoreTeamCount.addEventListener('change', () => resizeScoreTeams(scoreTeamCount.value));
  scoreReset.addEventListener('click', () => {
    state.scoreTeams.forEach((team) => { team.score = 0; });
    renderScoreBoard();
    saveState();
  });
  scoreBoard.addEventListener('click', (event) => {
    const button = event.target.closest('[data-score-delta]');
    if (!button) return;
    const card = button.closest('[data-score-team]');
    const teamIndex = Number(card?.dataset.scoreTeam);
    if (!Number.isInteger(teamIndex) || !state.scoreTeams[teamIndex]) return;
    state.scoreTeams[teamIndex].score += Number(button.dataset.scoreDelta) || 0;
    renderScoreBoard();
    saveState();
  });
  scoreBoard.addEventListener('input', (event) => {
    if (event.target.matches('[data-score-team-name]')) {
      const teamIndex = Number(event.target.dataset.scoreTeamName);
      if (state.scoreTeams[teamIndex]) {
        state.scoreTeams[teamIndex].name = event.target.value.slice(0, 30) || `${teamIndex + 1}팀`;
        saveState();
      }
    }
  });
  scoreBoard.addEventListener('change', (event) => {
    if (event.target.matches('[data-score-value]')) {
      const teamIndex = Number(event.target.dataset.scoreValue);
      if (state.scoreTeams[teamIndex]) {
        const nextScore = Number(event.target.value);
        state.scoreTeams[teamIndex].score = Number.isFinite(nextScore) ? nextScore : 0;
        renderScoreBoard();
        saveState();
      }
    }
  });
  memberInput.addEventListener('input', () => { state.memberDraft = memberInput.value.slice(0, 2000); saveState(); });
  splitTeamCount.addEventListener('change', () => { ensureSplitArrays(splitTeamCount.value); renderSplitResult(); saveState(); });
  splitButton.addEventListener('click', splitMembers);
  applySplit.addEventListener('click', applySplitToScoreboard);
  splitResult.addEventListener('input', (event) => {
    if (!event.target.matches('[data-split-team-name]')) return;
    const teamIndex = Number(event.target.dataset.splitTeamName);
    if (!Number.isInteger(teamIndex)) return;
    state.splitTeamNames[teamIndex] = event.target.value.slice(0, 30) || `${teamIndex + 1}팀`;
    saveState();
  });
  splitResult.addEventListener('change', (event) => {
    if (!event.target.matches('[data-move-member]')) return;
    const fromTeam = Number(event.target.dataset.fromTeam);
    const toTeam = Number(event.target.value);
    if (fromTeam === toTeam) return;
    moveMember(event.target.dataset.moveMember, fromTeam, toTeam);
  });
})();
