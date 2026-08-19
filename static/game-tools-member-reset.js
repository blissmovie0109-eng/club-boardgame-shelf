(() => {
  const STORAGE_KEY = 'kiribo-game-tools-v1';

  function addMemberResetButton() {
    const actions = document.querySelector('#gameToolsModal .game-tool-actions');
    if (!actions || actions.querySelector('#scoreMemberReset')) return;

    const scoreReset = actions.querySelector('#scoreReset');
    if (!scoreReset) return;

    const button = document.createElement('button');
    button.id = 'scoreMemberReset';
    button.className = 'game-tool-secondary';
    button.type = 'button';
    button.textContent = '팀원 초기화';
    scoreReset.insertAdjacentElement('beforebegin', button);

    button.addEventListener('click', () => {
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
        if (!saved || !Array.isArray(saved.scoreTeams)) return;

        saved.scoreTeams = saved.scoreTeams.map((team) => ({
          ...team,
          members: [],
        }));

        localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
        window.location.reload();
      } catch (error) {
        console.warn('점수판 팀원 정보를 초기화하지 못했습니다.', error);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addMemberResetButton, { once: true });
  } else {
    addMemberResetButton();
  }
})();
