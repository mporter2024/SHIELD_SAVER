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
            "task": "task_help",
            "todo": "task_help",
            "next step": "task_help",
            "what should i do next": "task_help",
            "plan": "event_creation",
            "create": "event_creation",
            "organize": "event_creation",
            "hello": "greeting",
            "hi": "greeting",
            "hey": "greeting",
            "summary": "event_summary",
            "status": "event_summary"
        }

    def detect_with_fallback(self, message: str) -> str:
        lowered = message.lower().strip()

        for keyword, intent in self.fallback_keywords.items():
            if keyword in lowered:
                return intent

        return detect_intent(lowered)

    def pick_relevant_event(self, message: str, context: dict):
        events = context.get("events", [])
        lowered = message.lower()

        # First try exact title match
        for event in events:
            title = (event.get("title") or "").lower()
            if title and title in lowered:
                return event

        # Then try partial word overlap
        best_event = None
        best_score = 0

        for event in events:
            title_words = set((event.get("title") or "").lower().split())
            msg_words = set(lowered.split())
            score = len(title_words.intersection(msg_words))
            if score > best_score:
                best_score = score
                best_event = event

        if best_score > 0:
            return best_event

        # Fallback: nearest upcoming / first event in list
        if events:
            return events[0]

        return None

    def get_response(self, message: str, context=None) -> str:
        cleaned_message = message.strip()

        if not cleaned_message:
            return "Please send a message so I can help."

        if context is None:
            context = {"events": [], "tasks": []}

        intent = self.detect_with_fallback(cleaned_message)
        selected_event = self.pick_relevant_event(cleaned_message, context)

        return get_response(
            intent=intent,
            text=cleaned_message,
            context=context,
            selected_event=selected_event
        )