import re
from copy import deepcopy

from ai.entity_parser import (
    build_missing_fields_prompt,
    detect_task_action,
    extract_event_fields,
    extract_event_update_fields,
    extract_task_fields,
    looks_like_event_creation,
    looks_like_event_update,
    merge_event_draft,
    missing_required_event_fields,
)


REFERENCE_WORDS = (
    "it",
    "that event",
    "this event",
    "the event",
    "that one",
    "this one",
)

CREATE_INTENT_PATTERNS = [
    r"\bcreate\b",
    r"\bplan\b",
    r"\bset\s+up\b",
    r"\bsetup\b",
    r"\borganize\b",
    r"\bmake\b",
    r"\bschedule\b",
    r"\bstart\b",
    r"\bhelp\s+me\s+create\b",
    r"\bhelp\s+me\s+plan\b",
    r"\bcan\s+you\s+create\b",
    r"\bcan\s+you\s+plan\b",
    r"\blet'?s\s+plan\b",
    r"\bi\s+want\s+to\s+create\b",
    r"\bi\s+want\s+to\s+plan\b",
    r"\bnew\s+event\b",
    r"\bevent\s+called\b",
    r"\bevent\s+named\b",
    r"\bsomething\s+called\b",
    r"\bsomething\s+named\b",
    r"\bon\s+the\s+calendar\b",
    r"\bon\s+the\s+books\b",
    r"\bto\s+the\s+planner\b",
    r"\blaunch\s+an\s+event\s+record\b",
    r"\bbuild\s+out\b.*\bas\s+an\s+event\b",
    r"\bneeds\s+to\s+be\s+created\b",
    r"\btrying\s+to\s+host\b",
    r"\bneed\s+to\s+host\b",
    r"\bi'?d\s+like\b.*\badded\b",
    r"\bfor\s+me\s+add\b",
    r"\bwhen\s+you\s+can\s+add\b",
    r"\b(?:okay|ok|hey|quickly)\s+add\b",
    r"\b(?:can\s+you\s+|could\s+you\s+|please\s+|will\s+you\s+)?add\s+.+?\s+on\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}",
    r"\bi'?m\s+planning\s+.+?;\s+set\s+it\s+for\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}",
]

STRONG_UPDATE_PATTERNS = [
    r"\bchange\b",
    r"\bupdate\b",
    r"\bmove\b",
    r"\breschedule\b",
    r"\brename\b",
    r"\bedit\b",
    r"\bswitch\b",
    r"\bpush\b",
    r"\bbump\b",
    r"\badjust\b",
    r"\brevise\b",
    r"\bincrease\b",
    r"\bset\s+it\s+to\b",
    r"\bchange\s+the\s+(?:date|time|location|title|name|description|guest count|catering)\b",
    r"\bupdate\s+the\s+(?:date|time|location|title|name|description|guest count|catering)\b",
    r"\bset\s+the\s+(?:date|time|location|title|name|description|guest count|catering|venue)\b",
    r"\blocation\s+is\b",
    r"\bdescription\s+is\b",
    r"\bguest\s+count\s+is\b",
    r"\bcall\s+it\b",
    r"\bmake\s+it\b",
    r"\bchange\s+when\b",
    r"\bthe\s+new\s+date\b",
    r"\bstarts\s+to\b",
    r"\battendance\s+is\b",
    r"\battendance\s+to\b",
    r"\bguest\s+count\s+for\b",
    r"\bvenue\s+for\b",
    r"\bvenue\s+on\b",
]

TASK_CREATE_PATTERNS = [
    r"\btrack\s+(?:a\s+)?task\s+for\s+(.+)$",
    r"\b(?:can|could|would|will)\s+you\s+(?:please\s+)?add\s+(?:a\s+)?task\s+for\s+(.+)$",
    r"\b(?:can|could|would|will)\s+you\s+add\s+task\s+(.+)$",
    r"\b(?:would\s+you\s+please|please)\s+add\s+(?:a\s+)?task\s+for\s+(.+)$",
    r"\badd\s+(.+?)\s+as\s+a\s+task$",
    r"\bput\s+(.+?)\s+on\s+my\s+to-?do\s+list$",
    r"\bput\s+(.+?)\s+on\s+my\s+task\s+list$",
    r"\bplease\s+add\s+(.+?)\s+to\s+the\s+task\s+list$",
    r"\badd\s+(.+?)\s+to\s+the\s+task\s+list$",
    r"\blog\s+a\s+task\s+that\s+says\s+(.+)$",
    r"\badd\s+a\s+checklist\s+item\s+to\s+(.+)$",
    r"\bi\s+need\s+a\s+task\s+for\s+(.+)$",
    r"\bi\s+want\s+a\s+task\s+for\s+(.+)$",
    r"\bcan\s+you\s+add\s+a\s+task\s+for\s+(.+)$",
    r"\bcould\s+you\s+add\s+a\s+task\s+for\s+(.+)$",
    r"\bwould\s+you\s+add\s+a\s+task\s+for\s+(.+)$",
    r"\bwill\s+you\s+add\s+a\s+task\s+for\s+(.+)$",
    r"\bwould\s+you\s+please\s+add\s+a\s+task\s+for\s+(.+)$",
    r"\bcan\s+you\s+add\s+task\s+(.+)$",
]

TASK_COMPLETE_PATTERNS = [
    r"\bset\s+(.+?)\s+to\s+finished$",
    r"\b(?:would|will|can|could)\s+you\s+(?:please\s+)?mark\s+(.+?)\s+complete$",
    r"\b(?:would|will|can|could)\s+you\s+mark\s+(.+?)\s+complete$",
    r"\bmark\s+the\s+task\s+(.+?)\s+as\s+complete$",
    r"\bmark\s+off\s+(.+)$",
    r"\bcheck\s+off\s+(.+)$",
    r"\bclose\s+out\s+(.+)$",
    r"\bfinish\s+(.+)$",
    r"\bcomplete\s+(.+)$",
    r"\b(.+?)\s+has\s+been\s+completed$",
    r"\b(.+?)\s+is\s+done$",
    r"\bmark\s+(.+?)\s+as\s+done$",
    r"\bmark\s+(.+?)\s+completed$",
    r"\bmark\s+(.+?)\s+complete$",
]

MONTH_PATTERN = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?"
TIME_PATTERN = r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon|midnight)"


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


def has_meaningful_create_data(extracted_create: dict) -> bool:
    return any(
        extracted_create.get(key) not in (None, "", [])
        for key in ["title", "date", "start_datetime", "location", "guest_count", "description"]
    )


def has_meaningful_update_data(extracted_update: dict) -> bool:
    return any(
        extracted_update.get(key) not in (None, "", [])
        for key in ["title", "date", "location", "guest_count", "description", "start_datetime"]
    ) or bool(extracted_update.get("_parsed_time_only"))


def _matches_any_pattern(message: str, patterns: list[str]) -> bool:
    lowered = message.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def looks_like_existing_event_edit(message: str) -> bool:
    return _matches_any_pattern(message or "", STRONG_UPDATE_PATTERNS)


def _clean_capture(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\b(?:for me|please|thanks)\b$", "", value, flags=re.IGNORECASE).strip(" .,!?;:")
    return value or None


def _supplement_task_action(message: str):
    lowered = message.lower().strip()
    for pattern in TASK_COMPLETE_PATTERNS:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            return "complete", _clean_capture(match.group(1))
    for pattern in TASK_CREATE_PATTERNS:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            return "create", _clean_capture(match.group(1))
    return None, None


def _extract_title_from_soft_create(message: str) -> str | None:
    patterns = [
        rf"(?:please\s+)?put\s+(.+?)\s+on\s+the\s+calendar\s+for\s+{MONTH_PATTERN}",
        rf"(?:please\s+)?get\s+(.+?)\s+on\s+the\s+books\s+for\s+{MONTH_PATTERN}",
        rf"(?:can\s+you\s+|could\s+you\s+|please\s+)?add\s+(.+?)\s+to\s+the\s+planner\s+for\s+{MONTH_PATTERN}",
        rf"launch\s+an\s+event\s+record\s+for\s+(.+?)\s+on\s+{MONTH_PATTERN}",
        rf"build\s+out\s+(.+?)\s+as\s+an\s+event\s+on\s+{MONTH_PATTERN}",
        rf"(.+?)\s+needs\s+to\s+be\s+created\s+for\s+{MONTH_PATTERN}",
        rf"i(?:'m|\s+am)?\s+trying\s+to\s+host\s+(.+?)\s+(?:in|at)\s+",
        rf"i\s+need\s+to\s+host\s+(.+?)\s+(?:in|at)\s+",
        rf"i(?:'d|\s+would)?\s+like\s+(.+?)\s+added\s+for\s+{MONTH_PATTERN}",
        rf"(?:okay|ok|hey|quickly)\s+add\s+(.+?)\s+on\s+{MONTH_PATTERN}",
        rf"for\s+me\s+add\s+(.+?)\s+on\s+{MONTH_PATTERN}",
        rf"when\s+you\s+can\s+add\s+(.+?)\s+on\s+{MONTH_PATTERN}",
        rf"set\s+an\s+event\s+up\s+for\s+me\s+called\s+(.+?)\s+(?:at|in)\s+",
        rf"(?:can\s+you\s+|could\s+you\s+|please\s+)?add\s+(.+?)\s+on\s+{MONTH_PATTERN}",
        rf"(?:can\s+you\s+|could\s+you\s+|please\s+)?add\s+(.+?)\s+for\s+{MONTH_PATTERN}",
        rf"i'?m\s+planning\s+(.+?);\s+set\s+it\s+for\s+{MONTH_PATTERN}",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return _clean_capture(match.group(1))
    return None


def _supplement_event_create_fields(message: str, extracted: dict) -> dict:
    result = dict(extracted or {})
    if not result.get("title"):
        result["title"] = _extract_title_from_soft_create(message)
    return result


def _extract_update_fields_supplement(message: str) -> dict:
    cleaned = message.strip()
    data = {}

    patterns = [
        ("title", rf"update\s+the\s+title\s+of\s+.+?\s+to\s+(.+)$"),
        ("title", rf"change\s+the\s+event\s+name\s+from\s+.+?\s+to\s+(.+)$"),
        ("title", rf"for\s+.+?,\s*rename\s+it\s+(.+)$"),
        ("title", rf"(?:can|could|will|would)\s+you\s+(?:please\s+)?rename\s+.+?\s+to\s+(.+)$"),
        ("title", rf"(?:would\s+you\s+please\s+)?rename\s+.+?\s+to\s+(.+)$"),
        ("title", rf"rename\s+.+?\s+to\s+(.+)$"),
        ("location", rf"switch\s+the\s+venue\s+for\s+.+?\s+to\s+(.+)$"),
        ("location", rf"set\s+the\s+venue\s+on\s+.+?\s+as\s+(.+)$"),
        ("location", rf"for\s+.+?,\s*switch\s+it\s+to\s+(.+)$"),
        ("location", rf"change\s+.+?\s+so\s+it\s+is\s+in\s+(.+)$"),
        ("location", rf"change\s+.+?\s+so\s+it\s+is\s+at\s+(.+)$"),
        ("location", rf"move\s+.+?\s+over\s+to\s+(.+?)\s+and\s+set\s+it\s+for\s+.+$"),
        ("location", rf"change\s+the\s+location\s+of\s+.+?\s+to\s+(.+)$"),
        ("description", rf"revise\s+the\s+description\s+for\s+.+?\s+to\s+(.+)$"),
        ("guest_count", rf"set\s+.+?\s+to\s+(\d+)\s+guests$"),
        ("guest_count", rf"increase\s+the\s+guest\s+count\s+for\s+.+?\s+to\s+(\d+)$"),
        ("guest_count", rf"edit\s+.+?\s+so\s+the\s+attendance\s+is\s+(\d+)$"),
        ("guest_count", rf"for\s+.+?,\s*bump\s+attendance\s+to\s+(\d+)$"),
        ("guest_count", rf"edit\s+.+?\s+so\s+the\s+attendance\s+is\s+(\d+)$"),
        ("guest_count", rf"set\s+.+?\s+to\s+(\d+)\s+guests$"),
    ]

    for field, pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            value = _clean_capture(match.group(1))
            if field == "guest_count":
                data[field] = int(value)
            else:
                data[field] = value
            return data

    time_match = re.search(r"change\s+when\s+.+?\s+starts\s+to\s+(.+)$", cleaned, re.IGNORECASE)
    if time_match:
        time_text = time_match.group(1).strip().lower()
        if time_text == "noon":
            data["_parsed_time_only"] = "12:00:00"
            return data
        if time_text == "midnight":
            data["_parsed_time_only"] = "00:00:00"
            return data
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_text)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2) or 0)
            mer = m.group(3).lower()
            if mer == "pm" and hour != 12:
                hour += 12
            if mer == "am" and hour == 12:
                hour = 0
            data["_parsed_time_only"] = f"{hour:02d}:{minute:02d}:00"
            return data

    # date/time combinations and looser update phrasing
    if re.search(r"\b(?:push|adjust|reschedule|move|change|update)\b", cleaned, re.IGNORECASE):
        date_match = re.search(MONTH_PATTERN, cleaned, re.IGNORECASE)
        if date_match:
            data["date"] = date_match.group(0)
        time_match2 = re.search(TIME_PATTERN, cleaned, re.IGNORECASE)
        if time_match2:
            time_text = time_match2.group(0).strip().lower()
            if time_text == "noon":
                data["_parsed_time_only"] = "12:00:00"
            elif time_text == "midnight":
                data["_parsed_time_only"] = "00:00:00"
            else:
                m2 = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_text)
                if m2:
                    hour = int(m2.group(1))
                    minute = int(m2.group(2) or 0)
                    mer = m2.group(3).lower()
                    if mer == "pm" and hour != 12:
                        hour += 12
                    if mer == "am" and hour == 12:
                        hour = 0
                    data["_parsed_time_only"] = f"{hour:02d}:{minute:02d}:00"
        return data

    return data




def _extract_event_reference_from_update(message: str) -> str | None:
    cleaned = message.strip()
    patterns = [
        r"(?:can|could|would|will)\s+you\s+(?:please\s+)?rename\s+(.+?)\s+to\s+.+$",
        r"(?:would\s+you\s+please\s+)?rename\s+(.+?)\s+to\s+.+$",
        r"rename\s+(.+?)\s+to\s+.+$",
        r"update\s+the\s+title\s+of\s+(.+?)\s+to\s+.+$",
        r"change\s+the\s+event\s+name\s+from\s+(.+?)\s+to\s+.+$",
        r"for\s+(.+?),\s*rename\s+it\s+.+$",
        r"switch\s+the\s+venue\s+for\s+(.+?)\s+to\s+.+$",
        r"set\s+the\s+venue\s+on\s+(.+?)\s+as\s+.+$",
        r"change\s+the\s+location\s+of\s+(.+?)\s+to\s+.+$",
        r"change\s+(.+?)\s+so\s+it\s+is\s+(?:in|at)\s+.+$",
        r"for\s+(.+?),\s*switch\s+it\s+to\s+.+$",
        r"for\s+(.+?),\s*move\s+it\s+to\s+.+$",
        r"move\s+(.+?)\s+over\s+to\s+.+$",
        r"move\s+(.+?)\s+to\s+.+$",
        r"reschedule\s+(.+?)\s+for\s+.+$",
        r"push\s+(.+?)\s+back\s+to\s+.+$",
        r"adjust\s+(.+?)\s+to\s+.+$",
        r"change\s+when\s+(.+?)\s+starts\s+to\s+.+$",
        r"update\s+(.+?)\s+so\s+it\s+starts\s+at\s+.+$",
        r"change\s+the\s+details\s+for\s+(.+?)\s+to\s+.+$",
        r"change\s+(.+?)\s+so\s+the\s+new\s+date\s+is\s+.+$",
        r"edit\s+(.+?)\s+so\s+the\s+attendance\s+is\s+.+$",
        r"set\s+(.+?)\s+to\s+\d+\s+guests$",
        r"increase\s+the\s+guest\s+count\s+for\s+(.+?)\s+to\s+.+$",
        r"for\s+(.+?),\s*bump\s+attendance\s+to\s+.+$",
        r"revise\s+the\s+description\s+for\s+(.+?)\s+to\s+.+$",
    ]
    for pattern in patterns:
        m = re.search(pattern, cleaned, re.IGNORECASE)
        if m:
            return _clean_capture(m.group(1))
    return None

def should_force_create(message: str, extracted_create: dict, pending_event_draft: dict) -> bool:
    if pending_event_draft:
        return True

    if looks_like_existing_event_edit(message):
        return False

    if _matches_any_pattern(message or "", CREATE_INTENT_PATTERNS):
        return True

    return looks_like_event_creation(message) and has_meaningful_create_data(extracted_create)


def should_force_update(message: str, extracted_update: dict) -> bool:
    if looks_like_existing_event_edit(message):
        return True

    if looks_like_event_update(message) and has_meaningful_update_data(extracted_update):
        return True

    if _extract_update_fields_supplement(message):
        return True

    return False


def find_event_by_title_reference(user_message, events):
    lowered_message = normalize_text(user_message)
    message_words = set(lowered_message.split())

    exact_match = None
    partial_match = None
    best_overlap_match = None
    best_overlap_score = 0

    for event in events:
        title = (event.get("title") or "").strip()
        if not title:
            continue

        normalized_title = normalize_text(title)
        title_words = set(normalized_title.split())

        if normalized_title == lowered_message:
            return event

        if normalized_title and normalized_title in lowered_message and exact_match is None:
            exact_match = event

        overlap = len(title_words.intersection(message_words)) if title_words else 0
        if overlap > best_overlap_score:
            best_overlap_score = overlap
            best_overlap_match = event

        if normalized_title and (normalized_title in lowered_message or lowered_message in normalized_title):
            partial_match = partial_match or event

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


def _clean_update_changes(extracted_update: dict) -> dict:
    update_changes = {
        key: value
        for key, value in extracted_update.items()
        if value not in (None, "", [])
    }
    if extracted_update.get("_parsed_time_only"):
        update_changes["_parsed_time_only"] = extracted_update["_parsed_time_only"]

    update_changes.pop("catering", None)
    update_changes.pop("event_size_hint", None)
    return update_changes


def _build_create_result(draft: dict, state: dict) -> dict:
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


def interpret_message(message, context, state):
    state = deepcopy(state or get_default_chat_state())
    context = context or {"events": [], "tasks": []}

    pending_event_draft = state.get("pending_event_draft") or {}
    extracted_create = _supplement_event_create_fields(message, extract_event_fields(message))
    extracted_update = extract_event_update_fields(message)
    extracted_update.update({k: v for k, v in _extract_update_fields_supplement(message).items() if v not in (None, "", [])})
    update_changes = _clean_update_changes(extracted_update)

    task_action = detect_task_action(message)
    task_fields = extract_task_fields(message)
    supplemental_task_action, supplemental_task_title = _supplement_task_action(message)

    if supplemental_task_action:
        task_action = supplemental_task_action
        task_fields = {
            "title": supplemental_task_title,
            "status": "pending" if task_action == "create" else "completed",
        }

    if task_action == "create":
        state["last_intent"] = "task_create"
        return {
            "type": "task_create",
            "task": task_fields,
            "reply": None,
            "state": state,
        }

    if task_action == "complete":
        target_task = find_task_by_reference(task_fields.get("title"), context.get("tasks", []))
        state["last_intent"] = "task_complete"
        return {
            "type": "task_complete",
            "task": task_fields,
            "target_task": target_task,
            "reply": None,
            "state": state,
        }

    create_triggered = should_force_create(message, extracted_create, pending_event_draft)
    update_triggered = False if create_triggered else should_force_update(message, extracted_update)

    if create_triggered:
        draft = merge_event_draft(pending_event_draft, extracted_create)
        return _build_create_result(draft, state)

    if update_triggered:
        target_event = resolve_target_event(message, context, state)

        if not target_event:
            referenced_title = _extract_event_reference_from_update(message)
            if referenced_title:
                target_event = {"id": state.get("last_event_id"), "title": referenced_title}
            else:
                return {
                    "type": "event_update_needs_target",
                    "reply": "I can update an event, but I couldn’t tell which one you meant. Please mention the event title.",
                    "state": state,
                }

        if not update_changes:
            return {
                "type": "event_update",
                "target_event": target_event,
                "changes": {},
                "reply": None,
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

    if has_meaningful_create_data(extracted_create) and (looks_like_event_creation(message) or _matches_any_pattern(message, CREATE_INTENT_PATTERNS)):
        draft = merge_event_draft(pending_event_draft, extracted_create)
        return _build_create_result(draft, state)

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

        return _build_create_result(draft, state)

    return None
