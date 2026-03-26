from flask import Blueprint, request, jsonify, session
from models.database import get_db
import sqlite3

tasks_bp = Blueprint("tasks", __name__)

@tasks_bp.get("/")
def get_tasks():
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks").fetchall()
    return jsonify([dict(task) for task in tasks]), 200


@tasks_bp.get("/mine")
def get_my_tasks():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    db = get_db()
    tasks = db.execute(
        """
        SELECT tasks.*
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE events.user_id = ?
        ORDER BY tasks.due_date ASC, tasks.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return jsonify([dict(task) for task in tasks]), 200


@tasks_bp.get("/event/<int:event_id>")
def get_tasks_by_event(event_id):
    db = get_db()
    tasks = db.execute(
        "SELECT * FROM tasks WHERE event_id = ?", (event_id,)
    ).fetchall()
    return jsonify([dict(task) for task in tasks]), 200


@tasks_bp.post("/")
def create_task():
    db = get_db()
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    event_id = data.get("event_id")
    due_date = data.get("due_date")
    completed = data.get("completed", 0)

    if not title or event_id is None:
        return jsonify({"error": "title and event_id are required"}), 400

    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return jsonify({"error": "event_id must be an integer"}), 400

    completed = 1 if str(completed).lower() in ("1", "true", "yes") else 0

    try:
        cursor = db.execute(
            """
            INSERT INTO tasks (event_id, title, completed, due_date)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, title, completed, due_date),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return jsonify({"error": "Database constraint failed", "details": str(e)}), 400

    task_id = cursor.lastrowid

    return jsonify({
        "id": task_id,
        "event_id": event_id,
        "title": title,
        "completed": completed,
        "due_date": due_date,
    }), 201


@tasks_bp.put("/<int:task_id>")
def update_task(task_id):
    db = get_db()
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    completed = data.get("completed")
    due_date = data.get("due_date")

    if completed is not None:
        completed = 1 if str(completed).lower() in ("1", "true", "yes") else 0

    cursor = db.execute(
        """
        UPDATE tasks
        SET title = COALESCE(?, title),
            completed = COALESCE(?, completed),
            due_date = COALESCE(?, due_date)
        WHERE id = ?
        """,
        (title, completed, due_date, task_id),
    )
    db.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({"message": "Task updated successfully"}), 200


@tasks_bp.delete("/<int:task_id>")
def delete_task(task_id):
    db = get_db()

    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({"message": "Task deleted successfully"}), 200