"""Agenda and lineup routes.

Agenda items belong to an event.
Lineup items belong to a specific agenda item.
"""

from flask import Blueprint, jsonify, request, session

from models.database import get_db

agenda_bp = Blueprint("agenda", __name__)


def require_login():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return None


def user_owns_event(event_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM events WHERE id = ? AND user_id = ?",
        (event_id, session["user_id"]),
    ).fetchone()


def user_owns_agenda_item(agenda_item_id: int):
    db = get_db()
    return db.execute(
        """
        SELECT agenda_items.*
        FROM agenda_items
        INNER JOIN events ON agenda_items.event_id = events.id
        WHERE agenda_items.id = ? AND events.user_id = ?
        """,
        (agenda_item_id, session["user_id"]),
    ).fetchone()


@agenda_bp.get("/event/<int:event_id>")
def get_agenda_for_event(event_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    owned_event = user_owns_event(event_id)
    if owned_event is None:
        return jsonify({"error": "Event not found"}), 404

    db = get_db()
    agenda_items = db.execute(
        """
        SELECT *
        FROM agenda_items
        WHERE event_id = ?
        ORDER BY COALESCE(start_datetime, end_datetime) ASC, id ASC
        """,
        (event_id,),
    ).fetchall()

    results = []
    for item in agenda_items:
        lineup = db.execute(
            "SELECT * FROM lineup_items WHERE agenda_item_id = ? ORDER BY id ASC",
            (item["id"],),
        ).fetchall()
        results.append({**dict(item), "lineup": [dict(row) for row in lineup]})

    return jsonify(results), 200


@agenda_bp.post("/")
def create_agenda_item():
    login_error = require_login()
    if login_error:
        return login_error

    data = request.get_json(silent=True) or {}
    event_id = data.get("event_id")
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip() or None
    start_datetime = data.get("start_datetime") or None
    end_datetime = data.get("end_datetime") or None

    if not event_id or not title:
        return jsonify({"error": "event_id and title are required"}), 400

    owned_event = user_owns_event(int(event_id))
    if owned_event is None:
        return jsonify({"error": "Event not found"}), 404

    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO agenda_items (event_id, title, description, start_datetime, end_datetime)
        VALUES (?, ?, ?, ?, ?)
        """,
        (event_id, title, description, start_datetime, end_datetime),
    )
    db.commit()

    created_item = db.execute("SELECT * FROM agenda_items WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({**dict(created_item), "lineup": []}), 201


@agenda_bp.put("/<int:agenda_item_id>")
def update_agenda_item(agenda_item_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    owned_item = user_owns_agenda_item(agenda_item_id)
    if owned_item is None:
        return jsonify({"error": "Agenda item not found"}), 404

    data = request.get_json(silent=True) or {}
    db = get_db()
    db.execute(
        """
        UPDATE agenda_items
        SET title = COALESCE(?, title),
            description = COALESCE(?, description),
            start_datetime = COALESCE(?, start_datetime),
            end_datetime = COALESCE(?, end_datetime)
        WHERE id = ?
        """,
        (
            (data.get("title") or None),
            data.get("description") if "description" in data else None,
            data.get("start_datetime") if "start_datetime" in data else None,
            data.get("end_datetime") if "end_datetime" in data else None,
            agenda_item_id,
        ),
    )
    db.commit()

    updated_item = db.execute("SELECT * FROM agenda_items WHERE id = ?", (agenda_item_id,)).fetchone()
    lineup = db.execute("SELECT * FROM lineup_items WHERE agenda_item_id = ? ORDER BY id ASC", (agenda_item_id,)).fetchall()
    return jsonify({**dict(updated_item), "lineup": [dict(row) for row in lineup]}), 200


@agenda_bp.delete("/<int:agenda_item_id>")
def delete_agenda_item(agenda_item_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    owned_item = user_owns_agenda_item(agenda_item_id)
    if owned_item is None:
        return jsonify({"error": "Agenda item not found"}), 404

    db = get_db()
    db.execute("DELETE FROM lineup_items WHERE agenda_item_id = ?", (agenda_item_id,))
    db.execute("DELETE FROM agenda_items WHERE id = ?", (agenda_item_id,))
    db.commit()
    return jsonify({"message": "Agenda item deleted successfully"}), 200


@agenda_bp.post("/<int:agenda_item_id>/lineup")
def create_lineup_item(agenda_item_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    owned_item = user_owns_agenda_item(agenda_item_id)
    if owned_item is None:
        return jsonify({"error": "Agenda item not found"}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "").strip() or None

    if not name:
        return jsonify({"error": "name is required"}), 400

    db = get_db()
    cursor = db.execute(
        "INSERT INTO lineup_items (agenda_item_id, name, role) VALUES (?, ?, ?)",
        (agenda_item_id, name, role),
    )
    db.commit()

    created_item = db.execute("SELECT * FROM lineup_items WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(dict(created_item)), 201


@agenda_bp.delete("/lineup/<int:lineup_item_id>")
def delete_lineup_item(lineup_item_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    db = get_db()
    owned_item = db.execute(
        """
        SELECT lineup_items.*
        FROM lineup_items
        INNER JOIN agenda_items ON lineup_items.agenda_item_id = agenda_items.id
        INNER JOIN events ON agenda_items.event_id = events.id
        WHERE lineup_items.id = ? AND events.user_id = ?
        """,
        (lineup_item_id, session["user_id"]),
    ).fetchone()

    if owned_item is None:
        return jsonify({"error": "Lineup item not found"}), 404

    db.execute("DELETE FROM lineup_items WHERE id = ?", (lineup_item_id,))
    db.commit()
    return jsonify({"message": "Lineup item deleted successfully"}), 200
