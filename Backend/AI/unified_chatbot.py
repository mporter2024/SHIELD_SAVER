from .intent_model import detect_intent
from .response_engine import get_response

class UnifiedChatbot:

    def chat(self, message):
        intent = detect_intent(message)
        response = get_response(intent, message)

        return {
            "intent": intent,
            "reply": response
        }