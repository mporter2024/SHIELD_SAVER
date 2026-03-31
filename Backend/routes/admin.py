from flask import Blueprint, jsonify
from models.database import get_db
from utils.auth import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/stats")
@admin_required
def get_admin_stats():
    db = get_db()

    user_count = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    event_count = db.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
    task_count = db.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]

    return jsonify({
        "total_users": user_count,
        "total_events": event_count,
        "total_tasks": task_count,
    }), 200


@admin_bp.get("/users")
@admin_required
def get_all_users():
    db = get_db()
    users = db.execute(
        """
        SELECT id, name, username, email, role
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()
    return jsonify([dict(user) for user in users]), 200


@admin_bp.get("/events")
@admin_required
def get_all_events():
    db = get_db()
    events = db.execute(
        """
        SELECT
            events.id,
            events.title,
            events.date,
            events.start_datetime,
            events.end_datetime,
            events.location,
            users.name AS owner_name,
            users.email AS owner_email
        FROM events
        JOIN users ON events.user_id = users.id
        ORDER BY COALESCE(events.start_datetime, events.date) DESC, events.id DESC
        """
    ).fetchall()
    return jsonify([dict(event) for event in events]), 200
