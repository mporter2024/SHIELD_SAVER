import re
from .intent_model import detect_intent_with_confidence
from .response_engine import get_response


class UnifiedChatbot:
    def __init__(self):
        self.fallback_keywords = {
            "budget": "budgeting",
            "cost": "budgeting",
            "price": "budgeting",
            "spend": "budgeting",
            "afford": "budgeting",
            "cheap": "budgeting",
            "low budget": "budgeting",
            "cut costs": "budgeting",
            "save money": "budgeting",
            "venue": "event_help",
            "location": "event_help",
            "food": "event_help",
            "catering": "event_help",
            "timeline": "timeline_help",
            "schedule": "timeline_help",
            "week before": "timeline_help",
            "event day": "timeline_help",
            "logistics": "event_help",
            "task": "task_help",
            "todo": "task_help",
            "checklist": "task_help",
            "what should i do next": "task_help",
            "next step": "task_help",
            "not forget": "task_help",
            "status": "event_summary",
            "summary": "event_summary",
            "overview": "event_summary",
            "plan": "event_creation",
            "create": "event_creation",
            "organize": "event_creation",
            "set up": "event_creation",
            "new event": "event_creation",
            "called": "event_creation",
            "named": "event_creation",
            "titled": "event_creation",
        }
        self.greetings = {"hello", "hi", "hey", "good morning", "good afternoon"}

    def normalize_text(self, text: str) -> str:
        text = (text or "").lower().strip()
        text = text.replace("to do", "todo")
        text = text.replace("next steps", "next step")
        text = text.replace("fund-raiser", "fundraiser")
        text = text.replace("pls", "please")
        text = text.replace("rn", "right now")
        text = text.replace("idk", "i do not know")
        text = re.sub(r"[^\w\s\-]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _matches_any(self, normalized: str, phrases):
        return any(phrase in normalized for phrase in phrases)

    def detect_intent_with_rules(self, message: str):
        normalized = self.normalize_text(message)

        if normalized in self.greetings:
            return "greeting", 0.99

        budget_phrases = [
            "budget", "cost", "price", "spend", "afford", "cheap", "low budget",
            "save money", "cut costs", "how much money", "not too expensive", "affordable",
        ]
        if self._matches_any(normalized, budget_phrases):
            return "budgeting", 0.99

        if "how long does it take" in normalized and "event" in normalized:
            return "event_creation", 0.98

        if any(p in normalized for p in ["focus on first", "what should i focus on first"]):
            return "event_creation", 0.98

        if any(p in normalized for p in ["first second third", "what should i do first second third"]):
            return "task_help", 0.98

        if "what should i do first" in normalized and ("people" in normalized or "event" in normalized or "planning" in normalized):
            return "event_creation", 0.98

        task_phrases = [
            "checklist", "tasks", "task", "what should i do next", "next step", "not forget",
            "organize tasks", "schedule tasks",
        ]
        if self._matches_any(normalized, task_phrases):
            return "task_help", 0.99

        timeline_phrases = ["timeline", "week before", "event day", "schedule"]
        if self._matches_any(normalized, timeline_phrases):
            return "timeline_help", 0.99

        event_help_phrases = [
            "what do i need", "what should i plan for", "any advice", "good plan", "how do i organize it",
            "what should i prioritize", "how do i choose a good location", "venues", "food should i get",
            "networking event", "outdoor event", "graduation", "club meeting", "casual event", "dinner event",
        ]
        if self._matches_any(normalized, event_help_phrases):
            return "event_help", 0.95

        creation_phrases = [
            "help me plan", "plan an event", "create something", "where do i start", "how do i start",
            "throw something", "something small", "small but still nice", "overthinking it", "what now",
            "guide me", "event planning", "i need ideas for an event", "how do i even plan this",
            "trying to plan", "i dont really know what im doing", "i do not know where to start",
        ]
        if self._matches_any(normalized, creation_phrases):
            return "event_creation", 0.95

        for keyword, intent in self.fallback_keywords.items():
            if keyword in normalized:
                return intent, 0.9

        intent, confidence = detect_intent_with_confidence(normalized)
        if confidence < 0.42:
            return "unclear", confidence
        return intent, confidence

    def pick_relevant_event(self, message: str, context: dict, allow_fallback=True):
        events = context.get("events", [])
        if not events:
            return None

        normalized_message = self.normalize_text(message)

        for event in events:
            title = self.normalize_text(event.get("title", ""))
            if title and title in normalized_message:
                return event

        best_event = None
        best_score = 0
        message_words = set(normalized_message.split())

        for event in events:
            title_words = set(self.normalize_text(event.get("title", "")).split())
            if not title_words:
                continue
            score = len(title_words.intersection(message_words))
            if score > best_score:
                best_score = score
                best_event = event

        if best_score >= 2:
            return best_event

        if allow_fallback and len(events) == 1:
            return events[0]

        fallback_phrases = ["my event", "this event", "that event", "my birthday dinner", "spring expo", "tech summit"]
        if allow_fallback and any(phrase in normalized_message for phrase in fallback_phrases):
            return events[0]

        return None

    def parse_add_task_command(self, message: str, context=None):
        return None

    def parse_complete_task_command(self, message: str, context=None):
        return None

    def build_response(self, message: str, context=None, selected_event=None):
        if context is None:
            context = {"events": [], "tasks": []}

        normalized = self.normalize_text(message)
        intent, confidence = self.detect_intent_with_rules(normalized)

        if selected_event is None:
            selected_event = self.pick_relevant_event(normalized, context)

        return get_response(
            intent=intent,
            text=normalized,
            context=context,
            selected_event=selected_event,
            confidence=confidence,
        )

    def get_response(self, message: str, context=None) -> str:
        cleaned_message = (message or "").strip()
        if not cleaned_message:
            return "Please send a message so I can help."
        if context is None:
            context = {"events": [], "tasks": []}
        return self.build_response(cleaned_message, context=context)
