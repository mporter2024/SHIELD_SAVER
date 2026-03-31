from flask import Blueprint, jsonify
from models.database import get_db
from utils.auth import admin_required

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/stats", methods=["GET"])
@admin_required
def get_admin_stats():
    db = get_db()

    user_count = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    event_count = db.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
    task_count = db.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]

    return jsonify({
        "total_users": user_count,
        "total_events": event_count,
        "total_tasks": task_count
    }), 200


@admin_bp.route("/users", methods=["GET"])
@admin_required
def get_all_users():
    db = get_db()

    users = db.execute("""
        SELECT id, name, username, email, role
        FROM users
        ORDER BY id DESC
    """).fetchall()

    return jsonify([dict(user) for user in users]), 200


@admin_bp.route("/events", methods=["GET"])
@admin_required
def get_all_events():
    db = get_db()

    events = db.execute("""
        SELECT events.id, events.name, events.date, events.location, users.name AS owner_name, users.email AS owner_email
        FROM events
        JOIN users ON events.user_id = users.id
        ORDER BY events.id DESC
    """).fetchall()

    return jsonify([dict(event) for event in events]), 200