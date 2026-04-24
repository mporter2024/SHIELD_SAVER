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
    agenda_count = db.execute("SELECT COUNT(*) AS count FROM agenda_items").fetchone()["count"]

    return jsonify({
        "total_users": user_count,
        "total_events": event_count,
        "total_tasks": task_count,
        "total_agenda_items": agenda_count,
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
            events.description,
            events.guest_count,
            events.selected_venue,
            events.selected_catering,
            events.estimated_venue_cost,
            events.estimated_catering_cost,
            events.budget_total,
            events.budget_limit,
            users.name AS owner_name,
            users.email AS owner_email,
            COUNT(DISTINCT tasks.id) AS task_count,
            SUM(CASE WHEN tasks.completed = 1 THEN 1 ELSE 0 END) AS completed_task_count,
            COUNT(DISTINCT agenda_items.id) AS agenda_count,
            COUNT(DISTINCT lineup_items.id) AS lineup_count,
            MIN(
                CASE
                    WHEN agenda_items.agenda_date IS NOT NULL AND agenda_items.start_time IS NOT NULL
                        THEN agenda_items.agenda_date || ' ' || agenda_items.start_time
                    WHEN agenda_items.agenda_date IS NOT NULL
                        THEN agenda_items.agenda_date
                    ELSE NULL
                END
            ) AS next_agenda_time
        FROM events
        JOIN users ON events.user_id = users.id
        LEFT JOIN tasks ON tasks.event_id = events.id
        LEFT JOIN agenda_items ON agenda_items.event_id = events.id
        LEFT JOIN lineup_items ON lineup_items.agenda_item_id = agenda_items.id
        GROUP BY events.id
        ORDER BY COALESCE(events.start_datetime, events.date) DESC, events.id DESC
        """
    ).fetchall()
    return jsonify([dict(event) for event in events]), 200
