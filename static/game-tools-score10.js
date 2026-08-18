(() => {
  function syncScoreButtons() {
    const scoreBoard = document.querySelector('#scoreBoard');
    if (!scoreBoard) return;

    scoreBoard.querySelectorAll('.score-value-row').forEach((row) => {
      row.querySelector('[data-score-delta="-5"]')?.remove();

      if (row.querySelector('[data-score-delta="10"]')) return;
      const plusFive = row.querySelector('[data-score-delta="5"]');
      if (!plusFive) return;

      const plusTen = document.createElement('button');
      plusTen.type = 'button';
      plusTen.dataset.scoreDelta = '10';
      plusTen.setAttribute('aria-label', '10점 더하기');
      plusTen.textContent = '+10';
      plusFive.insertAdjacentElement('afterend', plusTen);
    });
  }

  function init() {
    syncScoreButtons();
    const scoreBoard = document.querySelector('#scoreBoard');
    if (!scoreBoard) return;

    const observer = new MutationObserver(syncScoreButtons);
    observer.observe(scoreBoard, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
