from flask import Blueprint, request, jsonify, session
from ai.unified_chatbot import UnifiedChatbot
from models.database import get_db

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
        reply = chatbot.get_response(user_message, context=context)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500