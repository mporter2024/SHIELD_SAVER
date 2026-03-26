from flask import Blueprint, request, jsonify
from ai.unified_chatbot import UnifiedChatbot

ai_bp = Blueprint("ai", __name__)
chatbot = UnifiedChatbot()

@ai_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    try:
        reply = chatbot.get_response(user_message)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500