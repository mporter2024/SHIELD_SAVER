from flask import Blueprint, request, jsonify
from models.database import get_db

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


# -------------------------------
# GET all tasks
# -------------------------------
@tasks_bp.get("/")
def get_tasks():
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks").fetchall()
    return jsonify([dict(task) for task in tasks])


# -------------------------------
# GET all tasks for a specific event
# -------------------------------
@tasks_bp.get("/event/<int:event_id>")
def get_tasks_by_event(event_id):
    db = get_db()
    tasks = db.execute(
        "SELECT * FROM tasks WHERE event_id = ?", (event_id,)
    ).fetchall()
    return jsonify([dict(task) for task in tasks])


# -------------------------------
# CREATE a task
# -------------------------------
@tasks_bp.post("/")
def create_task():
    db = get_db()
    data = request.json

    title = data.get("title")
    event_id = data.get("event_id")
    due_date = data.get("due_date")
    completed = data.get("completed", 0)

    if not title or not event_id:
        return {"error": "title and event_id are required"}, 400

    cursor = db.execute(
        """
        INSERT INTO tasks (event_id, title, completed, due_date)
        VALUES (?, ?, ?, ?)
        """,
        (event_id, title, completed, due_date),
    )
    db.commit()

    task_id = cursor.lastrowid

    return {
        "id": task_id,
        "event_id": event_id,
        "title": title,
        "completed": completed,
        "due_date": due_date,
    }, 201


# -------------------------------
# UPDATE a task (title/status/date)
# -------------------------------
@tasks_bp.put("/<int:task_id>")
def update_task(task_id):
    db = get_db()
    data = request.json

    title = data.get("title")
    completed = data.get("completed")
    due_date = data.get("due_date")

    db.execute(
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

    return {"message": "Task updated successfully"}


# -------------------------------
# DELETE a task
# -------------------------------
@tasks_bp.delete("/<int:task_id>")
def delete_task(task_id):
    db = get_db()

    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()

    return {"message": "Task deleted successfully"}
