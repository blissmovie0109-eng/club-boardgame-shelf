import hmac
import os
import re
import secrets
import uuid
from functools import wraps
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import Float, Integer, String, Text, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
CLUB_NAME = os.environ.get("CLUB_NAME", "보드게임 컬렉션")
SITE_TAGLINE = os.environ.get("SITE_TAGLINE", "아지트에 있는 보드게임을 한눈에 확인하세요.")
DEFAULT_LOCATION = os.environ.get("DEFAULT_LOCATION", "아지트")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'games.db')}")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("postgresql+psycopg://"):
    engine_kwargs["connect_args"] = {"prepare_threshold": None}

engine = create_engine(DATABASE_URL, **engine_kwargs)
DBSession = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_url: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), default="")
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    video_url: Mapped[str] = mapped_column(String(1000), default="")
    material_url: Mapped[str] = mapped_column(String(1000), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_players: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_players: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_players: Mapped[str] = mapped_column(String(100), default="")
    recommended_players: Mapped[str] = mapped_column(String(150), default="")
    min_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    age: Mapped[str] = mapped_column(String(100), default="")
    category: Mapped[str] = mapped_column(String(250), default="")
    location: Mapped[str] = mapped_column(String(150), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(40), server_default=func.current_timestamp())


app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)


@app.context_processor
def inject_site_settings():
    return {"club_name": CLUB_NAME, "site_tagline": SITE_TAGLINE}


@app.teardown_appcontext
def remove_db_session(exception=None):
    DBSession.remove()


def init_db():
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("games")}
    additions = {
        "location": "VARCHAR(150) DEFAULT ''",
        "video_url": "VARCHAR(1000) DEFAULT ''",
        "material_url": "VARCHAR(1000) DEFAULT ''",
    }
    with engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE games ADD COLUMN {name} {sql_type}"))
        connection.execute(
            text("UPDATE games SET location = :location WHERE location IS NULL OR location = ''"),
            {"location": DEFAULT_LOCATION},
        )


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def verify_csrf():
    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        received = request.form.get("_csrf_token", "")
        if not expected or not received or not hmac.compare_digest(expected, received):
            abort(400, "잘못된 요청입니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.")


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def first_match(pattern, text_value, flags=0):
    match = re.search(pattern, text_value, flags)
    return match.groups() if match else None


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_boardlife_url(url):
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"boardlife.co.kr", "www.boardlife.co.kr"}
        and bool(re.match(r"^/game/\d+/?$", parsed.path))
    )


def fetch_boardlife(url, headers, max_redirects=3):
    current = url
    for _ in range(max_redirects + 1):
        if not validate_boardlife_url(current):
            raise ValueError("허용되지 않은 BoardLife 주소입니다.")
        response = requests.get(current, headers=headers, timeout=20, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                raise ValueError("BoardLife 리디렉션 주소를 확인할 수 없습니다.")
            current = urljoin(current, location)
            continue
        response.raise_for_status()
        return response
    raise ValueError("BoardLife 리디렉션 횟수가 너무 많습니다.")


def safe_next_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return None
    return value


def extract_label_value(text_value, label, value_pattern, window=120):
    idx = text_value.find(label)
    if idx < 0:
        return None
    chunk = text_value[idx: idx + window]
    match = re.search(value_pattern, chunk)
    return match.groups() if match else None


def parse_boardlife(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
    }
    response = fetch_boardlife(url, headers)
    soup = BeautifulSoup(response.text, "html.parser")
    page_text = clean_text(soup.get_text(" ", strip=True))

    def meta(*keys):
        for key in keys:
            tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                return clean_text(tag.get("content"))
        return ""

    title = meta("og:title", "twitter:title")
    if not title:
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else ""
    title = re.sub(r"\s*\|\s*보드게임.*$", "", title)
    title = re.sub(r"\s*보드게임$", "", title).strip()

    image_url = meta("og:image", "twitter:image")
    if not image_url:
        image = soup.find("img", src=re.compile(r"boardlife"))
        image_url = image.get("src", "") if image else ""
    if image_url.startswith("//"):
        image_url = "https:" + image_url

    description = meta("description", "og:description")
    players = extract_label_value(page_text, "인원", r"(\d+)\s*[-~]\s*(\d+)\s*명") or first_match(r"인원\s*(\d+)\s*[-~]\s*(\d+)\s*명", page_text)
    min_players, max_players = (map(int, players) if players else (None, None))
    playtime = extract_label_value(page_text, "플레이 시간", r"(\d+)\s*[-~]\s*(\d+)\s*분") or first_match(r"플레이 시간\s*(\d+)\s*[-~]\s*(\d+)\s*분", page_text)
    min_time, max_time = (map(int, playtime) if playtime else (None, None))

    difficulty_match = first_match(r"난이도\s*([0-9]+(?:\.[0-9]+)?)", page_text)
    difficulty = safe_float(difficulty_match[0]) if difficulty_match else None
    rating_match = first_match(r"평점\s*([0-9]+(?:\.[0-9]+)?)", page_text)
    rating = safe_float(rating_match[0]) if rating_match else None
    year_match = first_match(r"(?:^|\s)((?:19|20)\d{2})년(?:\s|$)", page_text)
    year = safe_int(year_match[0]) if year_match else None

    best_players = ""
    recommended_players = ""
    recommendation = first_match(r"베스트\s*:?\s*([^,\)]+).*?추천\s*:?\s*([^\)]+)", page_text)
    if recommendation:
        best_players = clean_text(recommendation[0])
        recommended_players = clean_text(recommendation[1])

    age_match = first_match(r"사용 연령\s*([^\n]{1,30}?이상)", page_text)
    age = clean_text(age_match[0]) if age_match else ""
    category_match = first_match(r"카테고리\s*([^|]{1,100})", page_text)
    category = clean_text(category_match[0])[:100] if category_match else ""

    if not title:
        raise ValueError("게임 제목을 찾지 못했습니다. 직접 추가 기능을 이용해 주세요.")

    return {
        "source_url": url,
        "title": title,
        "subtitle": "",
        "image_url": image_url,
        "video_url": "",
        "material_url": "",
        "year": year,
        "min_players": min_players,
        "max_players": max_players,
        "best_players": best_players,
        "recommended_players": recommended_players,
        "min_time": min_time,
        "max_time": max_time,
        "difficulty": difficulty,
        "rating": rating,
        "age": age,
        "category": category,
        "location": DEFAULT_LOCATION,
        "description": description[:1000],
    }


def form_game_data(form):
    return {
        "title": clean_text(form.get("title")),
        "subtitle": clean_text(form.get("subtitle")),
        "image_url": clean_text(form.get("image_url")),
        "video_url": clean_text(form.get("video_url")),
        "material_url": clean_text(form.get("material_url")),
        "year": safe_int(clean_text(form.get("year"))),
        "min_players": safe_int(clean_text(form.get("min_players"))),
        "max_players": safe_int(clean_text(form.get("max_players"))),
        "best_players": clean_text(form.get("best_players")),
        "recommended_players": clean_text(form.get("recommended_players")),
        "min_time": safe_int(clean_text(form.get("min_time"))),
        "max_time": safe_int(clean_text(form.get("max_time"))),
        "difficulty": safe_float(clean_text(form.get("difficulty"))),
        "rating": safe_float(clean_text(form.get("rating"))),
        "age": clean_text(form.get("age")),
        "category": clean_text(form.get("category")),
        "location": clean_text(form.get("location")) or DEFAULT_LOCATION,
        "description": clean_text(form.get("description")),
    }


@app.route("/")
def index():
    db = DBSession()
    games = db.scalars(select(Game).order_by(func.lower(Game.title))).all()
    locations = sorted({clean_text(game.location) for game in games if clean_text(game.location)})
    return render_template("index.html", games=games, locations=locations)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["admin"] = True
            session["_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(safe_next_url(request.args.get("next")) or url_for("admin"))
        flash("관리자 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    db = DBSession()
    if request.method == "POST":
        url = clean_text(request.form.get("url"))
        location = clean_text(request.form.get("location")) or DEFAULT_LOCATION
        if not validate_boardlife_url(url):
            flash("BoardLife 게임 주소 형식이 아닙니다. 예: https://boardlife.co.kr/game/20251", "error")
            return redirect(url_for("admin"))
        try:
            data = parse_boardlife(url)
            data["location"] = location
            game = Game(**data)
            db.add(game)
            db.commit()
            flash(f"{game.title}을(를) 추가했습니다.", "success")
        except IntegrityError:
            db.rollback()
            flash("이미 추가된 BoardLife 게임입니다.", "error")
        except Exception as exc:
            db.rollback()
            flash(f"자동 가져오기에 실패했습니다: {exc} 직접 추가 기능을 이용할 수 있습니다.", "error")
        return redirect(url_for("admin"))

    games = db.scalars(select(Game).order_by(Game.id.desc())).all()
    return render_template("admin.html", games=games, default_location=DEFAULT_LOCATION)


@app.route("/admin/game/new", methods=["GET", "POST"])
@admin_required
def new_game():
    if request.method == "POST":
        data = form_game_data(request.form)
        if not data["title"]:
            flash("게임 이름은 필수입니다.", "error")
            return render_template("new.html", game=data, default_location=DEFAULT_LOCATION)
        source_url = clean_text(request.form.get("source_url")) or f"manual:{uuid.uuid4()}"
        db = DBSession()
        try:
            game = Game(source_url=source_url, **data)
            db.add(game)
            db.commit()
            flash(f"{game.title}을(를) 직접 추가했습니다.", "success")
            return redirect(url_for("admin"))
        except IntegrityError:
            db.rollback()
            flash("같은 출처 주소의 게임이 이미 있습니다.", "error")
    return render_template("new.html", game={}, default_location=DEFAULT_LOCATION)


@app.route("/admin/game/<int:game_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_game(game_id):
    db = DBSession()
    game = db.get(Game, game_id)
    if not game:
        abort(404)
    if request.method == "POST":
        data = form_game_data(request.form)
        if not data["title"]:
            flash("게임 이름은 필수입니다.", "error")
            return render_template("edit.html", game=game, default_location=DEFAULT_LOCATION)
        for key, value in data.items():
            setattr(game, key, value)
        db.commit()
        flash("게임 정보를 수정했습니다.", "success")
        return redirect(url_for("admin"))
    return render_template("edit.html", game=game, default_location=DEFAULT_LOCATION)


@app.route("/admin/game/<int:game_id>/delete", methods=["POST"])
@admin_required
def delete_game(game_id):
    db = DBSession()
    game = db.get(Game, game_id)
    if game:
        db.delete(game)
        db.commit()
        flash("게임을 삭제했습니다.", "success")
    return redirect(url_for("admin"))


@app.route("/health")
def health():
    return {"ok": True}


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
