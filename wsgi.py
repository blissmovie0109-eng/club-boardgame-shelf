import json
import uuid
from datetime import datetime, timezone

from flask import Response, flash, redirect, request, url_for
from sqlalchemy import func, select

import app as app_module

app = app_module.app

BACKUP_FORMAT = "kiribo-boardgame-backup"
BACKUP_VERSION = 1
MAX_BACKUP_BYTES = 10 * 1024 * 1024
MAX_RESTORE_GAMES = 10000

BACKUP_FIELDS = (
    "source_url",
    "title",
    "subtitle",
    "image_url",
    "video_url",
    "material_url",
    "year",
    "min_players",
    "max_players",
    "best_players",
    "recommended_players",
    "min_time",
    "max_time",
    "difficulty",
    "rating",
    "age",
    "category",
    "location",
    "game_type",
    "parent_title",
    "parent_game_id",
    "description",
    "created_at",
)


def _backup_game(game):
    data = {"id": game.id}
    for field in BACKUP_FIELDS:
        data[field] = getattr(game, field, None)
    return data


def _clean_restore_item(item):
    title = app_module.clean_text(item.get("title"))[:250]
    if not title:
        return None

    source_url = app_module.canonical_source_url(item.get("source_url"))
    if not source_url:
        source_url = f"manual:restore:{uuid.uuid4()}"

    return {
        "source_url": source_url[:500],
        "title": title,
        "subtitle": app_module.clean_text(item.get("subtitle"))[:250],
        "image_url": app_module.clean_text(item.get("image_url"))[:1000],
        "video_url": app_module.clean_text(item.get("video_url"))[:1000],
        "material_url": app_module.clean_text(item.get("material_url"))[:1000],
        "year": app_module.safe_int(item.get("year")),
        "min_players": app_module.safe_int(item.get("min_players")),
        "max_players": app_module.safe_int(item.get("max_players")),
        "best_players": app_module.clean_text(item.get("best_players"))[:100],
        "recommended_players": app_module.clean_text(item.get("recommended_players"))[:150],
        "min_time": app_module.safe_int(item.get("min_time")),
        "max_time": app_module.safe_int(item.get("max_time")),
        "difficulty": app_module.safe_float(item.get("difficulty")),
        "rating": app_module.safe_float(item.get("rating")),
        "age": app_module.clean_text(item.get("age"))[:100],
        "category": app_module.normalize_category(item.get("category")),
        "location": app_module.clean_text(item.get("location"))[:150] or app_module.DEFAULT_LOCATION,
        "game_type": app_module.normalize_game_type(item.get("game_type")),
        "parent_title": app_module.clean_text(item.get("parent_title"))[:250],
        "description": app_module.clean_text(item.get("description")),
    }


@app.route("/admin/backup/download")
@app_module.admin_required
def admin_backup_download():
    db = app_module.DBSession()
    games = db.scalars(select(app_module.Game).order_by(app_module.Game.id)).all()
    payload = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "club_name": app_module.CLUB_NAME,
        "game_count": len(games),
        "games": [_backup_game(game) for game in games],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    date_text = datetime.now().strftime("%Y-%m-%d")
    response = Response(body, mimetype="application/json; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="kiribo-backup-{date_text}.json"'
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/admin/backup/restore", methods=["POST"])
@app_module.admin_required
def admin_backup_restore():
    upload = request.files.get("backup_file")
    if not upload or not upload.filename:
        flash("복원할 백업 JSON 파일을 선택해 주세요.", "error")
        return redirect(url_for("admin"))

    raw = upload.read(MAX_BACKUP_BYTES + 1)
    if len(raw) > MAX_BACKUP_BYTES:
        flash("백업 파일이 너무 큽니다. 10MB 이하의 파일만 복원할 수 있습니다.", "error")
        return redirect(url_for("admin"))

    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        flash("올바른 키리보 백업 JSON 파일이 아닙니다.", "error")
        return redirect(url_for("admin"))

    if not isinstance(payload, dict) or payload.get("format") != BACKUP_FORMAT or payload.get("version") != BACKUP_VERSION:
        flash("지원하지 않는 백업 파일 형식입니다.", "error")
        return redirect(url_for("admin"))

    items = payload.get("games")
    if not isinstance(items, list) or len(items) > MAX_RESTORE_GAMES:
        flash("백업 파일의 게임 목록이 올바르지 않거나 너무 많습니다.", "error")
        return redirect(url_for("admin"))

    db = app_module.DBSession()
    old_to_game = {}
    restored_items = []
    seen_sources = set()
    added = 0
    updated = 0
    skipped = 0

    try:
        for item in items:
            if not isinstance(item, dict):
                skipped += 1
                continue
            data = _clean_restore_item(item)
            if not data:
                skipped += 1
                continue

            source_url = data.pop("source_url")
            source_key = source_url.lower()
            if source_key in seen_sources:
                skipped += 1
                continue
            seen_sources.add(source_key)

            game = app_module.duplicate_game_for_source(db, source_url)
            if game is None:
                game = app_module.Game(source_url=source_url, title=data["title"])
                db.add(game)
                added += 1
            else:
                updated += 1

            for key, value in data.items():
                setattr(game, key, value)
            game.parent_game_id = None
            db.flush()

            old_id = app_module.safe_int(item.get("id"))
            if old_id is not None:
                old_to_game[old_id] = game
            restored_items.append((item, game))

        # 두 번째 단계에서 본판-확장 관계를 새 DB의 ID에 맞춰 복구합니다.
        for item, game in restored_items:
            parent_old_id = app_module.safe_int(item.get("parent_game_id"))
            parent = old_to_game.get(parent_old_id) if parent_old_id is not None else None
            if parent and app_module.normalize_game_type(parent.game_type) == "base" and parent.id != game.id:
                game.parent_game_id = parent.id
                game.parent_title = parent.title
                continue

            parent_title = app_module.clean_text(item.get("parent_title"))
            if parent_title and app_module.normalize_game_type(game.game_type) in app_module.EXPANSION_TYPES:
                parent = db.scalar(
                    select(app_module.Game)
                    .where(
                        app_module.Game.game_type == "base",
                        func.lower(app_module.Game.title) == parent_title.lower(),
                    )
                    .order_by(app_module.Game.id)
                    .limit(1)
                )
                if parent and parent.id != game.id:
                    game.parent_game_id = parent.id
                    game.parent_title = parent.title

        db.commit()
    except Exception:
        db.rollback()
        app.logger.exception("Backup restore failed")
        flash("복원 중 오류가 발생했습니다. 기존 데이터 변경은 취소되었습니다.", "error")
        return redirect(url_for("admin"))

    flash(
        f"백업 복원 완료: 새로 추가 {added}개 · 백업값으로 갱신 {updated}개 · 건너뜀 {skipped}개. 현재 DB에만 있던 게임은 삭제하지 않았습니다.",
        "success",
    )
    return redirect(url_for("admin"))
