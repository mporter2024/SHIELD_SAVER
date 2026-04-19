import json
import requests


SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["event_create", "event_update", "task_create", "task_complete", "none"]
        },
        "target_reference": {
            "type": "string",
            "enum": ["explicit_title", "last_event", "last_task", "unknown", "none"]
        },
        "fields": {
            "type": "object",
            "properties": {
                "title": {"type": ["string", "null"]},
                "date": {"type": ["string", "null"]},
                "start_time": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "description": {"type": ["string", "null"]},
                "guest_count": {"type": ["integer", "null"]},
                "task_title": {"type": ["string", "null"]}
            },
            "additionalProperties": True
        },
        "confidence": {"type": "number"},
        "clarification_needed": {"type": ["string", "null"]}
    },
    "required": ["action", "target_reference", "fields", "confidence", "clarification_needed"]
}


def ollama_available(url: str) -> bool:
    try:
        r = requests.get("http://localhost:11434", timeout=2)
        return r.status_code < 500
    except Exception:
        return False


def interpret_with_ollama(message: str, context: dict, model: str, url: str):
    system_prompt = """
You are a structured interpreter for an event-planning assistant.

Return JSON only.
Do not explain.
Do not add markdown.
Only include fields clearly supported by the user's message.

Allowed actions:
- event_create
- event_update
- task_create
- task_complete
- none

Use:
- target_reference = explicit_title if the user clearly names an event/task
- last_event if the message refers to "it", "that event", "this event"
- last_task if the message refers to a task
- unknown if action is clear but target is not
- none if no action should be taken
"""

    compact_context = {
        "last_event_id": context.get("last_event_id"),
        "events": [
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "date": e.get("date"),
                "location": e.get("location"),
                "guest_count": e.get("guest_count"),
            }
            for e in context.get("events", [])[:10]
        ],
        "tasks": [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "completed": t.get("completed"),
                "event_id": t.get("event_id"),
            }
            for t in context.get("tasks", [])[:15]
        ],
    }

    payload = {
        "model": model,
        "stream": False,
        "format": SCHEMA,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"message": message, "context": compact_context},
                    ensure_ascii=False
                )
            }
        ]
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    content = response.json()["message"]["content"]
    return json.loads(content)


def safe_ollama_interpret(message: str, context: dict, model: str, url: str):
    try:
        if not ollama_available(url):
            return None
        return interpret_with_ollama(message, context, model, url)
    except Exception:
        return None