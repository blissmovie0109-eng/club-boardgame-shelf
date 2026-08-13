(() => {
  if (!location.pathname.startsWith('/admin') || location.pathname.startsWith('/admin/login')) return;

  const anchor = document.querySelector('.topline');
  if (!anchor || document.getElementById('backupPanel')) return;

  const csrf = document.querySelector('input[name="_csrf_token"]')?.value || '';
  const panel = document.createElement('section');
  panel.id = 'backupPanel';
  panel.className = 'panel backup-panel';
  panel.innerHTML = `
    <div class="backup-heading">
      <div>
        <span class="backup-kicker">안전장치</span>
        <h2>💾 전체 데이터 백업 & 복원</h2>
        <p>게임 정보와 본판·확장 연결을 JSON 파일로 보관합니다. 복원은 백업에 없는 현재 게임을 삭제하지 않습니다.</p>
      </div>
      <a class="backup-download" href="/admin/backup/download">↓ 전체 백업 다운로드</a>
    </div>
    <form class="backup-restore-form" method="post" action="/admin/backup/restore" enctype="multipart/form-data">
      <input type="hidden" name="_csrf_token" value="${csrf.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}">
      <label class="backup-file-label">
        <span>백업 파일 선택</span>
        <input type="file" name="backup_file" accept=".json,application/json" required>
      </label>
      <button type="submit" class="backup-restore-button">♻️ 백업에서 복원</button>
      <small>복원 시 같은 게임은 백업 내용으로 갱신되고, 사라진 게임은 다시 추가됩니다. 현재 DB에만 있는 게임은 그대로 유지됩니다.</small>
    </form>
  `;

  panel.querySelector('.backup-restore-form').addEventListener('submit', event => {
    const file = panel.querySelector('input[type="file"]').files[0];
    if (!file) {
      event.preventDefault();
      return;
    }
    if (!confirm(`선택한 백업 파일(${file.name})로 복원할까요?\n\n현재 DB에만 있는 게임은 삭제되지 않습니다.`)) {
      event.preventDefault();
    }
  });

  anchor.insertAdjacentElement('afterend', panel);
})();
