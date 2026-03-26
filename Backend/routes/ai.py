from flask import Blueprint, request, jsonify
from ai.unified_chatbot import UnifiedChatbot

ai_bp = Blueprint("ai", __name__)
bot = UnifiedChatbot()

@ai_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")

    result = bot.chat(message)

    return jsonify(result)