import re
from copy import deepcopy

from ai.entity_parser import (
    extract_event_fields,
    extract_event_update_fields,
    looks_like_event_creation,
    looks_like_event_update,
    merge_event_draft,
    missing_required_event_fields,
    build_missing_fields_prompt,
)


REFERENCE_WORDS = (
    "it",
    "that event",
    "this event",
    "the event",
    "that one",
    "this one",
)


def get_default_chat_state():
    return {
        "last_event_id": None,
        "last_task_id": None,
        "active_flow": None,
        "awaiting_field": None,
        "pending_event_draft": {},
        "last_intent": None,
        "last_changes": {},
        "pending_followup": None,
        "planning_context": {},
    }


def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s\-&'/]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def looks_like_existing_event_edit(message: str):
    lowered = (message or "").lower()

    edit_phrases = [
        "change ",
        "update ",
        "move ",
        "reschedule ",
        "rename ",
        "edit ",
        "set the location",
        "set location",
        "change the location",
        "update the location",
        "location is",
        "set the guest count",
        "set guest count",
        "change the guest count",
        "change guest count",
        "update the guest count",
        "update guest count",
        "guest count is",
        "set the description",
        "change the description",
        "update the description",
        "description is",
        "set the title",
        "change the title",
        "update the title",
        "move it",
        "update it",
        "change it",
        "rename it",
        "set it to",
        "move that event",
        "change that event",
        "update that event",
        "make it ",
        "call it ",
        "bump it to",
        "switch it to",
        "push it to",
    ]

    return any(phrase in lowered for phrase in edit_phrases)


def find_event_by_title_reference(user_message, events):
    lowered_message = normalize_text(user_message)

    exact_match = None
    partial_match = None
    best_overlap_match = None
    best_overlap_score = 0

    message_words = set(lowered_message.split())

    for event in events:
        title = (event.get("title") or "").strip()
        if not title:
            continue

        normalized_title = normalize_text(title)
        title_words = set(normalized_title.split())

        if normalized_title == lowered_message:
            return event

        if normalized_title and normalized_title in lowered_message:
            if exact_match is None:
                exact_match = event

        if title_words:
            overlap = len(title_words.intersection(message_words))
            if overlap > best_overlap_score:
                best_overlap_score = overlap
                best_overlap_match = event

        if any(word in lowered_message for word in [normalized_title]) and partial_match is None:
            partial_match = event

    if exact_match:
        return exact_match
    if best_overlap_match and best_overlap_score >= 2:
        return best_overlap_match
    if partial_match:
        return partial_match

    return None


def find_event_from_state_reference(message, events, state):
    lowered = (message or "").lower()

    if not any(word in lowered for word in REFERENCE_WORDS):
        return None

    last_event_id = state.get("last_event_id")
    if not last_event_id:
        return None

    for event in events:
        if int(event["id"]) == int(last_event_id):
            return event

    return None


def resolve_target_event(message, context, state):
    events = context.get("events", [])

    target_event = find_event_by_title_reference(message, events)
    if target_event:
        return target_event

    target_event = find_event_from_state_reference(message, events, state)
    if target_event:
        return target_event

    last_event_id = state.get("last_event_id")
    if last_event_id:
        for event in events:
            if int(event["id"]) == int(last_event_id):
                return event

    if len(events) == 1:
        return events[0]

    return None


def interpret_message(message, context, state):
    state = deepcopy(state or get_default_chat_state())
    context = context or {"events": [], "tasks": []}

    pending_event_draft = state.get("pending_event_draft") or {}
    extracted_create = extract_event_fields(message)
    extracted_update = extract_event_update_fields(message)

    update_changes = {
        key: value
        for key, value in extracted_update.items()
        if value not in (None, "", [])
    }
    update_changes.pop("catering", None)
    update_changes.pop("event_size_hint", None)

    has_pending_create = bool(pending_event_draft)
    create_triggered = looks_like_event_creation(message) or has_pending_create
    update_triggered = looks_like_existing_event_edit(message) or looks_like_event_update(message)

    if create_triggered:
        draft = merge_event_draft(pending_event_draft, extracted_create)
        missing = missing_required_event_fields(draft)

        state["active_flow"] = "event_create"
        state["pending_event_draft"] = draft
        state["last_intent"] = "event_create"

        if missing:
            state["awaiting_field"] = missing[0]
            return {
                "type": "event_create_collecting",
                "draft": draft,
                "missing_fields": missing,
                "reply": build_missing_fields_prompt(draft),
                "state": state,
            }

        state["awaiting_field"] = None
        return {
            "type": "event_create",
            "draft": draft,
            "reply": None,
            "state": state,
        }

    if update_triggered:
        target_event = resolve_target_event(message, context, state)

        if not target_event:
            return {
                "type": "event_update_needs_target",
                "reply": "I can update an event, but I couldn’t tell which one you meant. Please mention the event title.",
                "state": state,
            }

        if not update_changes:
            return {
                "type": "event_update_no_changes",
                "target_event": target_event,
                "reply": f"I found '{target_event['title']}', but I couldn’t tell what you wanted to change.",
                "state": state,
            }

        state["active_flow"] = "event_update"
        state["last_event_id"] = target_event["id"]
        state["last_intent"] = "event_update"
        state["last_changes"] = dict(update_changes)

        return {
            "type": "event_update",
            "target_event": target_event,
            "changes": update_changes,
            "reply": None,
            "state": state,
        }

    return {
        "type": "fallback",
        "reply": None,
        "state": state,
    }
