import hmac
import os
import re
import secrets
import uuid
from functools import wraps
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import Float, Integer, String, Text, create_engine, func, inspect, or_, select, text
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
        "category": game.category or "",
        "location": game.location or "",
        "description": game.description or "",
    }


@app.route("/")
def index():
    db = DBSession()
    # PostgreSQL requires DISTINCT queries to order by selected expressions.
    # Ordering directly by location is sufficient here and avoids a 500 error.
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
            flash(f"{game.title}을(를) 추가했습니다.", "success")
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
