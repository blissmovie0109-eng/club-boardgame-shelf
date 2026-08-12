import base64
import hmac
import json
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
MAX_BULK_PASTE_GAMES = 300
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
GAME_TYPES = {
    "base": "본판",
    "expansion": "확장",
    "standalone_expansion": "독립형 확장",
}
EXPANSION_TYPES = ("expansion", "standalone_expansion")

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
    game_type: Mapped[str] = mapped_column(String(30), default="base")
    parent_title: Mapped[str] = mapped_column(String(250), default="")
    parent_game_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    return {"club_name": CLUB_NAME, "site_tagline": SITE_TAGLINE, "game_types": GAME_TYPES}


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
        "game_type": "VARCHAR(30) DEFAULT 'base'",
        "parent_title": "VARCHAR(250) DEFAULT ''",
        "parent_game_id": "INTEGER",
    }
    with engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE games ADD COLUMN {name} {sql_type}"))
        connection.execute(
            text("UPDATE games SET location = :location WHERE location IS NULL OR location = ''"),
            {"location": DEFAULT_LOCATION},
        )
        connection.execute(text("UPDATE games SET game_type = 'base' WHERE game_type IS NULL OR game_type = ''"))
        connection.execute(text("UPDATE games SET parent_title = '' WHERE parent_title IS NULL"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_title ON games (title)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_location ON games (location)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_difficulty ON games (difficulty)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_players ON games (min_players, max_players)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_game_type ON games (game_type)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_games_parent_game_id ON games (parent_game_id)"))
        connection.execute(text("""
            UPDATE games
            SET parent_game_id = (
                SELECT parent.id
                FROM games AS parent
                WHERE parent.id != games.id
                  AND parent.game_type = 'base'
                  AND lower(parent.title) = lower(games.parent_title)
                ORDER BY parent.id
                LIMIT 1
            )
            WHERE parent_game_id IS NULL
              AND game_type IN ('expansion', 'standalone_expansion')
              AND parent_title IS NOT NULL
              AND parent_title != ''
        """))


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


def normalize_game_type(value):
    raw = clean_text(value).lower().replace(" ", "_")
    aliases = {
        "": "base",
        "base": "base",
        "본판": "base",
        "기본": "base",
        "expansion": "expansion",
        "확장": "expansion",
        "확장판": "expansion",
        "standalone_expansion": "standalone_expansion",
        "standalone": "standalone_expansion",
        "독립형_확장": "standalone_expansion",
        "독립형확장": "standalone_expansion",
        "독립형_확장판": "standalone_expansion",
        "독립형확장판": "standalone_expansion",
    }
    return aliases.get(raw, "base")


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
        "game_type": normalize_game_type(form.get("game_type")),
        "parent_title": clean_text(form.get("parent_title")),
        "parent_game_id": safe_int(clean_text(form.get("parent_game_id"))),
        "description": clean_text(form.get("description")),
    }


def link_parent_data(db, data, current_game_id=None):
    if data.get("game_type") == "base":
        data["parent_game_id"] = None
        data["parent_title"] = ""
        return data

    parent = None
    parent_id = data.get("parent_game_id")
    if parent_id and parent_id != current_game_id:
        candidate = db.get(Game, parent_id)
        if candidate and normalize_game_type(candidate.game_type) == "base":
            parent = candidate

    parent_title = clean_text(data.get("parent_title"))
    if parent is None and parent_title:
        stmt = select(Game).where(
            Game.game_type == "base",
            func.lower(Game.title) == parent_title.lower(),
        )
        if current_game_id:
            stmt = stmt.where(Game.id != current_game_id)
        parent = db.scalar(stmt.order_by(Game.id).limit(1))

    if parent:
        data["parent_game_id"] = parent.id
        data["parent_title"] = parent.title
    else:
        data["parent_game_id"] = None
        data["parent_title"] = parent_title
    return data


def parent_game_for(db, game):
    if game.parent_game_id:
        parent = db.get(Game, game.parent_game_id)
        if parent:
            return parent
    if game.parent_title:
        return db.scalar(
            select(Game)
            .where(Game.game_type == "base", func.lower(Game.title) == game.parent_title.lower())
            .order_by(Game.id)
            .limit(1)
        )
    return None


def expansions_for(db, base_game):
    if normalize_game_type(base_game.game_type) != "base":
        return []
    return db.scalars(
        select(Game)
        .where(
            Game.game_type.in_(EXPANSION_TYPES),
            or_(
                Game.parent_game_id == base_game.id,
                (
                    Game.parent_game_id.is_(None)
                    & (func.lower(Game.parent_title) == base_game.title.lower())
                ),
            ),
        )
        .order_by(Game.game_type.desc(), func.lower(Game.title), Game.id)
    ).all()


def incomplete_game_condition():
    return or_(
        Game.image_url.is_(None),
        Game.image_url == "",
        Game.difficulty.is_(None),
        Game.min_players.is_(None),
        Game.max_players.is_(None),
        Game.min_time.is_(None),
        Game.max_time.is_(None),
    )


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


def game_to_dict(game, expansion_count=0):
    game_type = normalize_game_type(game.game_type)
    return {
        "id": game.id,
        "source_url": game.source_url or "",
        "detail_url": url_for("game_detail", game_id=game.id),
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
        "game_type": game_type,
        "game_type_label": GAME_TYPES[game_type],
        "parent_title": game.parent_title or "",
        "parent_game_id": game.parent_game_id,
        "expansion_count": expansion_count,
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
    total_games = db.scalar(select(func.count(Game.id)).where(Game.game_type != "expansion")) or 0
    return render_template("index.html", locations=locations, total_games=total_games)


@app.route("/game/<int:game_id>")
def game_detail(game_id):
    db = DBSession()
    game = db.get(Game, game_id)
    if not game:
        abort(404)
    parent_game = parent_game_for(db, game) if normalize_game_type(game.game_type) in EXPANSION_TYPES else None
    expansions = expansions_for(db, game)
    return render_template(
        "game_detail.html",
        game=game,
        game_type=normalize_game_type(game.game_type),
        parent_game=parent_game,
        expansions=expansions,
    )


@app.route("/api/games")
def api_games():
    db = DBSession()
    page = max(1, safe_int(request.args.get("page")) or 1)
    per_page = min(96, max(12, safe_int(request.args.get("per_page")) or 48))
    sort_mode = request.args.get("sort", "weight")
    conditions = game_conditions()
    conditions.append(Game.game_type != "expansion")

    count_stmt = select(func.count(Game.id)).where(*conditions)
    total = db.scalar(count_stmt) or 0
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)

    stmt = select(Game).where(*conditions)
    if sort_mode == "name":
        stmt = stmt.order_by(func.lower(Game.title), Game.id)
    else:
        stmt = stmt.order_by(Game.difficulty.is_(None), Game.difficulty, func.lower(Game.title), Game.id)
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    games = db.scalars(stmt).all()

    base_ids = [game.id for game in games if normalize_game_type(game.game_type) == "base"]
    expansion_counts = {}
    if base_ids:
        expansion_counts = dict(
            db.execute(
                select(Game.parent_game_id, func.count(Game.id))
                .where(Game.parent_game_id.in_(base_ids), Game.game_type.in_(EXPANSION_TYPES))
                .group_by(Game.parent_game_id)
            ).all()
        )

    return jsonify({
        "games": [game_to_dict(game, expansion_counts.get(game.id, 0)) for game in games],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    })


@app.route("/api/games/random")
def api_random_game():
    db = DBSession()
    conditions = game_conditions()
    conditions.append(Game.game_type != "expansion")
    stmt = select(Game).where(*conditions)
    game = db.scalar(stmt.order_by(func.random()).limit(1))
    if not game:
        return jsonify({"game": None})
    expansion_count = 0
    if normalize_game_type(game.game_type) == "base":
        expansion_count = db.scalar(
            select(func.count(Game.id)).where(
                Game.parent_game_id == game.id,
                Game.game_type.in_(EXPANSION_TYPES),
            )
        ) or 0
    return jsonify({"game": game_to_dict(game, expansion_count)})


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
    incomplete_only = request.args.get("incomplete") == "1"
    incomplete_clause = incomplete_game_condition()

    total = db.scalar(select(func.count(Game.id))) or 0
    incomplete_count = db.scalar(select(func.count(Game.id)).where(incomplete_clause)) or 0
    shown_total = incomplete_count if incomplete_only else total
    pages = max(1, (shown_total + per_page - 1) // per_page)
    page = min(page, pages)

    stmt = select(Game)
    if incomplete_only:
        stmt = stmt.where(incomplete_clause)
    games = db.scalars(
        stmt.order_by(Game.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()

    enrich_game_id = safe_int(request.args.get("enrich"))
    enrich_game = db.get(Game, enrich_game_id) if enrich_game_id else None

    return render_template(
        "admin.html",
        games=games,
        default_location=DEFAULT_LOCATION,
        total_games=total,
        shown_total=shown_total,
        incomplete_count=incomplete_count,
        incomplete_only=incomplete_only,
        enrich_game=enrich_game,
        admin_page=page,
        admin_pages=pages,
    )


@app.route("/admin/api/duplicate")
@admin_required
def admin_duplicate_check():
    source_url = canonical_source_url(request.args.get("source_url"))
    exclude_game_id = safe_int(request.args.get("exclude_game_id"))
    if not source_url:
        return jsonify({"duplicate": False})
    db = DBSession()
    game = duplicate_game_for_source(db, source_url, exclude_game_id=exclude_game_id)
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


@app.route("/admin/games/bulk-paste", methods=["POST"])
@admin_required
def bulk_paste_import():
    raw_json = request.form.get("bulk_games_json", "")
    location = clean_text(request.form.get("bulk_location")) or DEFAULT_LOCATION
    try:
        items = json.loads(raw_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        flash("붙여넣은 게임 목록을 읽지 못했습니다. 다시 붙여넣어 주세요.", "error")
        return redirect(url_for("admin"))

    if not isinstance(items, list) or not items:
        flash("등록할 게임이 없습니다.", "error")
        return redirect(url_for("admin"))

    items = items[:MAX_BULK_PASTE_GAMES]
    db = DBSession()
    added = 0
    duplicates = 0
    invalid = 0
    pending_expansions = []

    for item in items:
        if not isinstance(item, dict) or not item.get("selected", True):
            continue

        title = clean_text(item.get("title"))[:250]
        source_url = canonical_source_url(item.get("source_url"))
        if not title or not boardlife_game_id(source_url):
            invalid += 1
            continue

        if duplicate_game_for_source(db, source_url):
            duplicates += 1
            continue

        game_type = normalize_game_type(item.get("game_type"))
        game = Game(
            source_url=source_url,
            title=title,
            subtitle=clean_text(item.get("subtitle"))[:250],
            image_url=clean_text(item.get("image_url"))[:1000],
            year=safe_int(item.get("year")),
            location=location,
            game_type=game_type,
            parent_title=clean_text(item.get("parent_title"))[:250],
        )
        try:
            with db.begin_nested():
                db.add(game)
                db.flush()
            added += 1
            if game_type in EXPANSION_TYPES:
                pending_expansions.append(game)
        except IntegrityError:
            duplicates += 1

    for game in pending_expansions:
        data = {
            "game_type": game.game_type,
            "parent_title": game.parent_title,
            "parent_game_id": game.parent_game_id,
        }
        link_parent_data(db, data, current_game_id=game.id)
        game.parent_game_id = data["parent_game_id"]
        game.parent_title = data["parent_title"]

    db.commit()
    extra = ""
    if len(items) >= MAX_BULK_PASTE_GAMES:
        extra = f" · 한 번에 최대 {MAX_BULK_PASTE_GAMES}개까지 처리"
    flash(f"대량 등록 완료: 추가 {added}개 · 중복 건너뜀 {duplicates}개 · 읽기 실패 {invalid}개{extra}", "success")
    return redirect(url_for("admin", incomplete=1))


@app.route("/admin/game/new", methods=["GET", "POST"])
@admin_required
def new_game():
    db = DBSession()
    parent_id = safe_int(request.args.get("parent_id"))
    parent_game = db.get(Game, parent_id) if parent_id else None
    if parent_game and normalize_game_type(parent_game.game_type) != "base":
        parent_game = None

    if request.method == "POST":
        data = link_parent_data(db, form_game_data(request.form))
        if not data["title"]:
            parent_game = db.get(Game, data.get("parent_game_id")) if data.get("parent_game_id") else None
            flash("게임 이름은 필수입니다.", "error")
            return render_template("new.html", game=data, default_location=DEFAULT_LOCATION, parent_game=parent_game)

        supplied_source = clean_text(request.form.get("source_url"))
        source_url = canonical_source_url(supplied_source) or f"manual:{uuid.uuid4()}"
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
            if game.parent_game_id:
                flash(f"{game.parent_title}의 확장으로 {game.title}을(를) 추가했습니다.", "success")
                return redirect(url_for("edit_game", game_id=game.parent_game_id))
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

    game_data = {}
    if parent_game:
        game_data = {
            "game_type": "expansion",
            "parent_game_id": parent_game.id,
            "parent_title": parent_game.title,
            "location": parent_game.location or DEFAULT_LOCATION,
        }
    return render_template("new.html", game=game_data, default_location=DEFAULT_LOCATION, parent_game=parent_game)


@app.route("/admin/game/<int:game_id>/enrich", methods=["POST"])
@admin_required
def enrich_game(game_id):
    db = DBSession()
    game = db.get(Game, game_id)
    if not game:
        abort(404)

    supplied_source = clean_text(request.form.get("source_url"))
    source_url = canonical_source_url(supplied_source)
    old_boardlife_id = boardlife_game_id(game.source_url)
    new_boardlife_id = boardlife_game_id(source_url)
    if old_boardlife_id and new_boardlife_id and old_boardlife_id != new_boardlife_id:
        flash("선택한 게임과 다른 BoardLife 상세페이지를 붙여넣었습니다. 다시 확인해 주세요.", "error")
        return redirect(url_for("admin", incomplete=1, enrich=game.id))

    if source_url:
        duplicate = duplicate_game_for_source(db, source_url, exclude_game_id=game.id)
        if duplicate:
            flash(f"이 BoardLife 게임은 이미 {duplicate.title}(으)로 등록되어 있습니다.", "error")
            return redirect(url_for("admin", incomplete=1, enrich=game.id))

    data = link_parent_data(db, form_game_data(request.form), current_game_id=game.id)
    for key, value in data.items():
        if key in {"location", "game_type", "parent_game_id", "parent_title"}:
            setattr(game, key, value)
        elif value not in (None, ""):
            setattr(game, key, value)
    if source_url:
        game.source_url = source_url

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        flash("같은 BoardLife 게임이 이미 등록되어 있습니다.", "error")
        return redirect(url_for("admin", incomplete=1, enrich=game.id))

    flash(f"{game.title} 정보를 보강했습니다.", "success")
    return redirect(url_for("admin", incomplete=1))


@app.route("/admin/game/<int:game_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_game(game_id):
    db = DBSession()
    game = db.get(Game, game_id)
    if not game:
        abort(404)

    if request.method == "POST":
        data = link_parent_data(db, form_game_data(request.form), current_game_id=game.id)
        if not data["title"]:
            flash("게임 이름은 필수입니다.", "error")
            return render_template(
                "edit.html",
                game=game,
                default_location=DEFAULT_LOCATION,
                parent_game=parent_game_for(db, game),
                expansions=expansions_for(db, game),
            )

        current_children = expansions_for(db, game)
        if normalize_game_type(game.game_type) == "base" and data["game_type"] != "base" and current_children:
            flash("연결된 확장이 있어 본판을 확장으로 변경할 수 없습니다. 확장을 먼저 다른 본판으로 옮겨 주세요.", "error")
            return redirect(url_for("edit_game", game_id=game.id))

        old_title = game.title
        for key, value in data.items():
            setattr(game, key, value)

        if normalize_game_type(game.game_type) == "base" and old_title != game.title:
            children = db.scalars(select(Game).where(Game.parent_game_id == game.id)).all()
            for child in children:
                child.parent_title = game.title

        db.commit()
        flash("게임 정보를 수정했습니다.", "success")
        return redirect(url_for("admin"))

    return render_template(
        "edit.html",
        game=game,
        default_location=DEFAULT_LOCATION,
        parent_game=parent_game_for(db, game),
        expansions=expansions_for(db, game),
    )


@app.route("/admin/game/<int:game_id>/delete", methods=["POST"])
@admin_required
def delete_game(game_id):
    db = DBSession()
    game = db.get(Game, game_id)
    if game:
        children = expansions_for(db, game)
        if children:
            flash(f"{game.title}에는 확장 {len(children)}개가 연결되어 있어 삭제할 수 없습니다. 확장을 먼저 정리해 주세요.", "error")
            return redirect(url_for("edit_game", game_id=game.id))
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
