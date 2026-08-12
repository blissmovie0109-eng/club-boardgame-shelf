(() => {
  const CATEGORY_VALUES = ['전략', '추상', '컬렉터블', '가족', '어린이', '파티', '테마', '워게임', '머더미스터리'];

  function normalizeSiteCategory(value) {
    const text = String(value || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
    if (!text) return '';
    const match = CATEGORY_VALUES.find(category => text === category || text.startsWith(category + ' ') || text.startsWith(category + ',') || text.startsWith(category + '/'));
    if (!match) return '';
    return match === '가족' ? '파티' : match;
  }

  function normalizeCategoryInputs(root = document) {
    root.querySelectorAll?.('input[name="category"]').forEach(input => {
      const normalized = normalizeSiteCategory(input.value);
      if (normalized) input.value = normalized;
    });
    root.querySelectorAll?.('option[value="가족"]').forEach(option => option.remove());
  }

  function normalizeVisibleCategory(root = document) {
    root.querySelectorAll?.('.category-row .tag, .detail-tags span').forEach(el => {
      if ((el.textContent || '').trim() === '가족') el.textContent = '파티';
    });
  }

  function extractBoardlifeCategory(plain, html) {
    const combinedText = String(plain || '');
    const direct = combinedText.match(/카테고리\s*[:：]?\s*(전략|추상|컬렉터블|가족|어린이|파티|테마|워게임|머더미스터리)(?=\s|[,·/|]|$)/);
    if (direct) return direct[1] === '가족' ? '파티' : direct[1];

    if (html) {
      try {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const nodes = [...doc.querySelectorAll('body *')];
        for (const node of nodes) {
          const text = (node.textContent || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
          if (!text || text.length > 140 || !text.includes('카테고리')) continue;
          const match = text.match(/카테고리\s*[:：]?\s*(전략|추상|컬렉터블|가족|어린이|파티|테마|워게임|머더미스터리)(?=\s|[,·/|]|$)/);
          if (match) return match[1] === '가족' ? '파티' : match[1];
        }
      } catch (e) {}
    }
    return '';
  }

  function validRating(value) {
    const number = Number.parseFloat(String(value || '').replace(',', '.'));
    if (!Number.isFinite(number) || number <= 0 || number > 10) return '';
    return String(Math.round(number * 100) / 100);
  }

  function extractVisibleBoardlifeRating(plain, html) {
    const text = String(plain || '').replace(/\u00a0/g, ' ');
    const patterns = [
      /★\s*(10(?:\.0+)?|[0-9](?:\.[0-9]+)?)/,
      /(10(?:\.0+)?|[0-9](?:\.[0-9]+)?)\s*전체\s*\d+\s*위/,
      /(?:게임\s*)?평점\s*[:：]?\s*(10(?:\.0+)?|[0-9](?:\.[0-9]+)?)/,
      /(10(?:\.0+)?|[0-9](?:\.[0-9]+)?)\s*\/\s*10(?:\.0+)?/,
    ];
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        const rating = validRating(match[1]);
        if (rating) return rating;
      }
    }

    if (html) {
      try {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const visibleText = (doc.body?.innerText || doc.body?.textContent || '').replace(/\u00a0/g, ' ');
        for (const pattern of patterns) {
          const match = visibleText.match(pattern);
          if (match) {
            const rating = validRating(match[1]);
            if (rating) return rating;
          }
        }

        // ratingValue만 제한적으로 사용합니다. data-score 같은 범용 값은 최대점수 10과 혼동될 수 있어 사용하지 않습니다.
        for (const el of doc.querySelectorAll('[itemprop="ratingValue"], meta[itemprop="ratingValue"]')) {
          const rating = validRating(el.getAttribute('content') || el.textContent || '');
          if (rating) return rating;
        }
      } catch (e) {}
    }
    return '';
  }

  function fixPastePreview(event) {
    const target = event.target;
    if (!target || target.id !== 'boardlifePasteBox') return;

    const plain = event.clipboardData?.getData('text/plain') || '';
    const html = event.clipboardData?.getData('text/html') || '';
    const rating = extractVisibleBoardlifeRating(plain, html);
    const category = extractBoardlifeCategory(plain, html);

    // 기존 파서가 먼저 입력한 뒤 마지막에 정확한 값으로 덮어씁니다.
    setTimeout(() => {
      const ratingInput = document.getElementById('piRating');
      const categoryInput = document.getElementById('piCategory');
      if (rating && ratingInput) ratingInput.value = rating;
      if (category && categoryInput) categoryInput.value = category;

      const status = document.getElementById('pasteStatus');
      if (status) {
        let htmlText = status.innerHTML;
        if (rating) {
          htmlText = /평점\s*[0-9]+(?:\.[0-9]+)?/.test(htmlText)
            ? htmlText.replace(/평점\s*[0-9]+(?:\.[0-9]+)?/, `평점 ${rating}`)
            : htmlText;
        }
        if (category) {
          htmlText = /카테고리\s*(전략|추상|컬렉터블|가족|어린이|파티|테마|워게임|머더미스터리)/.test(htmlText)
            ? htmlText.replace(/카테고리\s*(전략|추상|컬렉터블|가족|어린이|파티|테마|워게임|머더미스터리)/, `카테고리 ${category}`)
            : htmlText;
        }
        status.innerHTML = htmlText;
      }
    }, 0);
  }

  document.addEventListener('paste', fixPastePreview, false);
  document.addEventListener('submit', event => normalizeCategoryInputs(event.target), true);

  function applyAll() {
    normalizeCategoryInputs(document);
    normalizeVisibleCategory(document);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', applyAll);
  else applyAll();

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (!(node instanceof Element)) return;
        normalizeCategoryInputs(node);
        normalizeVisibleCategory(node);
      });
    }
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
})();
