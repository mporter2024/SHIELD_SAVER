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
    detect_task_action,
    extract_task_fields,
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


def has_meaningful_create_data(extracted_create):
    return any(
        extracted_create.get(key) not in (None, "", [])
        for key in ["title", "date", "start_datetime", "location", "guest_count", "description"]
    )


def should_prefer_create_over_update(message, extracted_create, update_changes, pending_event_draft):
    lowered = (message or "").lower()

    if pending_event_draft:
        return True

    create_trigger = looks_like_event_creation(message)
    if not create_trigger:
        return False

    if not has_meaningful_create_data(extracted_create):
        return False

    strong_update_phrases = [
        "change it",
        "change it to",
        "update it",
        "update it to",
        "move it",
        "move it to",
        "reschedule it",
        "reschedule it to",
        "rename it",
        "rename it to",
        "set it to",
        "switch it to",
        "push it to",
        "bump it to",
        "change the location",
        "update the location",
        "set the location",
        "change the date",
        "update the date",
        "set the date",
        "change the time",
        "update the time",
        "set the time",
        "change the title",
        "update the title",
        "set the title",
        "change the guest count",
        "update the guest count",
        "set the guest count",
    ]

    if any(phrase in lowered for phrase in strong_update_phrases):
        return False

    return True


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



def find_task_by_reference(task_title, tasks):
    if not task_title or not tasks:
        return None

    normalized_query = task_title.lower().strip()

    for task in tasks:
        task_name = (task.get("title") or "").lower().strip()
        if task_name == normalized_query:
            return task

    for task in tasks:
        task_name = (task.get("title") or "").lower().strip()
        if normalized_query in task_name or task_name in normalized_query:
            return task

    query_tokens = {token for token in re.findall(r"\w+", normalized_query) if len(token) > 2}
    best_task = None
    best_score = 0

    for task in tasks:
        task_name = (task.get("title") or "").lower().strip()
        task_tokens = {token for token in re.findall(r"\w+", task_name) if len(token) > 2}
        overlap = len(query_tokens & task_tokens)
        if overlap > best_score:
            best_score = overlap
            best_task = task

    if best_score >= 1:
        return best_task

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
    if extracted_update.get("_parsed_time_only"):
        update_changes["_parsed_time_only"] = extracted_update["_parsed_time_only"]
    update_changes.pop("catering", None)
    update_changes.pop("event_size_hint", None)

    has_pending_create = bool(pending_event_draft)
    task_action = detect_task_action(message)

    create_triggered = should_prefer_create_over_update(
        message=message,
        extracted_create=extracted_create,
        update_changes=update_changes,
        pending_event_draft=pending_event_draft,
    )

    update_triggered = (
        not create_triggered
        and (looks_like_existing_event_edit(message) or looks_like_event_update(message))
    )

    if task_action == "create":
        task_fields = extract_task_fields(message)
        state["last_intent"] = "task_create"
        return {
            "type": "task_create",
            "task": task_fields,
            "reply": None,
            "state": state,
        }

    if task_action == "complete":
        task_fields = extract_task_fields(message)
        target_task = find_task_by_reference(task_fields.get("title"), context.get("tasks", []))
        state["last_intent"] = "task_complete"

        if task_fields.get("title") and target_task is None:
            return {
                "type": "task_complete_not_found",
                "task": task_fields,
                "reply": "I found your task request, but I couldn’t tell which task you meant. Try saying something like 'mark vendor confirmation done' or 'complete catering follow-up.'",
                "state": state,
            }

        return {
            "type": "task_complete",
            "task": task_fields,
            "target_task": target_task,
            "reply": None,
            "state": state,
        }

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

    if looks_like_event_creation(message) and has_meaningful_create_data(extracted_create):
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

    return {
        "type": "fallback",
        "reply": None,
        "state": state,
    }


def build_interpret_result_from_llm(llm_result, context, state):
    if not llm_result:
        return None

    action = llm_result.get("action")
    fields = llm_result.get("fields", {}) or {}
    state = state or get_default_chat_state()

    if action == "task_create":
        task_title = fields.get("task_title") or fields.get("title")
        if not task_title:
            return None
        return {
            "type": "task_create",
            "task_data": {
                "title": task_title,
                "status": "pending",
            },
            "reply": None,
            "state": state,
        }

    if action == "task_complete":
        task_title = fields.get("task_title") or fields.get("title")
        if not task_title:
            return None
        return {
            "type": "task_complete",
            "task_data": {
                "title": task_title,
                "status": "completed",
            },
            "reply": None,
            "state": state,
        }

    if action == "event_update":
        target_event = resolve_target_event("", context, state)
        if not target_event:
            return {
                "type": "event_update_needs_target",
                "reply": "I can update an event, but I couldn’t tell which one you meant.",
                "state": state,
            }

        changes = {}
        for key in ["title", "date", "location", "description", "guest_count"]:
            if fields.get(key) not in (None, "", []):
                changes[key] = fields[key]

        if fields.get("start_time"):
            changes["_parsed_time_only"] = fields["start_time"]

        if not changes:
            return None

        state["last_event_id"] = target_event["id"]
        state["last_intent"] = "event_update"
        state["last_changes"] = dict(changes)

        return {
            "type": "event_update",
            "target_event": target_event,
            "changes": changes,
            "reply": None,
            "state": state,
        }

    if action == "event_create":
        draft = {}
        for key in ["title", "date", "location", "description", "guest_count"]:
            if fields.get(key) not in (None, "", []):
                draft[key] = fields[key]
        if fields.get("start_time") and fields.get("date"):
            draft["start_datetime"] = f"{fields['date']}T{fields['start_time']}"

        if not draft:
            return None

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

    return None