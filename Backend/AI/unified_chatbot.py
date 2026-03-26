from .intent_model import detect_intent
from .response_engine import get_response

class UnifiedChatbot:
    def __init__(self):
        pass

    def get_response(self, message: str) -> str:
        message = message.lower().strip()

        if "budget" in message:
            return "I can help estimate an event budget. Tell me the event type and expected attendance."
        elif "venue" in message:
            return "I can help suggest venue planning considerations. What kind of event are you hosting?"
        elif "food" in message or "catering" in message:
            return "I can help estimate catering needs. About how many guests are you expecting?"
        else:
            return "I can help with event planning, budgeting, venues, catering, and event preparation."