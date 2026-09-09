from datetime import datetime, timezone
from flask import jsonify, redirect, render_template_string, request, url_for
from sqlalchemy import String
import app as app_module

app = app_module.app

class TodayGame(app_module.Base):
    __tablename__ = "today_game"
    id = app_module.mapped_column(app_module.Integer, primary_key=True, default=1)
    title = app_module.mapped_column(String(250), nullable=False, default="")
    cafe_url = app_module.mapped_column(String(1000), nullable=False, default="")
    updated_at = app_module.mapped_column(String(40), nullable=False, default="")

app_module.Base.metadata.create_all(app_module.engine)

def _current(db):
    item = db.get(TodayGame, 1)
    if item is None:
        item = TodayGame(id=1, title="", cafe_url="", updated_at="")
        db.add(item)
        db.commit()
    return item

@app.route("/api/today-game")
def api_today_game():
    db = app_module.DBSession()
    item = _current(db)
    return jsonify({"title": item.title or "", "cafe_url": item.cafe_url or "", "updated_at": item.updated_at or "", "enabled": bool(item.title and item.cafe_url)})

@app.route("/admin/today-game", methods=["GET", "POST"])
@app_module.admin_required
def admin_today_game():
    db = app_module.DBSession()
    item = _current(db)
    if request.method == "POST":
        title = app_module.clean_text(request.form.get("title"))[:250]
        cafe_url = app_module.clean_text(request.form.get("cafe_url"))[:1000]
        if cafe_url and not (cafe_url.startswith("https://cafe.naver.com/") or cafe_url.startswith("https://m.cafe.naver.com/")):
            return render_template_string(ADMIN_HTML, item=item, error="네이버 카페 주소만 입력해 주세요.")
        item.title = title
        item.cafe_url = cafe_url
        item.updated_at = datetime.now(timezone.utc).isoformat()
        db.commit()
        return redirect(url_for("admin_today_game"))
    return render_template_string(ADMIN_HTML, item=item, error="")

ADMIN_HTML = """<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>오늘의 게임 관리</title><style>body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif;background:#f6f3ed;margin:0;color:#29251f}.wrap{max-width:720px;margin:auto;padding:28px 18px}.panel{background:#fff;border:1px solid #e7e0d5;border-radius:20px;padding:24px;box-shadow:0 8px 30px #0000000b}h1{margin:0 0 8px}p{color:#716a61;line-height:1.6}.back{display:inline-block;margin-bottom:16px;color:#6a4cff;text-decoration:none}label{display:block;font-weight:700;margin:18px 0 8px}input{box-sizing:border-box;width:100%;padding:13px 14px;border:1px solid #d9d1c5;border-radius:12px;font:inherit}button{margin-top:20px;border:0;border-radius:12px;padding:13px 18px;background:#29251f;color:#fff;font-weight:800;font:inherit;cursor:pointer}.error{background:#fff0f0;color:#b42318;padding:12px;border-radius:10px;margin:12px 0}.hint{font-size:13px;color:#82796e}.preview{margin-top:22px;padding:18px;background:#faf8f4;border-radius:14px}.preview a{color:#6a4cff}</style></head><body><main class='wrap'><a class='back' href='/admin'>← 관리자 페이지로 돌아가기</a><section class='panel'><h1>🎲 오늘의 게임</h1><p>아지트 보유 게임과 관계없이 네이버 카페의 오늘 소개 글로 연결합니다. 홈페이지에는 본문을 복제하지 않습니다.</p>{% if error %}<div class='error'>{{ error }}</div>{% endif %}<form method='post'><input type='hidden' name='_csrf_token' value='{{ csrf_token() }}'><label>게임 이름</label><input name='title' value='{{ item.title }}' placeholder='예: 윙스팬'><label>네이버 카페 글 주소</label><input name='cafe_url' type='url' value='{{ item.cafe_url }}' placeholder='https://cafe.naver.com/...'><div class='hint'>매일 새 글로 바꿀 때 제목과 링크만 수정하면 됩니다.</div><button type='submit'>저장하기</button></form>{% if item.title and item.cafe_url %}<div class='preview'><b>현재 연결</b><p><strong>{{ item.title }}</strong></p><a href='{{ item.cafe_url }}' target='_blank' rel='noopener noreferrer'>네이버 카페 글 열기 ↗</a></div>{% endif %}</section></main></body></html>"""
