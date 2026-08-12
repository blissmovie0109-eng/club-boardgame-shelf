import base64
import csv
import hmac
import io
import os
import re
import secrets
import uuid
from functools import wraps
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import Float, Integer, String, Text, create_engine, func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker

from logo_data import KIRIBO_LOGO_JPG_B64

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
CLUB_NAME = os.environ.get("CLUB_NAME", "보드게임 컬렉션")
SITE_TAGLINE = os.environ.get("SITE_TAGLINE", "아지트에 있는 보드게임을 한눈에 확인하세요.")
DEFAULT_LOCATION = os.environ.get("DEFAULT_LOCATION", "아지트")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'games.db')}")
KIRIBO_LOGO_BYTES = base64.b64decode(KIRIBO_LOGO_JPG_B64)
MAX_CSV_ROWS = 5000
MAX_CSV_BYTES = 5 * 1024 * 1024
ALLOWED_CATEGORIES = (
    "전략",
    "추상",
    "컬렉터블",
    "가족",
    "어린이",
    "파티",
    "테마",
    "워게임",
    "머더미스터리",
)

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
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_title ON games (title)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_location ON games (location)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_difficulty ON games (difficulty)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_players ON games (min_players, max_players)"))


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


def normalize_category(value):
    category_text = clean_text(value)
    if not category_text:
        return ""
    for category in ALLOWED_CATEGORIES:
        if category in category_text:
            return category
    return ""


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


def safe_next_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return None
    return value


def boardlife_game_id(value):
    url = clean_text(value)
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    if host not in {"boardlife.co.kr", "www.boardlife.co.kr"}:
        return None
    match = re.fullmatch(r"/game/(\d+)/?", parsed.path or "")
    return match.group(1) if match else None


def canonical_source_url(value):
    url = clean_text(value)
    game_id = boardlife_game_id(url)
    if game_id:
        return f"https://boardlife.co.kr/game/{game_id}"
    return url


def duplicate_game_for_source(db, source_url, exclude_game_id=None):
    source_url = canonical_source_url(source_url)
    if not source_url:
        return None

    boardlife_id = boardlife_game_id(source_url)
    if boardlife_id:
        candidates = db.scalars(
            select(Game).where(Game.source_url.ilike(f"%/game/{boardlife_id}%"))
        ).all()
        for game in candidates:
            if game.id == exclude_game_id:
                continue
            if boardlife_game_id(game.source_url) == boardlife_id:
                return game

    stmt = select(Game).where(Game.source_url == source_url)
    if exclude_game_id is not None:
        stmt = stmt.where(Game.id != exclude_game_id)
    return db.scalar(stmt.limit(1))


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
        "category": normalize_category(form.get("category")),
        "location": clean_text(form.get("location")) or DEFAULT_LOCATION,
        "description": clean_text(form.get("description")),
    }


def csv_value(row, *names):
    normalized = {clean_text(k).lower(): clean_text(v) for k, v in row.items() if k is not None}
    for name in names:
        value = normalized.get(name.lower())
        if value:
            return value
    return ""


def csv_game_data(row):
    min_players = safe_int(csv_value(row, "최소인원", "min_players", "min players"))
    max_players = safe_int(csv_value(row, "최대인원", "max_players", "max players"))
    compact_players = csv_value(row, "인원", "players")
    if compact_players and (min_players is None or max_players is None):
        match = re.search(r"(\d+)\s*[-~–—]\s*(\d+)", compact_players)
        if match:
            min_players = min_players or int(match.group(1))
            max_players = max_players or int(match.group(2))
        else:
            one = safe_int(re.sub(r"\D", "", compact_players))
            if one:
                min_players = min_players or one
                max_players = max_players or one

    min_time = safe_int(csv_value(row, "최소시간", "min_time", "min time"))
    max_time = safe_int(csv_value(row, "최대시간", "max_time", "max time"))
    compact_time = csv_value(row, "시간", "플레이시간", "playtime", "play time")
    if compact_time and (min_time is None or max_time is None):
        match = re.search(r"(\d+)\s*[-~–—]\s*(\d+)", compact_time)
        if match:
            min_time = min_time or int(match.group(1))
            max_time = max_time or int(match.group(2))
        else:
            one = safe_int(re.sub(r"\D", "", compact_time))
            if one:
                min_time = min_time or one
                max_time = max_time or one
    if min_time is not None and max_time is None:
        max_time = min_time
    if max_time is not None and min_time is None:
        min_time = max_time

    return {
        "title": csv_value(row, "게임명", "title", "이름", "name"),
        "subtitle": csv_value(row, "영문/부제", "영문명", "부제", "subtitle"),
        "image_url": csv_value(row, "이미지URL", "image_url", "image url"),
        "video_url": csv_value(row, "영상URL", "video_url", "video url"),
        "material_url": csv_value(row, "자료URL", "material_url", "material url"),
        "year": safe_int(csv_value(row, "출시연도", "연도", "year")),
        "min_players": min_players,
        "max_players": max_players,
        "best_players": csv_value(row, "베스트인원", "best_players", "best players"),
        "recommended_players": csv_value(row, "추천인원", "recommended_players", "recommended players"),
        "min_time": min_time,
        "max_time": max_time,
        "difficulty": safe_float(csv_value(row, "웨이트", "난이도", "difficulty", "weight")),
        "rating": safe_float(csv_value(row, "평점", "rating")),
        "age": csv_value(row, "연령", "age"),
        "category": normalize_category(csv_value(row, "카테고리", "category")),
        "location": csv_value(row, "보유장소", "장소", "location") or DEFAULT_LOCATION,
        "description": csv_value(row, "게임설명", "설명", "description"),
    }


def game_conditions():
    conditions = []
    query = clean_text(request.args.get("q"))
    location = clean_text(request.args.get("location"))
    players = safe_int(request.args.get("players")) or 0
    weight = clean_text(request.args.get("weight"))

    if query:
        pattern = f"%{query}%"
        conditions.append(or_(Game.title.ilike(pattern), Game.subtitle.ilike(pattern)))
    if location:
        conditions.append(func.lower(Game.location) == location.lower())
    if players:
        if players >= 6:
            conditions.append(Game.max_players >= 6)
        else:
            conditions.extend([Game.min_players <= players, Game.max_players >= players])
    if weight in {"1", "2", "3", "4"}:
        low = float(weight)
        if weight == "4":
            conditions.extend([Game.difficulty >= 4, Game.difficulty <= 5])
        else:
            conditions.extend([Game.difficulty >= low, Game.difficulty < low + 1])
    return conditions


def game_to_dict(game):
    return {
        "id": game.id,
        "source_url": game.source_url or "",
        "title": game.title,
        "subtitle": game.subtitle or "",
        "image_url": game.image_url or "",
        "video_url": game.video_url or "",
        "material_url": game.material_url or "",
        "year": game.year,
        "min_players": game.min_players,
        "max_players": game.max_players,
        "best_players": game.best_players or "",
        "recommended_players": game.recommended_players or "",
        "min_time": game.min_time,
        "max_time": game.max_time,
        "difficulty": game.difficulty,
        "rating": game.rating,
        "age": game.age or "",
        "category": normalize_category(game.category),
        "location": game.location or "",
        "description": game.description or "",
    }


@app.route("/kiribo-logo.jpg")
def kiribo_logo():
    response = Response(KIRIBO_LOGO_BYTES, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return response


@app.route("/")
def index():
    db = DBSession()
    locations = db.scalars(
        select(Game.location)
        .where(Game.location.is_not(None), Game.location != "")
        .distinct()
        .order_by(Game.location)
    ).all()
    total_games = db.scalar(select(func.count(Game.id))) or 0
    return render_template("index.html", locations=locations, total_games=total_games)


@app.route("/api/games")
def api_games():
    db = DBSession()
    page = max(1, safe_int(request.args.get("page")) or 1)
    per_page = min(96, max(12, safe_int(request.args.get("per_page")) or 48))
    sort_mode = request.args.get("sort", "weight")
    conditions = game_conditions()

    count_stmt = select(func.count(Game.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)

    stmt = select(Game)
    if conditions:
        stmt = stmt.where(*conditions)
    if sort_mode == "name":
        stmt = stmt.order_by(func.lower(Game.title), Game.id)
    else:
        stmt = stmt.order_by(Game.difficulty.is_(None), Game.difficulty, func.lower(Game.title), Game.id)
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    games = db.scalars(stmt).all()

    return jsonify({
        "games": [game_to_dict(game) for game in games],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    })


@app.route("/api/games/random")
def api_random_game():
    db = DBSession()
    conditions = game_conditions()
    stmt = select(Game)
    if conditions:
        stmt = stmt.where(*conditions)
    game = db.scalar(stmt.order_by(func.random()).limit(1))
    if not game:
        return jsonify({"game": None})
    return jsonify({"game": game_to_dict(game)})


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


@app.route("/admin")
@admin_required
def admin():
    db = DBSession()
    page = max(1, safe_int(request.args.get("page")) or 1)
    per_page = 50
    total = db.scalar(select(func.count(Game.id))) or 0
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    games = db.scalars(
        select(Game).order_by(Game.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return render_template(
        "admin.html",
        games=games,
        default_location=DEFAULT_LOCATION,
        total_games=total,
        admin_page=page,
        admin_pages=pages,
    )


@app.route("/admin/api/duplicate")
@admin_required
def admin_duplicate_check():
    source_url = canonical_source_url(request.args.get("source_url"))
    if not source_url:
        return jsonify({"duplicate": False})
    db = DBSession()
    game = duplicate_game_for_source(db, source_url)
    if not game:
        return jsonify({"duplicate": False, "source_url": source_url})
    return jsonify({
        "duplicate": True,
        "source_url": source_url,
        "game": {
            "id": game.id,
            "title": game.title,
            "location": game.location or "",
            "edit_url": url_for("edit_game", game_id=game.id),
        },
    })


@app.route("/admin/games/template.csv")
@admin_required
def bulk_csv_template():
    headers = [
        "BoardLife주소", "게임명", "영문/부제", "출시연도", "최소인원", "최대인원",
        "베스트인원", "추천인원", "최소시간", "최대시간", "웨이트", "평점", "연령",
        "카테고리", "보유장소", "이미지URL", "영상URL", "자료URL", "게임설명",
    ]
    output = io.StringIO()
    csv.writer(output).writerow(headers)
    payload = ("\ufeff" + output.getvalue()).encode("utf-8")
    response = Response(payload, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=boardgames_template.csv"
    return response


@app.route("/admin/games/import", methods=["POST"])
@admin_required
def bulk_csv_import():
    upload = request.files.get("csv_file")
    if not upload or not upload.filename:
        flash("CSV 파일을 선택해 주세요.", "error")
        return redirect(url_for("admin"))

    raw = upload.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        flash("CSV 파일은 5MB 이하만 업로드할 수 있습니다.", "error")
        return redirect(url_for("admin"))

    decoded = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        flash("CSV 문자 인코딩을 읽을 수 없습니다. UTF-8 또는 CP949로 저장해 주세요.", "error")
        return redirect(url_for("admin"))

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        flash("CSV 첫 줄에 열 이름이 필요합니다.", "error")
        return redirect(url_for("admin"))

    db = DBSession()
    existing_rows = db.execute(select(Game.source_url, Game.title, Game.location)).all()
    existing_sources = {canonical_source_url(row.source_url) for row in existing_rows if row.source_url}
    existing_boardlife_ids = {
        game_id
        for row in existing_rows
        if (game_id := boardlife_game_id(row.source_url))
    }

    added = 0
    duplicates = 0
    invalid = 0
    processed = 0

    for row in reader:
        if processed >= MAX_CSV_ROWS:
            break
        processed += 1
        data = csv_game_data(row)
        if not data["title"]:
            invalid += 1
            continue

        supplied_source = csv_value(row, "BoardLife주소", "출처주소", "source_url", "url")
        source_url = canonical_source_url(supplied_source)
        boardlife_id = boardlife_game_id(source_url)

        if boardlife_id and boardlife_id in existing_boardlife_ids:
            duplicates += 1
            continue
        if source_url and source_url in existing_sources:
            duplicates += 1
            continue
        if not source_url:
            source_url = f"manual:{uuid.uuid4()}"

        game = Game(source_url=source_url, **data)
        try:
            with db.begin_nested():
                db.add(game)
                db.flush()
            added += 1
            existing_sources.add(source_url)
            if boardlife_id:
                existing_boardlife_ids.add(boardlife_id)
        except IntegrityError:
            duplicates += 1

    db.commit()
    if processed >= MAX_CSV_ROWS:
        flash(f"최대 {MAX_CSV_ROWS}행까지만 처리했습니다. 추가 {added}개 · 중복 {duplicates}개 · 오류/빈 제목 {invalid}개", "success")
    else:
        flash(f"CSV 등록 완료: 추가 {added}개 · 중복 건너뜀 {duplicates}개 · 오류/빈 제목 {invalid}개", "success")
    return redirect(url_for("admin"))


@app.route("/admin/game/new", methods=["GET", "POST"])
@admin_required
def new_game():
    if request.method == "POST":
        data = form_game_data(request.form)
        if not data["title"]:
            flash("게임 이름은 필수입니다.", "error")
            return render_template("new.html", game=data, default_location=DEFAULT_LOCATION)

        supplied_source = clean_text(request.form.get("source_url"))
        source_url = canonical_source_url(supplied_source) or f"manual:{uuid.uuid4()}"
        db = DBSession()
        duplicate = duplicate_game_for_source(db, source_url) if supplied_source else None
        if duplicate:
            flash(
                f"이미 등록된 게임입니다: {duplicate.title} · 보유 장소 {duplicate.location or '미지정'}",
                "error",
            )
            return redirect(url_for("admin"))

        try:
            game = Game(source_url=source_url, **data)
            db.add(game)
            db.commit()
            flash(f"{game.title}을(를) 추가했습니다.", "success")
            return redirect(url_for("admin"))
        except IntegrityError:
            db.rollback()
            duplicate = duplicate_game_for_source(db, source_url)
            if duplicate:
                flash(
                    f"다른 관리자가 먼저 등록했습니다: {duplicate.title} · 보유 장소 {duplicate.location or '미지정'}",
                    "error",
                )
            else:
                flash("같은 출처 주소의 게임이 이미 있습니다.", "error")
            return redirect(url_for("admin"))
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
