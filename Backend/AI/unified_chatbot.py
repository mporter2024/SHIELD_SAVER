import re
from .intent_model import detect_intent_with_confidence
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
            "logistics": "event_help",
            "task": "task_help",
            "todo": "task_help",
            "next step": "task_help",
            "what should i do next": "task_help",
            "status": "event_summary",
            "summary": "event_summary",
            "overview": "event_summary",
            "hello": "greeting",
            "hi": "greeting",
            "hey": "greeting",
            "plan": "event_creation",
            "create": "event_creation",
            "organize": "event_creation"
        }

    def normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("to do", "todo")
        text = text.replace("next steps", "next step")
        text = text.replace("fund-raiser", "fundraiser")
        text = re.sub(r"[^\w\s\-]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def detect_intent_with_rules(self, message: str):
        normalized = self.normalize_text(message)

        for keyword, intent in self.fallback_keywords.items():
            if keyword in normalized:
                return intent, 0.99

        intent, confidence = detect_intent_with_confidence(normalized)

        if confidence < 0.45:
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

        if allow_fallback and any(
            phrase in normalized_message for phrase in ["my event", "this event", "that event"]
        ):
            return events[0]

        return None

    def parse_add_task_command(self, message: str, context=None):
        if context is None:
            context = {"events": [], "tasks": []}

        normalized = self.normalize_text(message)

        valid_starts = (
            "add task",
            "add a task",
            "create task",
            "create a task"
        )

        if not normalized.startswith(valid_starts):
            return None

        original = message.strip()

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

        remainder = original
        lowered_original = original.lower()

        for prefix in prefixes:
            if lowered_original.startswith(prefix):
                remainder = original[len(prefix):].strip()
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
            normalized_event_name = self.normalize_text(event_name)

            for event in events:
                event_title = self.normalize_text(event.get("title", ""))
                if event_title == normalized_event_name:
                    selected_event = event
                    break

            if selected_event is None:
                for event in events:
                    event_title = self.normalize_text(event.get("title", ""))
                    if normalized_event_name in event_title or event_title in normalized_event_name:
                        selected_event = event
                        break
        else:
            selected_event = self.pick_relevant_event(message, context, allow_fallback=False)

            if selected_event is None and len(events) == 1:
                selected_event = events[0]

        if selected_event is None:
            return {
                "error": "I couldn’t tell which event this task belongs to. Please include the event name."
            }

        return {
            "title": title,
            "due_date": due_date,
            "event_id": selected_event["id"]
        }

    def parse_complete_task_command(self, message: str, context=None):
        if context is None:
            context = {"events": [], "tasks": []}

        normalized = self.normalize_text(message)

        command_starts = (
            "complete task",
            "complete",
            "mark task",
            "mark",
            "finish task",
            "finish"
        )

        if not normalized.startswith(command_starts):
            return None

        if "complete" not in normalized and "finish" not in normalized and "mark" not in normalized:
            return None

        original = message.strip()
        task_part = original

        patterns = [
            r"^complete task\s+",
            r"^complete\s+",
            r"^mark task\s+",
            r"^mark\s+",
            r"^finish task\s+",
            r"^finish\s+"
        ]

        for pattern in patterns:
            task_part = re.sub(pattern, "", task_part, flags=re.IGNORECASE).strip()
            if task_part != original.strip():
                break

        task_part = re.sub(r"\s+as\s+complete$", "", task_part, flags=re.IGNORECASE).strip()
        task_part = re.sub(r"\s+complete$", "", task_part, flags=re.IGNORECASE).strip()
        task_part = re.sub(r"\s+for\s+(.+)$", "", task_part, flags=re.IGNORECASE).strip()

        event_name = None
        event_match = re.search(r"\s+for\s+(.+)$", original, re.IGNORECASE)
        if event_match:
            event_name = event_match.group(1).strip()

        if not task_part:
            return {"error": "Please include the task name you want to complete."}

        tasks = context.get("tasks", [])
        events = context.get("events", [])

        selected_event = None
        if event_name:
            normalized_event_name = self.normalize_text(event_name)
            for event in events:
                event_title = self.normalize_text(event.get("title", ""))
                if event_title == normalized_event_name:
                    selected_event = event
                    break
            if selected_event is None:
                for event in events:
                    event_title = self.normalize_text(event.get("title", ""))
                    if normalized_event_name in event_title or event_title in normalized_event_name:
                        selected_event = event
                        break

        candidate_tasks = tasks
        if selected_event is not None:
            candidate_tasks = [
                task for task in tasks
                if int(task.get("event_id", 0)) == int(selected_event["id"])
            ]

        normalized_task_name = self.normalize_text(task_part)

        exact_matches = []
        partial_matches = []

        for task in candidate_tasks:
            task_title = self.normalize_text(task.get("title", ""))

            if task_title == normalized_task_name:
                exact_matches.append(task)
            elif normalized_task_name in task_title or task_title in normalized_task_name:
                partial_matches.append(task)

        matches = exact_matches if exact_matches else partial_matches

        if not matches:
            return {
                "error": "I couldn’t find a matching task to complete. Try using the full task name."
            }

        incomplete_matches = [
            task for task in matches
            if int(task.get("completed", 0)) == 0
        ]

        if len(incomplete_matches) == 1:
            return {
                "task_id": incomplete_matches[0]["id"]
            }

        if len(incomplete_matches) > 1:
            task_titles = ", ".join(task["title"] for task in incomplete_matches[:3])
            return {
                "error": f"I found multiple matching incomplete tasks: {task_titles}. Please be more specific."
            }

        if len(matches) == 1 and int(matches[0].get("completed", 0)) == 1:
            return {
                "error": f"'{matches[0]['title']}' is already marked complete."
            }

        return {
            "error": "I couldn’t find an incomplete version of that task."
        }

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
            confidence=confidence
        )

    def get_response(self, message: str, context=None) -> str:
        cleaned_message = message.strip()

        if not cleaned_message:
            return "Please send a message so I can help."

        if context is None:
            context = {"events": [], "tasks": []}

        return self.build_response(cleaned_message, context=context)