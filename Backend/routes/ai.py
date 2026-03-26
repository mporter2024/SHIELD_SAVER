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
        SELECT id, title, date, location, description
        FROM events
        WHERE user_id = ?
        ORDER BY date ASC, id DESC
        """,
        (user_id,)
    ).fetchall()

    tasks = db.execute(
        """
        SELECT tasks.id, tasks.event_id, tasks.title, tasks.completed, tasks.due_date
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE events.user_id = ?
        ORDER BY tasks.due_date ASC, tasks.id DESC
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

    try:
        cursor = db.execute(
            """
            INSERT INTO tasks (event_id, title, completed, due_date)
            VALUES (?, ?, ?, ?)
            """,
            (
                task_data["event_id"],
                task_data["title"],
                0,
                task_data.get("due_date")
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
        "due_date": task_data.get("due_date"),
        "event_title": owned_event["title"]
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

        action = chatbot.parse_add_task_command(user_message, context=context)

        if action:
            created_task, error = create_task_for_user(session["user_id"], action)

            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_create_failed"
                }), 200

            return jsonify({
                "reply": (
                    f"Task '{created_task['title']}' was added to "
                    f"'{created_task['event_title']}'"
                    + (
                        f" with due date {created_task['due_date']}."
                        if created_task["due_date"] else "."
                    )
                ),
                "action": "task_created",
                "task": created_task
            }), 200

        reply = chatbot.get_response(user_message, context=context)

        return jsonify({
            "reply": reply,
            "action": "chat_reply"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500