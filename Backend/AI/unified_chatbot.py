from .intent_model import detect_intent
from .response_engine import get_response


class UnifiedChatbot:
    def __init__(self):
        self.fallback_keywords = {
            "budget": "budgeting",
            "cost": "budgeting",
            "price": "budgeting",
            "venue": "event_help",
            "location": "event_help",
            "food": "event_help",
            "catering": "event_help",
            "timeline": "event_help",
            "schedule": "event_help",
            "plan": "event_creation",
            "create": "event_creation",
            "organize": "event_creation",
            "hello": "greeting",
            "hi": "greeting",
            "hey": "greeting",
        }

    def detect_with_fallback(self, message: str) -> str:
        lowered = message.lower().strip()

        for keyword, intent in self.fallback_keywords.items():
            if keyword in lowered:
                return intent

        return detect_intent(lowered)

    def get_response(self, message: str) -> str:
        cleaned_message = message.strip()

        if not cleaned_message:
            return "Please send a message so I can help."

        intent = self.detect_with_fallback(cleaned_message)
        return get_response(intent, cleaned_message)