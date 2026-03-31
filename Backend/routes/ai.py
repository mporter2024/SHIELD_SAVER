from flask import Blueprint, request, jsonify, session
from ai.unified_chatbot import UnifiedChatbot
from models.database import get_db
import sqlite3

ai_bp = Blueprint("ai", __name__)
chatbot = UnifiedChatbot()


def load_user_context(user_id):
    db = get_db()

    events = db.execute(
        """
        SELECT id, title, date, start_datetime, end_datetime, location, description,
               guest_count, budget_total
        FROM events
        WHERE user_id = ?
        ORDER BY COALESCE(start_datetime, date) ASC, id DESC
        """,
        (user_id,)
    ).fetchall()

    tasks = db.execute(
        """
        SELECT tasks.id, tasks.event_id, tasks.title, tasks.completed,
               tasks.due_date, tasks.start_datetime, tasks.end_datetime
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE events.user_id = ?
        ORDER BY COALESCE(tasks.start_datetime, tasks.due_date) ASC, tasks.id DESC
        """,
        (user_id,)
    ).fetchall()

    return {
        "events": [dict(row) for row in events],
        "tasks": [dict(row) for row in tasks]
    }


def create_task_for_user(user_id, task_data):
    db = get_db()
    event_id = task_data["event_id"]

    owned_event = db.execute(
        "SELECT id, title FROM events WHERE id = ? AND user_id = ?",
        (event_id, user_id)
    ).fetchone()

    if owned_event is None:
        return None, "That event does not belong to the current user."

    due_date = task_data.get("due_date")
    start_datetime = task_data.get("start_datetime")
    end_datetime = task_data.get("end_datetime")

    try:
        cursor = db.execute(
            """
            INSERT INTO tasks (event_id, title, completed, due_date, start_datetime, end_datetime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task_data["event_id"],
                task_data["title"],
                0,
                due_date or (start_datetime[:10] if start_datetime else None),
                start_datetime,
                end_datetime,
            )
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return None, f"Database error: {str(e)}"

    return {
        "id": cursor.lastrowid,
        "event_id": task_data["event_id"],
        "title": task_data["title"],
        "completed": 0,
        "due_date": due_date or (start_datetime[:10] if start_datetime else None),
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "event_title": owned_event["title"]
    }, None


def complete_task_for_user(user_id, task_id):
    db = get_db()

    task = db.execute(
        """
        SELECT tasks.id, tasks.title, tasks.completed, tasks.event_id, events.title AS event_title
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE tasks.id = ? AND events.user_id = ?
        """,
        (task_id, user_id)
    ).fetchone()

    if task is None:
        return None, "That task was not found for the current user."

    if int(task["completed"]) == 1:
        return None, f"'{task['title']}' is already marked complete."

    db.execute(
        "UPDATE tasks SET completed = 1 WHERE id = ?",
        (task_id,)
    )
    db.commit()

    return {
        "id": task["id"],
        "title": task["title"],
        "event_id": task["event_id"],
        "event_title": task["event_title"],
        "completed": 1
    }, None


@ai_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        context = load_user_context(session["user_id"])

        add_action = chatbot.parse_add_task_command(user_message, context=context)
        if add_action:
            if "error" in add_action:
                return jsonify({
                    "reply": add_action["error"],
                    "action": "task_create_needs_event"
                }), 200

            created_task, error = create_task_for_user(session["user_id"], add_action)

            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_create_failed"
                }), 200

            return jsonify({
                "reply": (
                    f"Task '{created_task['title']}' was added to "
                    f"'{created_task['event_title']}'"
                    + (f" with timing starting {created_task['start_datetime']}." if created_task["start_datetime"] else (f" with due date {created_task['due_date']}." if created_task["due_date"] else "."))
                ),
                "action": "task_created",
                "task": created_task
            }), 200

        complete_action = chatbot.parse_complete_task_command(user_message, context=context)
        if complete_action:
            if "error" in complete_action:
                return jsonify({
                    "reply": complete_action["error"],
                    "action": "task_complete_failed"
                }), 200

            completed_task, error = complete_task_for_user(session["user_id"], complete_action["task_id"])

            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_complete_failed"
                }), 200

            return jsonify({
                "reply": (
                    f"Task '{completed_task['title']}' for "
                    f"'{completed_task['event_title']}' was marked complete."
                ),
                "action": "task_completed",
                "task": completed_task
            }), 200

        reply = chatbot.get_response(user_message, context=context)

        return jsonify({
            "reply": reply,
            "action": "chat_reply"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
