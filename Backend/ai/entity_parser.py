import re
from datetime import datetime, timedelta

CURRENT_YEAR = datetime.now().year


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" .,!?"))


def _title_case_first(text: str):
    if not text:
        return text
    return text[0].upper() + text[1:]


def _words_to_number(text: str):
    if not text:
        return None

    text = text.lower().replace("-", " ")
    parts = [p for p in text.split() if p in NUMBER_WORDS]

    if not parts:
        return None

    total = 0
    current = 0

    for part in parts:
        value = NUMBER_WORDS[part]
        if value == 100:
            current = max(current, 1) * 100
        else:
            current += value

    total += current
    return total if total > 0 else None


def _extract_guest_count(message: str):
    digit_patterns = [
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
        r"\bset it to\s+(\d+)\s+people\b",
        r"\bbump (?:it|attendance|guest count)\s+to\s+(\d+)\b",
        r"\bwe(?:'| a)?re expecting\s+(\d+)\b",
    ]

    for pattern in digit_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return int(match.group(1))

    word_patterns = [
        r"\bfor\s+([a-z\-\s]+?)\s+people\b",
        r"\bfor\s+([a-z\-\s]+?)\s+guests\b",
        r"\bmake it\s+([a-z\-\s]+?)\s+people\b",
        r"\bguest count\s+(?:of\s+)?([a-z\-\s]+)\b",
    ]

    for pattern in word_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = _words_to_number(match.group(1))
            if value is not None:
                return value

    return None


def _extract_date(message: str):
    lowered = message.lower()
    today = datetime.now()

    relative_map = {
        "today": 0,
        "tomorrow": 1,
    }

    for word, offset in relative_map.items():
        if re.search(rf"\b{word}\b", lowered):
            return (today + timedelta(days=offset)).strftime("%Y-%m-%d")

    weekday_names = [
        "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday"
    ]

    next_weekday_match = re.search(r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered)
    if next_weekday_match:
        target_name = next_weekday_match.group(1)
        target_idx = weekday_names.index(target_name)
        days_ahead = (target_idx - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    plain_weekday_match = re.search(r"\b(on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered)
    if plain_weekday_match:
        target_name = plain_weekday_match.group(2)
        target_idx = weekday_names.index(target_name)
        days_ahead = (target_idx - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

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


def looks_like_event_update(message: str):
    lowered = message.lower().strip()

    update_phrases = [
        "actually",
        "change it to",
        "change it",
        "update it to",
        "update it",
        "set it to",
        "set it",
        "move it to",
        "move it",
        "reschedule it to",
        "reschedule it",
        "rename it to",
        "rename it",
        "call it",
        "the location is",
        "location is",
        "change the location",
        "update the location",
        "set the location",
        "move the event to",
        "change the date",
        "update the date",
        "set the date",
        "change the time",
        "update the time",
        "set the time",
        "change the start time",
        "update the start time",
        "set the start time",
        "change the guest count",
        "update the guest count",
        "set the guest count",
        "guest count is",
        "make it",
        "bump it to",
        "switch it to",
        "push it to",
        "description is",
        "change the description",
        "update the description",
        "set the description",
        "catering is",
        "food is from",
        "change the catering",
        "update the catering",
        "set the catering",
        "change name to",
        "change the name to",
        "update name to",
        "update the name to",
        "set name to",
        "set the name to",
        "change the title to",
        "update the title to",
        "set the title to",
        ""
    ]

    if any(phrase in lowered for phrase in update_phrases):
        return True

    parsed_date = _extract_date(message)
    parsed_time = _extract_time(message)

    if parsed_date or parsed_time:
        if any(ref in lowered for ref in ["it", "that event", "this event", "the event", "that one", "this one"]):
            return True

    return False

def _extract_time(message: str):
    lowered = message.lower()

    if re.search(r"\bnoon\b", lowered):
        return "12:00:00"
    if re.search(r"\bmidnight\b", lowered):
        return "00:00:00"

    match = re.search(
        r"\b(?:at|starting at|start at|starts at|for|from|move it to|set it to)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        lowered,
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
        r"\bat\s+([A-Za-z0-9\s&'\/\-]+?)(?:\s+for\s+|\s+on\s+|\s+with\s+|\s+starting\b|\.\s*|,\s*|$)",
        r"\bin\s+([A-Za-z0-9\s&'\/\-]+?)(?:\s+for\s+|\s+on\s+|\s+with\s+|\s+starting\b|\.\s*|,\s*|$)",
        r"\blocation\s+(?:is\s+|to\s+)?([A-Za-z0-9\s&'\/\-]+?)(?:\.\s*|,\s*|$)",
    ]

    blocked = {
        "about", "around", "roughly", "approximately",
        "april", "may", "june", "july", "tomorrow", "today"
    }

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1))
            if candidate and candidate.lower() not in blocked:
                if _extract_date(candidate):
                    continue
                return candidate
    return None


def _extract_catering(message: str):
    patterns = [
        r"\bwith\s+(.+?)\s+catering\b",
        r"\bcatering\s+(?:from\s+|is\s+|to\s+)?(.+?)(?:$|\.|,)",
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
        r"\bcalled\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\s+in\s+|\.\s*|,\s*|$)",
        r"\bnamed\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\s+in\s+|\.\s*|,\s*|$)",
        r"\btitle\s+it\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\s+in\s+|\.\s*|,\s*|$)",
        r"\bit'?s\s+called\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\s+in\s+|\.\s*|,\s*|$)",
        r"\bthe\s+title\s+is\s+(.+?)(?:\s+on\s+|\s+at\s+|\s+for\s+|\s+with\s+|\s+in\s+|\.\s*|,\s*|$)",
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
        r"\bdescription\s+(?:is\s+|to\s+)?(.+?)(?:$|\.)",
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
        "create an",
        "create a",
        "make an event",
        "make a new event",
        "make an",
        "make a",
        "plan an event",
        "plan a event",
        "plan an",
        "plan a",
        "organize an event",
        "organize a",
        "set up an event",
        "set up a",
        "i want to create",
        "i want to plan",
        "help me plan",
        "help me create an event",
        "create event",
        "new event",
    ]

    return any(phrase in lowered for phrase in trigger_phrases)


def extract_event_update_fields(message: str):
    cleaned_message = message.strip()
    lowered = cleaned_message.lower()

    data = {
        "title": None,
        "date": None,
        "start_datetime": None,
        "location": None,
        "description": None,
        "guest_count": None,
        "catering": None,
        "event_size_hint": None,
    }

    rename_patterns = [
        r"\brename\s+(?:it|the event)?\s*to\s+(.+?)(?:$|\.)",
        r"\bchange\s+(?:the title|title)\s+to\s+(.+?)(?:$|\.)",
        r"\bupdate\s+(?:the title|title)\s+to\s+(.+?)(?:$|\.)",
        r"\bset\s+(?:the title|title)\s+to\s+(.+?)(?:$|\.)",
        r"\bcall\s+it\s+(.+?)(?:$|\.)",
        r"\bit'?s\s+called\s+(.+?)(?:$|\.)",
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
        r"\bmove\s+the\s+event\s+to\s+([A-Za-z0-9\s&'\/\-]+?)(?:$|\.)",
    ]
    for pattern in location_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1))
            if candidate and not _extract_date(candidate) and not _extract_time(candidate):
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
        r"\bbump\s+(?:it|attendance|guest count)\s+to\s+(\d+)\b",
        r"\bwe(?:'| a)?re expecting\s+(\d+)\b",
    ]
    for pattern in guest_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            data["guest_count"] = int(match.group(1))
            break

    if data["guest_count"] is None:
        guest_count_from_words = _extract_guest_count(cleaned_message)
        if guest_count_from_words is not None:
            data["guest_count"] = guest_count_from_words

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
        r"\bset\s+(?:the\s+start\s+time|start\s+time|time)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bchange\s+(?:the\s+start\s+time|start\s+time|time)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bupdate\s+(?:the\s+start\s+time|start\s+time|time)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bmake\s+it\s+start\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bmove\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bpush\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bswitch\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bupdate\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bset\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bchange\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\breschedule\s+it\s+to\s+(?:[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    ]

    matched_time_only = None
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

            matched_time_only = f"{hour:02d}:{minute:02d}:00"
            break

    if matched_time_only:
        data["_parsed_time_only"] = matched_time_only
    elif parsed_time and not parsed_date:
        data["_parsed_time_only"] = parsed_time

    if parsed_date and parsed_time:
        data["start_datetime"] = f"{parsed_date}T{parsed_time}"

    return data


def merge_event_draft(existing: dict, new_data: dict):
    merged = dict(existing or {})
    for key, value in (new_data or {}).items():
        if value not in (None, "", []):
            merged[key] = value
    return merged


def missing_required_event_fields(draft: dict):
    required = ["title", "location"]
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
    ]
    for pattern in location_patterns:
        match = re.search(pattern, cleaned_message, re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1))
            if not _extract_date(candidate):
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
        r"\bbump\s+(?:it|attendance|guest count)\s+to\s+(\d+)\b",
        r"\bwe(?:'| a)?re expecting\s+(\d+)\b",
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
        r"\bpush\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        r"\bswitch\s+it\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
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


PLANNING_DIETARY_KEYWORDS = [
    'vegetarian', 'vegan', 'gluten-free', 'gluten free', 'dairy-free', 'dairy free',
    'halal', 'kosher', 'nut-free', 'nut free'
]


CUISINE_KEYWORDS = [
    'italian', 'bbq', 'barbecue', 'mexican', 'pizza', 'american', 'seafood',
    'mediterranean', 'asian', 'soul food', 'new american'
]


SERVICE_TYPE_KEYWORDS = [
    'buffet', 'plated', 'drop-off', 'drop off', 'food truck', 'family style'
]


VENUE_TYPE_KEYWORDS = [
    'ballroom', 'theater', 'theatre', 'arena', 'banquet hall', 'pavilion',
    'park', 'waterfront', 'conference center', 'opera house', 'music venue'
]


STYLE_KEYWORDS = [
    'casual', 'modern', 'upscale', 'elegant', 'formal', 'historic', 'rustic'
]


def _extract_budget_level(message: str):
    lowered = message.lower()
    if any(phrase in lowered for phrase in ['affordable', 'budget-friendly', 'budget friendly', 'cheap', 'low cost']):
        return 'budget'
    if any(phrase in lowered for phrase in ['mid-range', 'mid range', 'moderate']):
        return 'mid'
    if any(phrase in lowered for phrase in ['upscale', 'premium', 'luxury', 'high-end', 'high end', 'formal']):
        return 'premium'
    return None


def _extract_money_amount(message: str, labels):
    label_pattern = '|'.join(re.escape(label) for label in labels)
    patterns = [
        rf'(?:under|below|less than|max(?:imum)? of)\s*\$?(\d+(?:\.\d+)?)',
        rf'(?:{label_pattern})\s+(?:under|below|of|around|about)?\s*\$?(\d+(?:\.\d+)?)',
        rf'\$\s*(\d+(?:\.\d+)?)\s*(?:max|budget)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def extract_planning_preferences(message: str):
    lowered = (message or '').lower()
    preferences = {
        'event_type': None,
        'guest_count': _extract_guest_count(message),
        'date': _extract_date(message),
        'location_area': _extract_location(message),
        'budget_level': _extract_budget_level(message),
        'max_budget_total': _extract_money_amount(message, ['venue budget', 'venue', 'space', 'location']),
        'budget_per_person': _extract_money_amount(message, ['per person', 'head', 'catering budget', 'food budget', 'catering']),
        'indoor_outdoor': None,
        'venue_type': None,
        'style': None,
        'parking': None,
        'accessibility': None,
        'cuisine': None,
        'service_type': None,
        'dietary_needs': [],
    }

    if 'graduation' in lowered:
        preferences['event_type'] = 'graduation'
    elif 'wedding' in lowered:
        preferences['event_type'] = 'wedding'
    elif 'birthday' in lowered:
        preferences['event_type'] = 'birthday'
    elif 'conference' in lowered or 'corporate' in lowered:
        preferences['event_type'] = 'corporate'
    elif 'party' in lowered:
        preferences['event_type'] = 'party'

    if 'indoor' in lowered:
        preferences['indoor_outdoor'] = 'indoor'
    elif 'outdoor' in lowered:
        preferences['indoor_outdoor'] = 'outdoor'

    for keyword in VENUE_TYPE_KEYWORDS:
        if keyword in lowered:
            preferences['venue_type'] = keyword
            break

    for keyword in STYLE_KEYWORDS:
        if keyword in lowered:
            preferences['style'] = keyword
            break

    for keyword in CUISINE_KEYWORDS:
        if keyword in lowered:
            preferences['cuisine'] = 'bbq' if keyword == 'barbecue' else keyword
            break

    for keyword in SERVICE_TYPE_KEYWORDS:
        if keyword in lowered:
            preferences['service_type'] = keyword.replace('drop off', 'drop-off')
            break

    dietary = []
    for keyword in PLANNING_DIETARY_KEYWORDS:
        if keyword in lowered:
            dietary.append(keyword.replace('gluten free', 'gluten-free').replace('dairy free', 'dairy-free').replace('nut free', 'nut-free'))
    preferences['dietary_needs'] = sorted(set(dietary))

    if 'parking' in lowered:
        preferences['parking'] = True
    if 'accessible' in lowered or 'accessibility' in lowered or 'wheelchair' in lowered:
        preferences['accessibility'] = True

    return preferences
