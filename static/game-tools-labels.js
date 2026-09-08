(() => {
  const updateLabels = () => {
    const openButton = document.querySelector('#gameToolsOpen');
    if (openButton) {
      const title = openButton.querySelector('b');
      const subtitle = openButton.querySelector('small');
      if (title) title.textContent = '점수판 · 팀 나누기(수동)';
      if (subtitle) subtitle.textContent = '2~6팀 게임 도구';
    }

    const modal = document.querySelector('#gameToolsModal');
    if (!modal) return;

    const title = modal.querySelector('#gameToolsTitle');
    if (title) title.textContent = '📊 점수판 · 팀 나누기(수동)';

    const teamTab = modal.querySelector('[data-game-tool-tab="team"]');
    if (teamTab) teamTab.textContent = '팀 나누기(수동)';

    const teamHeading = modal.querySelector('[data-game-tool-panel="team"] h3');
    if (teamHeading) teamHeading.textContent = '팀 나누기(수동)';

    const teamDescription = modal.querySelector('[data-game-tool-panel="team"] .game-tool-toolbar-copy p');
    if (teamDescription) teamDescription.textContent = '참가자 이름을 직접 입력해 원하는 팀으로 나눕니다.';
  };

  updateLabels();
  const observer = new MutationObserver(updateLabels);
  observer.observe(document.body, { childList: true, subtree: true });
})();
