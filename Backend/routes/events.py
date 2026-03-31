"""Routes for creating, reading, updating, and deleting events."""

import sqlite3
from flask import Blueprint, jsonify, request, session

from models.database import get_db

events_bp = Blueprint("events", __name__)


def require_login():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return None


def clean_number(value, default=0):
    """Convert numeric input safely for forms and JSON payloads."""
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_owned_event(event_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM events WHERE id = ? AND user_id = ?",
        (event_id, session["user_id"]),
    ).fetchone()


@events_bp.get("/")
def get_events():
    db = get_db()
    events = db.execute("SELECT * FROM events ORDER BY COALESCE(start_datetime, date) DESC, id DESC").fetchall()
    return jsonify([dict(row) for row in events]), 200


@events_bp.get("/mine")
def get_my_events():
    login_error = require_login()
    if login_error:
        return login_error

    db = get_db()
    events = db.execute(
        """
        SELECT *
        FROM events
        WHERE user_id = ?
        ORDER BY COALESCE(start_datetime, date) ASC, id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return jsonify([dict(row) for row in events]), 200


@events_bp.get("/<int:event_id>")
def get_event(event_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    event = get_owned_event(event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    db = get_db()
    tasks = db.execute(
        """
        SELECT *
        FROM tasks
        WHERE event_id = ?
        ORDER BY COALESCE(start_datetime, due_date) ASC, id DESC
        """,
        (event_id,),
    ).fetchall()

    return jsonify({"event": dict(event), "tasks": [dict(task) for task in tasks]}), 200


@events_bp.get("/user/<int:user_id>")
def get_events_by_user(user_id: int):
    db = get_db()
    events = db.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY COALESCE(start_datetime, date) ASC",
        (user_id,),
    ).fetchall()
    return jsonify([dict(row) for row in events]), 200


@events_bp.post("/")
def create_event():
    login_error = require_login()
    if login_error:
        return login_error

    data = request.get_json(silent=True) or {}
    required_fields = ["title", "location", "description"]
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({"error": "Missing required fields", "missing": missing_fields}), 400

    start_datetime = data.get("start_datetime") or None
    end_datetime = data.get("end_datetime") or None
    date = data.get("date") or (start_datetime[:10] if start_datetime else None)

    if not start_datetime and not date:
        return jsonify({"error": "Please provide a start date or date for the event."}), 400

    payload = {
        "title": data.get("title"),
        "date": date,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "location": data.get("location"),
        "description": data.get("description"),
        "guest_count": int(clean_number(data.get("guest_count"), 0)),
        "venue_cost": clean_number(data.get("venue_cost"), 0),
        "food_cost_per_person": clean_number(data.get("food_cost_per_person"), 0),
        "decorations_cost": clean_number(data.get("decorations_cost"), 0),
        "equipment_cost": clean_number(data.get("equipment_cost"), 0),
        "staff_cost": clean_number(data.get("staff_cost"), 0),
        "marketing_cost": clean_number(data.get("marketing_cost"), 0),
        "misc_cost": clean_number(data.get("misc_cost"), 0),
        "contingency_percent": clean_number(data.get("contingency_percent"), 0),
        "budget_subtotal": clean_number(data.get("budget_subtotal"), 0),
        "budget_contingency": clean_number(data.get("budget_contingency"), 0),
        "budget_total": clean_number(data.get("budget_total"), 0),
        "user_id": session["user_id"],
    }

    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO events (
                title, date, start_datetime, end_datetime, location, description, user_id,
                guest_count, venue_cost, food_cost_per_person, decorations_cost,
                equipment_cost, staff_cost, marketing_cost, misc_cost,
                contingency_percent, budget_subtotal, budget_contingency, budget_total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"], payload["date"], payload["start_datetime"], payload["end_datetime"],
                payload["location"], payload["description"], payload["user_id"],
                payload["guest_count"], payload["venue_cost"], payload["food_cost_per_person"],
                payload["decorations_cost"], payload["equipment_cost"], payload["staff_cost"],
                payload["marketing_cost"], payload["misc_cost"], payload["contingency_percent"],
                payload["budget_subtotal"], payload["budget_contingency"], payload["budget_total"],
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        return jsonify({"error": "Database constraint failed", "details": str(error)}), 400

    payload["id"] = cursor.lastrowid
    return jsonify(payload), 201


@events_bp.put("/<int:event_id>")
def update_event(event_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    data = request.get_json(silent=True) or {}
    existing = get_owned_event(event_id)
    if existing is None:
        return jsonify({"error": "Event not found"}), 404

    title = data.get("title")
    location = data.get("location")
    description = data.get("description")
    start_datetime = data.get("start_datetime") if "start_datetime" in data else None
    end_datetime = data.get("end_datetime") if "end_datetime" in data else None
    date = data.get("date") if "date" in data else None

    if "start_datetime" in data and start_datetime:
        date = start_datetime[:10]

    numeric_values = {
        "guest_count": int(clean_number(data.get("guest_count"), existing["guest_count"] or 0)) if "guest_count" in data else None,
        "venue_cost": clean_number(data.get("venue_cost"), existing["venue_cost"] or 0) if "venue_cost" in data else None,
        "food_cost_per_person": clean_number(data.get("food_cost_per_person"), existing["food_cost_per_person"] or 0) if "food_cost_per_person" in data else None,
        "decorations_cost": clean_number(data.get("decorations_cost"), existing["decorations_cost"] or 0) if "decorations_cost" in data else None,
        "equipment_cost": clean_number(data.get("equipment_cost"), existing["equipment_cost"] or 0) if "equipment_cost" in data else None,
        "staff_cost": clean_number(data.get("staff_cost"), existing["staff_cost"] or 0) if "staff_cost" in data else None,
        "marketing_cost": clean_number(data.get("marketing_cost"), existing["marketing_cost"] or 0) if "marketing_cost" in data else None,
        "misc_cost": clean_number(data.get("misc_cost"), existing["misc_cost"] or 0) if "misc_cost" in data else None,
        "contingency_percent": clean_number(data.get("contingency_percent"), existing["contingency_percent"] or 0) if "contingency_percent" in data else None,
        "budget_subtotal": clean_number(data.get("budget_subtotal"), existing["budget_subtotal"] or 0) if "budget_subtotal" in data else None,
        "budget_contingency": clean_number(data.get("budget_contingency"), existing["budget_contingency"] or 0) if "budget_contingency" in data else None,
        "budget_total": clean_number(data.get("budget_total"), existing["budget_total"] or 0) if "budget_total" in data else None,
    }

    db = get_db()
    try:
        db.execute(
            """
            UPDATE events
            SET title = COALESCE(?, title),
                date = COALESCE(?, date),
                start_datetime = COALESCE(?, start_datetime),
                end_datetime = COALESCE(?, end_datetime),
                location = COALESCE(?, location),
                description = COALESCE(?, description),
                guest_count = COALESCE(?, guest_count),
                venue_cost = COALESCE(?, venue_cost),
                food_cost_per_person = COALESCE(?, food_cost_per_person),
                decorations_cost = COALESCE(?, decorations_cost),
                equipment_cost = COALESCE(?, equipment_cost),
                staff_cost = COALESCE(?, staff_cost),
                marketing_cost = COALESCE(?, marketing_cost),
                misc_cost = COALESCE(?, misc_cost),
                contingency_percent = COALESCE(?, contingency_percent),
                budget_subtotal = COALESCE(?, budget_subtotal),
                budget_contingency = COALESCE(?, budget_contingency),
                budget_total = COALESCE(?, budget_total)
            WHERE id = ?
            """,
            (
                title, date, start_datetime, end_datetime, location, description,
                numeric_values["guest_count"], numeric_values["venue_cost"], numeric_values["food_cost_per_person"],
                numeric_values["decorations_cost"], numeric_values["equipment_cost"], numeric_values["staff_cost"],
                numeric_values["marketing_cost"], numeric_values["misc_cost"], numeric_values["contingency_percent"],
                numeric_values["budget_subtotal"], numeric_values["budget_contingency"], numeric_values["budget_total"],
                event_id,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        return jsonify({"error": "Database constraint failed", "details": str(error)}), 400

    updated = get_owned_event(event_id)
    return jsonify({"message": "Event updated successfully", "event": dict(updated)}), 200


@events_bp.delete("/<int:event_id>")
def delete_event(event_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    existing = get_owned_event(event_id)
    if existing is None:
        return jsonify({"error": "Event not found"}), 404

    db = get_db()
    db.execute("DELETE FROM lineup_items WHERE agenda_item_id IN (SELECT id FROM agenda_items WHERE event_id = ?)", (event_id,))
    db.execute("DELETE FROM agenda_items WHERE event_id = ?", (event_id,))
    db.execute("DELETE FROM tasks WHERE event_id = ?", (event_id,))
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()
    return jsonify({"message": "Event deleted successfully"}), 200
