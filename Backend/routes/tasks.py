"""Routes for event tasks."""

import sqlite3
from flask import Blueprint, jsonify, request, session

from models.database import get_db

tasks_bp = Blueprint("tasks", __name__)


def require_login():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return None


def get_owned_task(task_id: int):
    db = get_db()
    return db.execute(
        """
        SELECT tasks.*
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE tasks.id = ? AND events.user_id = ?
        """,
        (task_id, session["user_id"]),
    ).fetchone()


def get_owned_event(event_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM events WHERE id = ? AND user_id = ?",
        (event_id, session["user_id"]),
    ).fetchone()


@tasks_bp.get("/")
def get_tasks():
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY COALESCE(start_datetime, due_date) ASC, id DESC").fetchall()
    return jsonify([dict(task) for task in tasks]), 200


@tasks_bp.get("/mine")
def get_my_tasks():
    login_error = require_login()
    if login_error:
        return login_error

    db = get_db()
    tasks = db.execute(
        """
        SELECT tasks.*
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE events.user_id = ?
        ORDER BY COALESCE(tasks.start_datetime, tasks.due_date) ASC, tasks.id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return jsonify([dict(task) for task in tasks]), 200


@tasks_bp.get("/event/<int:event_id>")
def get_tasks_by_event(event_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    owned_event = get_owned_event(event_id)
    if owned_event is None:
        return jsonify({"error": "Event not found"}), 404

    db = get_db()
    tasks = db.execute(
        "SELECT * FROM tasks WHERE event_id = ? ORDER BY COALESCE(start_datetime, due_date) ASC, id DESC",
        (event_id,),
    ).fetchall()
    return jsonify([dict(task) for task in tasks]), 200


@tasks_bp.post("/")
def create_task():
    login_error = require_login()
    if login_error:
        return login_error

    db = get_db()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    event_id = data.get("event_id")
    due_date = data.get("due_date")
    start_datetime = data.get("start_datetime") or None
    end_datetime = data.get("end_datetime") or None
    completed = data.get("completed", 0)

    if not title or event_id is None:
        return jsonify({"error": "title and event_id are required"}), 400

    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return jsonify({"error": "event_id must be an integer"}), 400

    owned_event = get_owned_event(event_id)
    if owned_event is None:
        return jsonify({"error": "Event not found"}), 404

    completed = 1 if str(completed).lower() in ("1", "true", "yes") else 0
    due_date = due_date or (start_datetime[:10] if start_datetime else None)

    try:
        cursor = db.execute(
            """
            INSERT INTO tasks (event_id, title, completed, due_date, start_datetime, end_datetime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, title, completed, due_date, start_datetime, end_datetime),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        return jsonify({"error": "Database constraint failed", "details": str(error)}), 400

    task_id = cursor.lastrowid
    return jsonify({
        "id": task_id,
        "event_id": event_id,
        "title": title,
        "completed": completed,
        "due_date": due_date,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
    }), 201


@tasks_bp.put("/<int:task_id>")
def update_task(task_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    existing = get_owned_task(task_id)
    if existing is None:
        return jsonify({"error": "Task not found"}), 404

    db = get_db()
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    completed = data.get("completed")
    due_date = data.get("due_date") if "due_date" in data else None
    start_datetime = data.get("start_datetime") if "start_datetime" in data else None
    end_datetime = data.get("end_datetime") if "end_datetime" in data else None

    if completed is not None:
        completed = 1 if str(completed).lower() in ("1", "true", "yes") else 0

    if start_datetime:
        due_date = start_datetime[:10]

    db.execute(
        """
        UPDATE tasks
        SET title = COALESCE(?, title),
            completed = COALESCE(?, completed),
            due_date = COALESCE(?, due_date),
            start_datetime = COALESCE(?, start_datetime),
            end_datetime = COALESCE(?, end_datetime)
        WHERE id = ?
        """,
        (title, completed, due_date, start_datetime, end_datetime, task_id),
    )
    db.commit()

    updated = get_owned_task(task_id)
    return jsonify({"message": "Task updated successfully", "task": dict(updated)}), 200


@tasks_bp.delete("/<int:task_id>")
def delete_task(task_id: int):
    login_error = require_login()
    if login_error:
        return login_error

    existing = get_owned_task(task_id)
    if existing is None:
        return jsonify({"error": "Task not found"}), 404

    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"message": "Task deleted successfully"}), 200
