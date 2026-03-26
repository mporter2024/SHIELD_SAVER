import re
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

        for event in events:
            title = (event.get("title") or "").lower()
            if title and title in lowered:
                return event

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

        if events:
            return events[0]

        return None

    def parse_add_task_command(self, message: str, context=None):
        if context is None:
            context = {"events": [], "tasks": []}

        lowered = message.lower().strip()

        if not lowered.startswith(("add task", "add a task", "create task", "create a task")):
            return None

        cleaned = message.strip()

        prefixes = [
            "add a task called ",
            "add a task ",
            "add task called ",
            "add task ",
            "create a task called ",
            "create a task ",
            "create task called ",
            "create task "
        ]

        remainder = cleaned
        for prefix in prefixes:
            if lowered.startswith(prefix):
                remainder = cleaned[len(prefix):].strip()
                break

        if not remainder:
            return None

        due_date = None
        due_match = re.search(r"\s+due\s+(\d{4}-\d{2}-\d{2})\s*$", remainder, re.IGNORECASE)
        if due_match:
            due_date = due_match.group(1)
            remainder = remainder[:due_match.start()].strip()

        event_name = None
        event_match = re.search(r"\s+for\s+(.+)$", remainder, re.IGNORECASE)
        if event_match:
            event_name = event_match.group(1).strip()
            title = remainder[:event_match.start()].strip()
        else:
            title = remainder.strip()

        if not title:
            return None

        selected_event = None
        events = context.get("events", [])

        if event_name:
            event_name_lower = event_name.lower()

            for event in events:
                if (event.get("title") or "").lower() == event_name_lower:
                    selected_event = event
                    break

            if selected_event is None:
                for event in events:
                    event_title = (event.get("title") or "").lower()
                    if event_name_lower in event_title or event_title in event_name_lower:
                        selected_event = event
                        break
        else:
            selected_event = self.pick_relevant_event(message, context)

        if selected_event is None:
            return None

        return {
            "title": title,
            "due_date": due_date,
            "event_id": selected_event["id"]
        }

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