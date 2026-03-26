from flask import Blueprint, request, jsonify, session
from models.database import get_db
import sqlite3

events_bp = Blueprint("events", __name__)

@events_bp.get("/")
def get_events():
    db = get_db()
    events = db.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
    return jsonify([dict(row) for row in events]), 200


@events_bp.get("/mine")
def get_my_events():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    db = get_db()
    events = db.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY date ASC, id DESC",
        (session["user_id"],)
    ).fetchall()

    return jsonify([dict(row) for row in events]), 200


@events_bp.get("/<int:event_id>")
def get_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

    if event is None:
        return jsonify({"error": "Event not found"}), 404

    return jsonify(dict(event)), 200


@events_bp.get("/user/<int:user_id>")
def get_events_by_user(user_id):
    db = get_db()
    events = db.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY date ASC",
        (user_id,),
    ).fetchall()

    return jsonify([dict(row) for row in events]), 200


@events_bp.post("/")
def create_event():
    data = request.get_json(silent=True) or {}

    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    required = ["title", "date", "location", "description"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    title = data.get("title")
    date = data.get("date")
    location = data.get("location")
    description = data.get("description")
    user_id = session["user_id"]

    db = get_db()

    try:
        cursor = db.execute(
            """
            INSERT INTO events (title, date, location, description, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, date, location, description, user_id),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return jsonify({"error": "Database constraint failed", "details": str(e)}), 400

    event_id = cursor.lastrowid

    return jsonify({
        "id": event_id,
        "title": title,
        "date": date,
        "location": location,
        "description": description,
        "user_id": user_id
    }), 201


@events_bp.put("/<int:event_id>")
def update_event(event_id):
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    date = data.get("date")
    location = data.get("location")
    description = data.get("description")

    db = get_db()

    cursor = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if cursor is None:
        return jsonify({"error": "Event not found"}), 404

    try:
        result = db.execute(
            """
            UPDATE events
            SET title = COALESCE(?, title),
                date = COALESCE(?, date),
                location = COALESCE(?, location),
                description = COALESCE(?, description)
            WHERE id = ?
            """,
            (title, date, location, description, event_id),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return jsonify({"error": "Database constraint failed", "details": str(e)}), 400

    if result.rowcount == 0:
        return jsonify({"error": "Event not found"}), 404

    return jsonify({"message": "Event updated successfully"}), 200


@events_bp.delete("/<int:event_id>")
def delete_event(event_id):
    db = get_db()

    db.execute("DELETE FROM tasks WHERE event_id = ?", (event_id,))
    cursor = db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Event not found"}), 404

    return jsonify({"message": "Event deleted successfully"}), 200