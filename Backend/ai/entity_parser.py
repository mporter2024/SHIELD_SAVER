import re
from datetime import datetime

CURRENT_YEAR = datetime.now().year


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" .,!?"))


def _title_case_first(text: str):
    if not text:
        return text
    return text[0].upper() + text[1:]


def _extract_guest_count(message: str):
    patterns = [
        r"\bfor\s+about\s+(\d+)\s+people\b",
        r"\bfor\s+around\s+(\d+)\s+people\b",
        r"\bfor\s+roughly\s+(\d+)\s+people\b",
        r"\bfor\s+(\d+)\s+people\b",
        r"\babout\s+(\d+)\s+guests\b",
        r"\baround\s+(\d+)\s+guests\b",
        r"\b(\d+)\s+guests\b",
        r"\babout\s+(\d+)\s+attendees\b",
        r"\b(\d+)\s+attendees\b",
        r"\bguest count\s+(?:of\s+)?(\d+)\b",
        r"\bmake it\s+(\d+)\s+people\b",
        r"\bchange it to\s+(\d+)\s+people\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_date(message: str):
    lowered = message.lower()

    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }

    for month, month_num in month_map.items():
        pattern = rf"\b{month}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*(\d{{4}}))?\b"
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            year = int(match.group(2)) if match.group(2) else CURRENT_YEAR
            try:
                return datetime(year, month_num, day).strftime("%Y-%m-%d")
            except ValueError:
                return None

    numeric_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", lowered)
    if numeric_match:
        month_num = int(numeric_match.group(1))
        day = int(numeric_match.group(2))
        year = numeric_match.group(3)

        if year is None:
            year = CURRENT_YEAR
        else:
            year = int(year)
            if year < 100:
                year += 2000

        try:
            return datetime(year, month_num, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def _extract_time(message: str):
    match = re.search(
        r"\b(?:at|starting at|start at|starts at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        message,
        re.IGNORECASE
    )
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    meridiem = match.group(3).lower()

    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}:00"


def _extract_location(message: str):
    patterns = [
        r"\bat\s+([A-Za-z0-9\s&'\/\-]+?)(?:\s+for\s+|\s+on\s+|\s+with\s+|\.\s*|,\s*|$)",
        r"\bin\s+([A-Za-z0-9\s&'\/\-]+?)(?:\s+for\s+|\s+on\s+|\s+with\s+|\.\s*|,\s*|$)",
        r"\blocation\s+(?:is\s+)?([A-Za-z0-9\s&'\/\-]+?)(?:\.\s*|,\s*|$)",
    ]

    blocked = {
        "about", "around", "roughly", "approximately",
        "april", "may", "june", "july"
    }

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1))
            if candidate and candidate.lower() not in blocked:
                return candidate
    return None


def _extract_catering(message: str):
    patterns = [
        r"\bwith\s+(.+?)\s+catering\b",
        r"\bcatering\s+(?:from\s+|is\s+)?(.+?)(?:$|\.|,)",
        r"\bfood\s+from\s+(.+?)(?:$|\.|,)",
        r"\bcater(?:er|ing)?\s+(?:is\s+)?(.+?)(?:$|\.|,)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))
    return None


def _extract_title(message: str):
    patterns = [
        r"\bcalled\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\.\s*|,\s*|$)",
        r"\bnamed\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\.\s*|,\s*|$)",
        r"\btitle\s+it\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\.\s*|,\s*|$)",
        r"\bit'?s\s+called\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\.\s*|,\s*|$)",
        r"\bthe\s+title\s+is\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\.\s*|,\s*|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))
    return None


def _extract_description(message: str):
    patterns = [
        r"\bit'?s\s+for\s+(.+?)(?:$|\.)",
        r"\bthis is for\s+(.+?)(?:$|\.)",
        r"\bthe purpose is\s+(.+?)(?:$|\.)",
        r"\bdescription\s+(?:is\s+)?(.+?)(?:$|\.)",
        r"\bfor\s+(student networking|networking|fundraising|a fundraiser|celebration|meeting|conference|workshop|party)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return _title_case_first(_clean_text(match.group(1)))
    return None


def _extract_size_hint(message: str):
    lowered = message.lower()
    if "small event" in lowered or "small gathering" in lowered:
        return "small"
    if "medium event" in lowered or "medium-sized event" in lowered:
        return "medium"
    if "large event" in lowered or "big event" in lowered:
        return "large"
    return None


def extract_event_fields(message: str):
    message = message.strip()

    date_value = _extract_date(message)
    time_value = _extract_time(message)

    start_datetime = None
    if date_value and time_value:
        start_datetime = f"{date_value}T{time_value}"

    return {
        "title": _extract_title(message),
        "date": date_value,
        "start_datetime": start_datetime,
        "location": _extract_location(message),
        "description": _extract_description(message),
        "guest_count": _extract_guest_count(message),
        "catering": _extract_catering(message),
        "event_size_hint": _extract_size_hint(message),
    }


def looks_like_event_creation(message: str):
    lowered = message.lower()

    trigger_phrases = [
        "create an event",
        "create a event",
        "make an event",
        "plan an event",
        "plan a event",
        "organize an event",
        "set up an event",
        "i want to create",
        "i want to plan",
        "help me plan",
        "help me create an event",
    ]

    return any(phrase in lowered for phrase in trigger_phrases)


def looks_like_event_update(message: str):
    lowered = message.lower()

    update_phrases = [
        "actually",
        "change it to",
        "make it",
        "update it to",
        "the location is",
        "it's called",
        "it is called",
        "call it",
        "named",
        "catering is",
        "food is from",
        "it's for",
        "this is for",
        "description is",
    ]

    return any(phrase in lowered for phrase in update_phrases)


def merge_event_draft(existing: dict, new_data: dict):
    merged = dict(existing or {})
    for key, value in (new_data or {}).items():
        if value not in (None, "", []):
            merged[key] = value
    return merged


def missing_required_event_fields(draft: dict):
    required = ["title", "location", "description"]
    missing = [field for field in required if not draft.get(field)]

    if not draft.get("date") and not draft.get("start_datetime"):
        missing.append("date")

    return missing


def build_missing_fields_prompt(draft: dict):
    known_parts = []

    if draft.get("title"):
        known_parts.append(f"title as {draft['title']}")
    if draft.get("date"):
        known_parts.append(f"date as {draft['date']}")
    if draft.get("start_datetime"):
        known_parts.append(f"start time as {draft['start_datetime']}")
    if draft.get("location"):
        known_parts.append(f"location as {draft['location']}")
    if draft.get("guest_count"):
        known_parts.append(f"guest count as {draft['guest_count']}")
    if draft.get("catering"):
        known_parts.append(f"catering as {draft['catering']}")

    missing = missing_required_event_fields(draft)

    field_labels = {
        "title": "event title",
        "location": "location",
        "description": "short description",
        "date": "date",
    }

    missing_text = ", ".join(field_labels[field] for field in missing)

    if known_parts:
        return f"I’ve got {', '.join(known_parts)}. I still need the {missing_text}."
    return f"I can help create that event. I still need the {missing_text}."


def extract_event_update_fields(message: str):
    data = extract_event_fields(message)
    cleaned_message = message.strip()

    rename_patterns = [
        r"\brename\s+(?:it|the event)?\s*to\s+(.+?)(?:$|\.)",
        r"\bchange\s+(?:the title|title)\s+to\s+(.+?)(?:$|\.)",
        r"\bupdate\s+(?:the title|title)\s+to\s+(.+?)(?:$|\.)",
        r"\bset\s+(?:the title|title)\s+to\s+(.+?)(?:$|\.)",
        r"\bcall\s+it\s+(.+?)(?:$|\.)",
    ]
    for pattern in rename_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            data["title"] = _clean_text(match.group(1))
            break

    location_patterns = [
        r"\bset\s+the\s+location\s+to\s+(.+?)(?:$|\.)",
        r"\bchange\s+the\s+location\s+to\s+(.+?)(?:$|\.)",
        r"\bupdate\s+the\s+location\s+to\s+(.+?)(?:$|\.)",
        r"\blocation\s+is\s+(.+?)(?:$|\.)",
        r"\bmove\s+(?:it|the event)?\s+to\s+([A-Za-z0-9\s&'\/\-]+?)(?:$|\.)",
    ]
    for pattern in location_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1))
            parsed_date = _extract_date(candidate)
            if not parsed_date:
                data["location"] = candidate
                break

    description_patterns = [
        r"\bchange\s+the\s+description\s+to\s+(.+?)(?:$|\.)",
        r"\bupdate\s+the\s+description\s+to\s+(.+?)(?:$|\.)",
        r"\bset\s+the\s+description\s+to\s+(.+?)(?:$|\.)",
        r"\bdescription\s+is\s+(.+?)(?:$|\.)",
    ]
    for pattern in description_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            data["description"] = _title_case_first(_clean_text(match.group(1)))
            break

    guest_patterns = [
        r"\bset\s+the\s+guest\s+count\s+to\s+(\d+)\b",
        r"\bset\s+guest\s+count\s+to\s+(\d+)\b",
        r"\bchange\s+the\s+guest\s+count\s+to\s+(\d+)\b",
        r"\bchange\s+guest\s+count\s+to\s+(\d+)\b",
        r"\bupdate\s+the\s+guest\s+count\s+to\s+(\d+)\b",
        r"\bupdate\s+guest\s+count\s+to\s+(\d+)\b",
        r"\bmake\s+the\s+guest\s+count\s+(\d+)\b",
        r"\bguest\s+count\s+is\s+(\d+)\b",
        r"\bmake\s+it\s+(\d+)\s+people\b",
        r"\bmake\s+it\s+(\d+)\s+guests\b",
        r"\bset\s+it\s+to\s+(\d+)\s+people\b",
        r"\bset\s+it\s+to\s+(\d+)\s+guests\b",
        r"\bchange\s+it\s+to\s+(\d+)\s+people\b",
        r"\bchange\s+it\s+to\s+(\d+)\s+guests\b", 
    ]
    for pattern in guest_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            data["guest_count"] = int(match.group(1))
            break

    catering_patterns = [
        r"\bset\s+the\s+catering\s+to\s+(.+?)(?:$|\.)",
        r"\bchange\s+the\s+catering\s+to\s+(.+?)(?:$|\.)",
        r"\bupdate\s+the\s+catering\s+to\s+(.+?)(?:$|\.)",
        r"\bcatering\s+is\s+(.+?)(?:$|\.)",
        r"\bfood\s+is\s+from\s+(.+?)(?:$|\.)",
    ]
    for pattern in catering_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            data["catering"] = _clean_text(match.group(1))
            break

    parsed_date = _extract_date(cleaned_message)
    parsed_time = _extract_time(cleaned_message)

    if parsed_date:
        data["date"] = parsed_date

    time_only_patterns = [
        r"\bset\s+(?:the\s+start\s+time|start\s+time)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bchange\s+(?:the\s+start\s+time|start\s+time)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bupdate\s+(?:the\s+start\s+time|start\s+time)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bmake\s+it\s+start\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bmove\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    ]

    for pattern in time_only_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            meridiem = match.group(3).lower()

            if meridiem == "pm" and hour != 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0

            parsed_time = f"{hour:02d}:{minute:02d}:00"
            break

    if parsed_time:
        data["_parsed_time_only"] = parsed_time

    return data
