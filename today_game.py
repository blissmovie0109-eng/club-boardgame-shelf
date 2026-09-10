from datetime import datetime, timezone
from flask import jsonify, redirect, render_template_string, request, url_for
from sqlalchemy import String, inspect, text
import app as app_module

app = app_module.app


class TodayGame(app_module.Base):
    __tablename__ = "today_game"
    id = app_module.mapped_column(app_module.Integer, primary_key=True, default=1)
    title = app_module.mapped_column(String(250), nullable=False, default="")
    image_url = app_module.mapped_column(String(1000), nullable=False, default="")
    cafe_url = app_module.mapped_column(String(1000), nullable=False, default="")
    updated_at = app_module.mapped_column(String(40), nullable=False, default="")


app_module.Base.metadata.create_all(app_module.engine)

# Existing installations already have the today_game table. Add the new image field
# without requiring a manual database migration.
try:
    columns = {column["name"] for column in inspect(app_module.engine).get_columns("today_game")}
    if "image_url" not in columns:
        with app_module.engine.begin() as connection:
            connection.execute(text("ALTER TABLE today_game ADD COLUMN image_url VARCHAR(1000) DEFAULT ''"))
except Exception:
    # The normal startup path will still surface a useful database error if the
    # migration cannot be applied; do not prevent the rest of the app from loading.
    pass


def _current(db):
    item = db.get(TodayGame, 1)
    if item is None:
        item = TodayGame(id=1, title="", image_url="", cafe_url="", updated_at="")
        db.add(item)
        db.commit()
    return item


def _safe_image_url(value):
    image_url = app_module.clean_text(value)[:1000]
    if not image_url:
        return ""
    if not (image_url.startswith("https://") or image_url.startswith("http://")):
        return ""
    return image_url


def _safe_cafe_url(value):
    cafe_url = app_module.clean_text(value)[:1000]
    if cafe_url and not (
        cafe_url.startswith("https://cafe.naver.com/")
        or cafe_url.startswith("https://m.cafe.naver.com/")
    ):
        return None
    return cafe_url


@app.route("/api/today-game")
def api_today_game():
    db = app_module.DBSession()
    item = _current(db)
    return jsonify(
        {
            "title": item.title or "",
            "image_url": item.image_url or "",
            "cafe_url": item.cafe_url or "",
            "updated_at": item.updated_at or "",
            "enabled": bool(item.title and item.cafe_url),
        }
    )


@app.route("/admin/today-game", methods=["GET", "POST"])
@app_module.admin_required
def admin_today_game():
    db = app_module.DBSession()
    item = _current(db)
    error = ""

    if request.method == "POST":
        title = app_module.clean_text(request.form.get("title"))[:250]
        image_url = _safe_image_url(request.form.get("image_url"))
        cafe_url = _safe_cafe_url(request.form.get("cafe_url"))

        if cafe_url is None:
            error = "네이버 카페 주소만 입력해 주세요."
        elif not title:
            error = "BoardLife 전체복사에서 게임 이름을 찾지 못했습니다. BoardLife 상세페이지 전체를 다시 복사해 주세요."
        elif not image_url:
            error = "BoardLife 전체복사에서 게임 이미지를 찾지 못했습니다. BoardLife 상세페이지 전체를 다시 복사해 주세요."
        elif not cafe_url:
            error = "네이버 카페 글 주소를 입력해 주세요."
        else:
            item.title = title
            item.image_url = image_url
            item.cafe_url = cafe_url
            item.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            return redirect(url_for("admin_today_game"))

    return render_template_string(ADMIN_HTML, item=item, error=error)


ADMIN_HTML = """<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>오늘의 게임 관리</title>
<style>
body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif;background:#f6f3ed;margin:0;color:#29251f}
.wrap{max-width:780px;margin:auto;padding:28px 18px}.panel{background:#fff;border:1px solid #e7e0d5;border-radius:22px;padding:24px;box-shadow:0 8px 30px #0000000b}
.back{display:inline-block;margin-bottom:16px;color:#6a4cff;text-decoration:none}.kicker{display:inline-block;margin-bottom:7px;color:#8a6a20;font-size:12px;font-weight:900;letter-spacing:.08em}
h1{margin:0 0 8px}p{color:#716a61;line-height:1.6}.error{background:#fff0f0;color:#b42318;padding:12px;border-radius:10px;margin:16px 0}
label{display:block;font-weight:800;margin:20px 0 8px}input{box-sizing:border-box;width:100%;padding:13px 14px;border:1px solid #d9d1c5;border-radius:12px;font:inherit}
.paste-box{min-height:180px;display:grid;place-items:center;text-align:center;padding:20px;border:2px dashed #d7cdbf;border-radius:16px;background:#fbfaf7;color:#82796e;line-height:1.6;cursor:text;outline:none}
.paste-box:focus{border-color:#9a7cff;box-shadow:0 0 0 4px #8b5cf61a}.paste-box.loaded{border-style:solid;border-color:#9ac9a8;background:#f2fbf4;color:#315c47}
.status{margin-top:9px;font-size:13px;color:#82796e}.status.ok{color:#315c47}.hint{font-size:13px;color:#82796e;margin-top:8px}
.preview{display:none;margin-top:18px;padding:14px;border:1px solid #e7e0d5;border-radius:15px;background:#faf8f4;grid-template-columns:100px 1fr;gap:14px;align-items:center}
.preview.show{display:grid}.preview img{width:100px;height:100px;object-fit:cover;border-radius:12px;background:#eee}.preview b{font-size:18px}.preview small{display:block;margin-top:6px;color:#82796e}
button{margin-top:20px;border:0;border-radius:13px;padding:14px 18px;background:#29251f;color:#fff;font-weight:900;font:inherit;cursor:pointer;width:100%}button:disabled{opacity:.45;cursor:not-allowed}
.current{margin-top:24px;padding:16px;background:#faf8f4;border-radius:15px}.current img{width:100%;max-width:220px;aspect-ratio:1;object-fit:cover;border-radius:13px;display:block;margin:12px 0}.current a{color:#6a4cff;font-weight:800}
.steps{margin:18px 0 0;padding-left:22px;color:#5f584f;line-height:1.75}.steps b{color:#29251f}
@media(max-width:560px){.panel{padding:18px}.preview{grid-template-columns:78px 1fr}.preview img{width:78px;height:78px}}
</style>
</head>
<body>
<main class='wrap'>
<a class='back' href='/admin'>← 관리자 페이지로 돌아가기</a>
<section class='panel'>
<span class='kicker'>TODAY'S GAME</span>
<h1>오늘의 게임 설정</h1>
<p>BoardLife 상세페이지는 <b>전체복사</b>만 하면 됩니다. 여기서 게임 이름과 대표 이미지를 자동으로 읽고, 실제 소개 내용은 네이버 카페 글로 연결합니다.</p>
{% if error %}<div class='error'>{{ error }}</div>{% endif %}

<form method='post' id='todayGameForm'>
<input type='hidden' name='_csrf_token' value='{{ csrf_token() }}'>
<input type='hidden' name='title' id='parsedTitle' value='{{ item.title }}'>
<input type='hidden' name='image_url' id='parsedImage' value='{{ item.image_url }}'>

<label>1. BoardLife 상세페이지 전체복사</label>
<div id='boardlifePasteBox' class='paste-box' tabindex='0' role='textbox' aria-label='BoardLife 상세페이지 전체복사 붙여넣기'>
{% if item.title and item.image_url %}현재 {{ item.title }} 정보가 있습니다. 새 BoardLife 페이지를 Ctrl+A → Ctrl+C 후 여기에 Ctrl+V하세요.{% else %}BoardLife 상세페이지에서 Ctrl+A → Ctrl+C 한 뒤 여기에 Ctrl+V하세요.{% endif %}
</div>
<div id='pasteStatus' class='status'>붙여넣으면 게임 이름과 대표 이미지를 자동으로 찾습니다.</div>
<div id='pastePreview' class='preview'>
<img id='previewImage' alt='게임 대표 이미지'>
<div><b id='previewTitle'></b><small>BoardLife에서 자동으로 읽은 정보</small></div>
</div>

<label for='cafeUrl'>2. 네이버 카페 글 주소</label>
<input id='cafeUrl' name='cafe_url' type='url' value='{{ item.cafe_url }}' placeholder='https://cafe.naver.com/... ' required>
<div class='hint'>홈페이지의 큰 오늘의 게임 카드를 누르면 이 글로 이동합니다.</div>

<button id='saveButton' type='submit' {% if not item.title or not item.image_url or not item.cafe_url %}disabled{% endif %}>오늘의 게임 저장</button>
</form>

<ol class='steps'>
<li>BoardLife에서 소개할 게임의 상세페이지를 엽니다.</li>
<li><b>Ctrl+A → Ctrl+C</b>로 페이지 전체를 복사합니다.</li>
<li>위 첫 번째 상자에 <b>Ctrl+V</b>합니다.</li>
<li>두 번째 칸에 네이버 카페 글 주소를 붙여넣고 저장합니다.</li>
</ol>

{% if item.title and item.image_url and item.cafe_url %}
<div class='current'><b>현재 오늘의 게임</b><img src='{{ item.image_url }}' alt=''><strong>{{ item.title }}</strong><p><a href='{{ item.cafe_url }}' target='_blank' rel='noopener noreferrer'>현재 네이버 카페 글 열기 ↗</a></p></div>
{% endif %}
</section>
</main>
<script>
(() => {
  const box = document.getElementById('boardlifePasteBox');
  const status = document.getElementById('pasteStatus');
  const titleInput = document.getElementById('parsedTitle');
  const imageInput = document.getElementById('parsedImage');
  const preview = document.getElementById('pastePreview');
  const previewTitle = document.getElementById('previewTitle');
  const previewImage = document.getElementById('previewImage');
  const saveButton = document.getElementById('saveButton');
  const cafeUrl = document.getElementById('cafeUrl');

  const clean = value => String(value || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
  const absoluteUrl = value => {
    const raw = clean(value);
    if (!raw || raw.startsWith('data:') || raw.startsWith('blob:')) return '';
    if (raw.startsWith('//')) return 'https:' + raw;
    try { return new URL(raw, 'https://boardlife.co.kr/').href; } catch (e) { return ''; }
  };
  const titleClean = value => clean(value)
    .replace(/^보드게임\\s*[:|-]\\s*/i, '')
    .replace(/\\s*[|·-]\\s*(보드라이프|BoardLife).*$/i, '')
    .replace(/\\s+보드게임$/i, '')
    .trim();

  function firstText(doc, selectors) {
    for (const selector of selectors) {
      const node = doc.querySelector(selector);
      const value = clean(node?.getAttribute('content') || node?.textContent || '');
      if (value) return value;
    }
    return '';
  }

  function findImage(doc) {
    const meta = firstText(doc, ['meta[property="og:image"]','meta[name="twitter:image"]']);
    if (meta) return absoluteUrl(meta);
    const images = [...doc.querySelectorAll('img[src], img[data-src], img[data-original]')];
    const scored = images.map(img => {
      const src = absoluteUrl(img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original') || '');
      const alt = clean(img.getAttribute('alt') || '');
      const width = Number(img.getAttribute('width') || 0);
      const height = Number(img.getAttribute('height') || 0);
      let score = 0;
      if (src.includes('/game/') || src.includes('/wys2/')) score += 3;
      if (width >= 200 || height >= 200) score += 2;
      if (alt) score += 1;
      if (/logo|icon|avatar|profile|banner/i.test(alt + ' ' + src)) score -= 3;
      return {src, score};
    }).filter(item => item.src).sort((a,b) => b.score - a.score);
    return scored[0]?.src || '';
  }

  function parseClipboard(html, text) {
    const doc = new DOMParser().parseFromString(html || '<div></div>', 'text/html');
    let title = titleClean(firstText(doc, [
      'meta[property="og:title"]',
      'h1',
      'main h2',
      '[class*="game-title" i]',
      '[class*="game_name" i]',
      '[class*="game-name" i]',
      '[class*="title" i]'
    ]));
    if (!title) title = titleClean(doc.title || '');
    if (!title) {
      const lines = String(text || '').split(/\\r?\\n/).map(clean).filter(Boolean);
      const candidate = lines.find(line => line.length >= 2 && line.length <= 120 && !/^(보드라이프|BoardLife|게임정보|로그인|회원가입|전체보기)$/i.test(line));
      title = titleClean(candidate || '');
    }
    const image = findImage(doc);
    return {title, image};
  }

  function updatePreview(title, image) {
    const ready = !!(title && image && cafeUrl.value.trim());
    saveButton.disabled = !ready;
    if (title && image) {
      titleInput.value = title;
      imageInput.value = image;
      previewTitle.textContent = title;
      previewImage.src = image;
      preview.classList.add('show');
      box.classList.add('loaded');
      status.className = 'status ok';
      status.textContent = '✓ 게임 이름과 대표 이미지를 찾았습니다. 저장하면 홈페이지에 크게 표시됩니다.';
    } else {
      status.className = 'status';
      status.textContent = '게임 이름 또는 대표 이미지를 찾지 못했습니다. BoardLife 상세페이지 전체를 다시 복사해 주세요.';
    }
  }

  box.addEventListener('paste', event => {
    event.preventDefault();
    const html = event.clipboardData.getData('text/html') || '';
    const text = event.clipboardData.getData('text/plain') || '';
    const parsed = parseClipboard(html, text);
    updatePreview(parsed.title, parsed.image);
    if (!parsed.title || !parsed.image) box.textContent = '⚠ 다시 붙여넣어 주세요.';
    else box.textContent = `✓ ${parsed.title} 정보를 읽었습니다.`;
  });

  cafeUrl.addEventListener('input', () => {
    saveButton.disabled = !(titleInput.value.trim() && imageInput.value.trim() && cafeUrl.value.trim());
  });
})();
</script>
</body>
</html>"""
