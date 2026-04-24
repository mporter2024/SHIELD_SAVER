from flask import current_app
from ai.llm_fallback import safe_ollama_interpret
from ai.action_interpreter import build_interpret_result_from_llm
from flask import Blueprint, request, jsonify, session
from ai.unified_chatbot import UnifiedChatbot
from ai.action_interpreter import interpret_message, get_default_chat_state, resolve_target_event
from ai.entity_parser import extract_planning_preferences
from ai.planning_engine import search_venues, search_caterers
from models.database import get_db
import sqlite3
import re
from datetime import datetime
from ai.budget_engine import analyze_budget, calculate_budget_totals


ai_bp = Blueprint("ai", __name__)
chatbot = UnifiedChatbot()


YES_WORDS = {
    "yes", "yeah", "yep", "sure", "ok", "okay", "do that", "go ahead",
    "please do", "add them", "sounds good", "absolutely", "definitely"
}

NO_WORDS = {
    "no", "nope", "not now", "maybe later", "don't", "do not"
}


FOLLOWUP_TASK_KEYWORDS = {
    "venue": ["Confirm venue"],
    "catering": ["Arrange catering"],
    "cater": ["Arrange catering"],
    "invite": ["Send invitations"],
    "invitations": ["Send invitations"],
    "guest": ["Prepare guest check-in list"],
    "check-in": ["Prepare guest check-in list"],
    "check in": ["Prepare guest check-in list"],
    "name tag": ["Arrange name tags"],
    "name tags": ["Arrange name tags"],
    "donation": ["Set up donation process"],
    "promo": ["Prepare promotional materials"],
    "promotional": ["Prepare promotional materials"],
    "sponsor": ["Reach out to sponsors"],
    "speaker": ["Confirm speaker or facilitator"],
    "materials": ["Prepare presentation materials"],
    "equipment": ["Test room equipment"],
    "decorations": ["Plan decorations"],
    "music": ["Prepare music or entertainment"],
    "entertainment": ["Prepare music or entertainment"],
    "staff": ["Assign event staff or volunteers"],
    "volunteer": ["Assign event staff or volunteers"],
    "seating": ["Review crowd flow and seating"],
    "security": ["Review security needs"],
}


def load_user_context(user_id):
    db = get_db()

    events = db.execute(
        """
        SELECT id, title, date, start_datetime, end_datetime, location, description,
               guest_count, budget_total, budget_limit, selected_venue, selected_catering,
               estimated_venue_cost, estimated_catering_cost
        FROM events
        WHERE user_id = ?
        ORDER BY COALESCE(start_datetime, date) ASC, id DESC
        """,
        (user_id,)
    ).fetchall()

    tasks = db.execute(
        """
        SELECT tasks.id, tasks.event_id, tasks.title, tasks.completed,
               tasks.due_date, tasks.start_datetime, tasks.end_datetime
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE events.user_id = ?
        ORDER BY COALESCE(tasks.start_datetime, tasks.due_date) ASC, tasks.id DESC
        """,
        (user_id,)
    ).fetchall()

    return {
        "events": [dict(row) for row in events],
        "tasks": [dict(row) for row in tasks]
    }


def create_task_for_user(user_id, task_data):
    db = get_db()
    event_id = task_data["event_id"]

    owned_event = db.execute(
        "SELECT id, title FROM events WHERE id = ? AND user_id = ?",
        (event_id, user_id)
    ).fetchone()

    if owned_event is None:
        return None, "That event does not belong to the current user."

    due_date = task_data.get("due_date")
    start_datetime = task_data.get("start_datetime")
    end_datetime = task_data.get("end_datetime")

    try:
        cursor = db.execute(
            """
            INSERT INTO tasks (event_id, title, completed, due_date, start_datetime, end_datetime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task_data["event_id"],
                task_data["title"],
                0,
                due_date or (start_datetime[:10] if start_datetime else None),
                start_datetime,
                end_datetime,
            )
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return None, f"Database error: {str(e)}"

    return {
        "id": cursor.lastrowid,
        "event_id": task_data["event_id"],
        "title": task_data["title"],
        "completed": 0,
        "due_date": due_date or (start_datetime[:10] if start_datetime else None),
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "event_title": owned_event["title"]
    }, None


def complete_task_for_user(user_id, task_id):
    db = get_db()

    task = db.execute(
        """
        SELECT tasks.id, tasks.title, tasks.completed, tasks.event_id, events.title AS event_title
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE tasks.id = ? AND events.user_id = ?
        """,
        (task_id, user_id)
    ).fetchone()

    if task is None:
        return None, "That task was not found for the current user."

    if int(task["completed"]) == 1:
        return None, f"'{task['title']}' is already marked complete."

    db.execute(
        "UPDATE tasks SET completed = 1 WHERE id = ?",
        (task_id,)
    )
    db.commit()

    return {
        "id": task["id"],
        "title": task["title"],
        "event_id": task["event_id"],
        "event_title": task["event_title"],
        "completed": 1
    }, None


def create_event_for_user(user_id, event_data):
    db = get_db()

    start_datetime = event_data.get("start_datetime")
    date = event_data.get("date") or (start_datetime[:10] if start_datetime else None)

    cursor = db.execute(
        """
        INSERT INTO events (
            title, date, start_datetime, end_datetime, location, description,
            guest_count, venue_cost, food_cost_per_person, decorations_cost,
            equipment_cost, staff_cost, marketing_cost, misc_cost,
            contingency_percent, budget_subtotal, budget_contingency, budget_total,
            budget_limit, selected_venue, selected_catering, estimated_venue_cost, estimated_catering_cost,
            user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_data.get("title"),
            date,
            start_datetime,
            event_data.get("end_datetime"),
            event_data.get("location"),
            event_data.get("description"),
            int(event_data.get("guest_count") or 0),
            float(event_data.get("venue_cost") or 0),
            float(event_data.get("food_cost_per_person") or 0),
            float(event_data.get("decorations_cost") or 0),
            float(event_data.get("equipment_cost") or 0),
            float(event_data.get("staff_cost") or 0),
            float(event_data.get("marketing_cost") or 0),
            float(event_data.get("misc_cost") or 0),
            float(event_data.get("contingency_percent") or 0),
            float(event_data.get("budget_subtotal") or 0),
            float(event_data.get("budget_contingency") or 0),
            float(event_data.get("budget_total") or 0),
            float(event_data.get("budget_limit") or event_data.get("max_budget_total") or 0),
            event_data.get("selected_venue"),
            event_data.get("selected_catering") or event_data.get("catering"),
            float(event_data.get("estimated_venue_cost") or event_data.get("venue_cost") or 0),
            float(event_data.get("estimated_catering_cost") or 0),
            user_id,
        )
    )
    db.commit()

    return {
        "id": cursor.lastrowid,
        "title": event_data.get("title"),
        "date": date,
        "start_datetime": start_datetime,
        "location": event_data.get("location"),
        "description": event_data.get("description"),
        "guest_count": int(event_data.get("guest_count") or 0),
        "catering": event_data.get("selected_catering") or event_data.get("catering"),
        "budget_limit": float(event_data.get("budget_limit") or event_data.get("max_budget_total") or 0),
    }


def update_event_in_db(event_id, updated_fields):
    db = get_db()

    allowed_fields = {
        "title",
        "date",
        "start_datetime",
        "end_datetime",
        "location",
        "description",
        "guest_count",
        "venue_cost",
        "food_cost_per_person",
        "decorations_cost",
        "equipment_cost",
        "staff_cost",
        "marketing_cost",
        "misc_cost",
        "contingency_percent",
        "budget_subtotal",
        "budget_contingency",
        "budget_total",
        "budget_limit",
        "selected_venue",
        "selected_catering",
        "estimated_venue_cost",
        "estimated_catering_cost",
    }

    set_clauses = []
    values = []

    for key, value in updated_fields.items():
        if key in allowed_fields and value is not None:
            set_clauses.append(f"{key} = ?")
            values.append(value)

    if not set_clauses:
        return False

    values.append(event_id)

    db.execute(
        f"""
        UPDATE events
        SET {', '.join(set_clauses)}
        WHERE id = ?
        """,
        values
    )
    db.commit()
    return True


def _get_chat_state():
    state = session.get("chat_state")
    if not isinstance(state, dict):
        state = get_default_chat_state()

    if session.get("last_event_id") and not state.get("last_event_id"):
        state["last_event_id"] = session.get("last_event_id")

    if session.get("pending_event_draft") and not state.get("pending_event_draft"):
        state["pending_event_draft"] = session.get("pending_event_draft")

    if "pending_followup" not in state:
        state["pending_followup"] = None

    if "planning_context" not in state or not isinstance(state.get("planning_context"), dict):
        state["planning_context"] = _default_planning_context()
    else:
        state["planning_context"] = _merge_planning_context(state.get("planning_context"), {})

    return state


def _save_chat_state(state):
    state = dict(state or {})
    state["planning_context"] = _merge_planning_context(state.get("planning_context"), {})
    session["chat_state"] = state
    session["last_event_id"] = state.get("last_event_id")
    session["pending_event_draft"] = state.get("pending_event_draft") or {}


def _default_planning_context():
    return {
        "event_type": None,
        "guest_count": None,
        "date": None,
        "location_area": None,
        "budget_level": None,
        "max_budget_total": None,
        "budget_per_person": None,
        "indoor_outdoor": None,
        "venue_type": None,
        "style": None,
        "parking": None,
        "accessibility": None,
        "cuisine": None,
        "service_type": None,
        "dietary_needs": [],
        "last_recommendations": {"venues": [], "caterers": []},
    }


def _merge_planning_context(existing, updates):
    merged = _default_planning_context()
    if isinstance(existing, dict):
        for key, value in existing.items():
            if key == "last_recommendations" and isinstance(value, dict):
                merged[key] = {
                    "venues": list(value.get("venues", [])),
                    "caterers": list(value.get("caterers", [])),
                }
            elif value not in (None, "", []):
                merged[key] = value

    for key, value in (updates or {}).items():
        if value in (None, "", []):
            continue
        if key == "dietary_needs":
            prior = list(merged.get("dietary_needs", []))
            merged[key] = sorted({*(prior or []), *value})
        else:
            merged[key] = value
    return merged


def _seed_planning_context_from_event(planning_context, event):
    if not event:
        return planning_context

    seeded = dict(planning_context or _default_planning_context())
    if not seeded.get("guest_count") and event.get("guest_count"):
        seeded["guest_count"] = int(event.get("guest_count") or 0)
    if not seeded.get("date"):
        seeded["date"] = event.get("date") or (event.get("start_datetime") or "")[:10] or None
    if not seeded.get("location_area") and event.get("location"):
        seeded["location_area"] = event.get("location")
    return seeded


def _is_venue_request(message):
    lowered = (message or "").lower()
    return "venue" in lowered or "venues" in lowered or "place to host" in lowered


def _is_catering_request(message):
    lowered = (message or "").lower()
    catering_terms = [
        "catering", "caterer", "food", "buffet", "plated", "food truck",
        "meal", "meals", "lunch", "dinner", "snack", "refreshment",
        "vegetarian", "vegan", "gluten-free", "gluten free", "dairy-free",
        "dairy free", "dietary", "dietary options", "food options"
    ]
    return any(word in lowered for word in catering_terms)


def _planning_signal_count(planning_context, keys):
    score = 0
    for key in keys:
        value = planning_context.get(key)
        if value not in (None, "", [], {}):
            score += 1
    return score


def _generic_venue_reply(planning_context):
    guest_count = planning_context.get("guest_count")
    if guest_count:
        return (
            f"For about {guest_count} guests, the best venue depends on budget, atmosphere, and whether you want indoor or outdoor space. "
            "Smaller groups usually do well in simple rooms or restaurant-style spaces, while larger groups need to prioritize capacity and parking. "
            "Do you want something more affordable, more polished, or outdoors?"
        )
    return (
        "The best venue depends mostly on guest count, budget, and the kind of atmosphere you want. "
        "For smaller events, simple spaces are usually easier and cheaper. For medium events, halls or ballrooms tend to work well. "
        "About how many people are you expecting?"
    )


def _generic_catering_reply(planning_context):
    guest_count = planning_context.get("guest_count")
    if guest_count:
        return (
            f"For about {guest_count} guests, catering mostly comes down to budget, formality, and service style. "
            "Tray service is usually easiest for casual events, buffet works well for medium groups, and plated meals feel more formal. "
            "Do you want something casual and affordable, or more polished?"
        )
    return (
        "Catering depends mostly on guest count, budget, and how formal you want the food to feel. "
        "For smaller casual events, trays are usually easiest. For medium groups, buffet service is often the safest choice. "
        "About how many people are you expecting?"
    )


def _summarize_venue_option(item):
    parts = []
    venue_type = item.get("venue_type") or item.get("type")
    if venue_type:
        parts.append(venue_type)
    capacity = item.get("capacity")
    if capacity:
        parts.append(f"capacity {capacity}")
    cost = item.get("estimated_cost") or item.get("cost")
    if cost not in (None, ""):
        try:
            parts.append(f"about ${int(float(cost))}")
        except Exception:
            parts.append(f"about ${cost}")
    summary = f"• {item['name']}"
    if parts:
        summary += " — " + ", ".join(parts)
    reasons = item.get("reasons") or []
    if reasons:
        summary += f" ({reasons[0]})"
    return summary


def _summarize_catering_option(item):
    parts = []
    cuisine = item.get("cuisine")
    if cuisine:
        parts.append(cuisine)
    service = item.get("service_type")
    if service:
        parts.append(service)
    price = item.get("cost_per_person")
    if price not in (None, ""):
        try:
            parts.append(f"${float(price):.0f}/person")
        except Exception:
            parts.append(f"${price}/person")
    summary = f"• {item['name']}"
    if parts:
        summary += " — " + ", ".join(parts)
    reasons = item.get("reasons") or []
    if reasons:
        summary += f" ({reasons[0]})"
    return summary


def _format_venue_reply(results, planning_context):
    if not results:
        area = planning_context.get("location_area") or "your area"
        return f"I couldn't find a strong venue match in {area} with the current filters. Try loosening the budget, guest count, or venue style."

    signal_count = _planning_signal_count(planning_context, ["guest_count", "location_area", "indoor_outdoor", "budget_level", "date"])
    if signal_count < 2:
        return _generic_venue_reply(planning_context)

    guest_count = planning_context.get("guest_count")
    if guest_count:
        intro = f"For about {guest_count} guests, these look like the strongest venue fits:"
    else:
        intro = "Here are a few venue options that look like the best fit:"

    lines = [_summarize_venue_option(item) for item in results[:3]]
    return intro + "\n" + "\n".join(lines) + "\n\nDo you want me to narrow this down by affordability, vibe, or capacity?"


def _format_catering_reply(results, planning_context, budget_limited=False, event=None):
    guest_count = planning_context.get("guest_count")
    limit = float((event or {}).get("budget_limit") or planning_context.get("max_budget_total") or 0)

    if not results:
        if budget_limited and limit > 0:
            guest_text = f" for about {guest_count} guests" if guest_count else ""
            return (
                f"I could not find a catering option that fits the current ${limit:.2f} spending limit{guest_text}. "
                "To stay within budget, consider lighter refreshments, snacks, a free/low-cost venue, or increasing the budget."
            )
        area = planning_context.get("location_area") or "your area"
        return f"I couldn't find a strong catering match in {area} with the current filters. Try loosening cuisine, service type, or budget."

    signal_count = _planning_signal_count(planning_context, ["guest_count", "cuisine", "service_type", "budget_per_person", "budget_level", "location_area", "dietary_needs", "max_budget_total"])
    if signal_count < 2 and not budget_limited:
        return _generic_catering_reply(planning_context)

    if guest_count and budget_limited and limit > 0:
        intro = f"For about {guest_count} guests, these catering options fit your ${limit:.2f} event limit:"
    elif guest_count:
        intro = f"For about {guest_count} guests, these look like the best catering fits:"
    else:
        intro = "Here are a few catering options that look like the best fit:"

    dietary = planning_context.get("dietary_needs") or []
    if dietary:
        intro += " I filtered this for " + ", ".join(dietary) + " options."

    lines = [_summarize_catering_option(item) for item in results[:3]]
    closing = "Want me to add one of these to the event?" if budget_limited else "Do you want me to narrow this down by budget, formality, or cuisine?"
    return intro + "\n" + "\n".join(lines) + "\n\n" + closing


def _apply_time_logic(target_event, cleaned_updates):
    existing_start = target_event.get("start_datetime")

    if "_parsed_time_only" in cleaned_updates:
        parsed_time_only = cleaned_updates.pop("_parsed_time_only")

        effective_date = cleaned_updates.get("date") or target_event.get("date")
        if not effective_date and existing_start:
            effective_date = existing_start[:10]

        if effective_date:
            cleaned_updates["start_datetime"] = f"{effective_date}T{parsed_time_only}"

    elif "date" in cleaned_updates and "start_datetime" in cleaned_updates:
        pass
    elif "date" in cleaned_updates and existing_start:
        existing_time = existing_start[11:] if len(existing_start) >= 16 else None
        if existing_time:
            cleaned_updates["start_datetime"] = f"{cleaned_updates['date']}T{existing_time}"

    return cleaned_updates


def _normalize_reply_choice(message: str) -> str:
    lowered = (message or "").strip().lower()
    if lowered in YES_WORDS:
        return "yes"
    if lowered in NO_WORDS:
        return "no"
    return "other"


def _normalize_text(value):
    return (value or "").strip().lower()


BUDGET_LIMIT_PATTERNS = [
    r"\bmaximum\s+budget\s+(?:is|of|at)?\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bmax\s+budget\s+(?:is|of|at)?\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bmy\s+spending\s+limit\s+(?:is|of)?\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bi\s+can\s+only\s+spend\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bi\s+only\s+have\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bmy\s+max(?:imum)?\s+(?:budget|spend|spending|limit)\s+is\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bmy\s+(?:budget|spending\s+limit|limit)\s+is\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bkeep\s+(?:it|this|the\s+event|everything)?\s*(?:at\s+or\s+)?under\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bkeep\s+(?:it|this|the\s+event|everything)?\s*(?:at\s+or\s+)?below\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bdo\s+not\s+go\s+over\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bdon't\s+go\s+over\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bno\s+more\s+than\s*\$?(\d+(?:\.\d+)?)\b",
    r"\bnot\s+more\s+than\s*\$?(\d+(?:\.\d+)?)\b",
    r"\b(?:cap|limit)\s+(?:it|this|the\s+event|spending)?\s*(?:at|to)?\s*\$?(\d+(?:\.\d+)?)\b",
    r"\b(?:hard|strict)\s+(?:cap|limit|ceiling)\s+(?:of|is)?\s*\$?(\d+(?:\.\d+)?)\b",
    r"\b(?:spending|budget)\s+ceiling\s+(?:of|is)?\s*\$?(\d+(?:\.\d+)?)\b",
    r"\b(?:under|below|less\s+than)\s*\$?(\d+(?:\.\d+)?)\s+(?:total|overall|all\s+in|for\s+everything)\b",
    r"\b\$\s*(\d+(?:\.\d+)?)\s+(?:budget|max|maximum|limit|cap|ceiling|all\s+in)\b",
]

BUDGET_REQUEST_WORDS = [
    "budget", "spending", "afford", "affordable", "cost", "costs", "total", "over budget",
    "under budget", "remaining", "how much left", "can i afford", "budget health", "spending limit",
]


MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

KNOWN_CATERING_ALIASES = {
    "doumar": "Doumar's Drive-In Catering",
    "doumars": "Doumar's Drive-In Catering",
    "doumar's": "Doumar's Drive-In Catering",
    "chickfila": "Chick-Fil-A",
    "chickfil": "Chick-Fil-A",
    "cfa": "Chick-Fil-A",
    "chef": "Chef by Design Catering Co.",
    "chefbydesign": "Chef by Design Catering Co.",
    "cuisine": "Cuisine & Company Catering",
    "cuisinecompany": "Cuisine & Company Catering",
}

KNOWN_VENUE_ALIASES = {
    "localpark": "Local Park",
    "park": "Local Park",
    "studentcenter": "Student Center",
    "innovation": "Innovation Hall",
    "innovationhall": "Innovation Hall",
    "webb": "Webb Center Ballroom",
    "webbcenter": "Webb Center Ballroom",
    "ballroom": "Webb Center Ballroom",
}


def _compact(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _extract_direct_dietary_need(message):
    lowered = _normalize_text(message)
    needs = []
    checks = [
        ("vegetarian", ["vegetarian"]),
        ("vegan", ["vegan"]),
        ("gluten free", ["gluten free", "gluten-free"]),
        ("gluten-free", ["gluten free", "gluten-free"]),
        ("dairy free", ["dairy free", "dairy-free"]),
        ("dairy-free", ["dairy free", "dairy-free"]),
    ]
    for label, variants in checks:
        if any(v in lowered for v in variants):
            needs.append(label)
    return needs


def _extract_simple_datetime(message):
    text = message or ""
    date = None
    month_match = re.search(r"\b(" + "|".join(MONTHS.keys()) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", text, re.IGNORECASE)
    if month_match:
        month = MONTHS[month_match.group(1).lower()]
        day = int(month_match.group(2))
        # Match the rest of your AI behavior/tests: assume 2026 for current capstone demos.
        date = f"2026-{month:02d}-{day:02d}"

    time_value = None
    time_match = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        ampm = (time_match.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        time_value = f"{hour:02d}:{minute:02d}:00"

    return date, time_value


def _extract_simple_create_event(message):
    """Broad, forgiving parser for demo/test prompts like:
    'Set up Career Workshop for 25 people on May 1st at 5:30pm in Student Center'.
    """
    text = (message or "").strip()
    lowered = text.lower()
    if not (lowered.startswith("create an event") or lowered.startswith("create event") or lowered.startswith("set up ") or lowered.startswith("setup ")):
        return None

    title = None
    m = re.search(r"(?:called|named)\s+(.+?)(?:\s+(?:for|on|at|in|with)\b|$)", text, re.IGNORECASE)
    if m:
        title = m.group(1).strip(" .,!?:;")
    else:
        m = re.search(r"(?:set\s*up|setup|create\s+(?:an\s+)?event)\s+(.+?)(?:\s+for\s+\d+\s*(?:people|guests|attendees)|\s+on\s+\w+\s+\d|\s+at\s+\d|\s+in\s+.+|$)", text, re.IGNORECASE)
        if m:
            title = m.group(1).strip(" .,!?:;")

    if not title or title.lower() in {"an event", "event"}:
        return None

    guest_count = None
    gm = re.search(r"\bfor\s+(?:about\s+|around\s+)?(\d{1,5})\s*(?:people|guests|attendees)\b", text, re.IGNORECASE)
    if gm:
        guest_count = int(gm.group(1))

    date, time_value = _extract_simple_datetime(text)
    start_datetime = f"{date}T{time_value}" if date and time_value else None

    location = None
    lm = re.search(r"\bin\s+(.+?)(?:\s+with\b|\s+for\b|$)", text, re.IGNORECASE)
    if lm:
        location = lm.group(1).strip(" .,!?:;")
    # If 'at Student Center' appears and it is not the time phrase, use it as location.
    am = re.search(r"\bat\s+(.+?)(?:\s+on\b|\s+with\b|$)", text, re.IGNORECASE)
    if am and not re.match(r"\d{1,2}(:\d{2})?\s*(am|pm)?$", am.group(1).strip(), re.IGNORECASE):
        possible = am.group(1).strip(" .,!?:;")
        if not any(month in possible.lower() for month in MONTHS):
            location = possible

    catering = None
    service_item = _find_service_match(text, "catering")
    if service_item and any(w in lowered for w in ["catering", "caterer", "food", "chick", "doumar", "chef", "cuisine", "cfa"]):
        catering = service_item.get("name")

    budget_limit = _extract_budget_limit_amount(text)

    data = {
        "title": title,
        "date": date,
        "start_datetime": start_datetime,
        "location": location,
        "guest_count": guest_count or 0,
        "description": None,
        "budget_limit": budget_limit or 0,
    }
    if catering:
        per_person = float(service_item.get("cost_per_person") or _infer_custom_catering_cost_per_person(catering))
        data.update({
            "selected_catering": catering,
            "food_cost_per_person": per_person,
            "estimated_catering_cost": per_person * max(int(data["guest_count"] or 0), 1),
        })
    return data


def _looks_like_named_catering(message):
    compacted = _compact(message)
    return any(alias in compacted for alias in KNOWN_CATERING_ALIASES.keys())


def _looks_like_named_venue(message):
    compacted = _compact(message)
    return any(alias in compacted for alias in KNOWN_VENUE_ALIASES.keys())


def _is_task_status_request(message):
    lowered = _normalize_text(message)
    return any(phrase in lowered for phrase in [
        "what tasks are left", "tasks left", "remaining tasks", "show tasks", "list tasks", "what tasks", "task status"
    ])


def _format_task_status_for_event(user_id, event):
    db = get_db()
    rows = db.execute(
        """
        SELECT title, completed, due_date, start_datetime
        FROM tasks
        WHERE event_id = ?
        ORDER BY completed ASC, COALESCE(start_datetime, due_date) ASC, id ASC
        """,
        (event["id"],)
    ).fetchall()
    tasks = [dict(row) for row in rows]
    if not tasks:
        return f"There are no tasks listed for '{event['title']}' yet. You can ask me to add starter tasks."
    open_tasks = [t for t in tasks if int(t.get("completed") or 0) == 0]
    done_tasks = [t for t in tasks if int(t.get("completed") or 0) == 1]
    lines = [f"Tasks for '{event['title']}':"]
    if open_tasks:
        lines.append("Remaining: " + ", ".join(t["title"] for t in open_tasks))
    if done_tasks:
        lines.append("Completed: " + ", ".join(t["title"] for t in done_tasks))
    return "\n".join(lines)


def _is_guest_count_question(message):
    lowered = _normalize_text(message)
    return "guest count" in lowered or "how many guests" in lowered or "how many people" in lowered


def _service_affordability_question(message):
    lowered = _normalize_text(message)
    if "afford" not in lowered and "fit" not in lowered:
        return None
    if _looks_like_named_catering(message):
        return "catering"
    if _looks_like_named_venue(message) or "paid venue" in lowered or "venue" in lowered:
        return "venue"
    return None


def _extract_budget_limit_amount(message):
    for pattern in BUDGET_LIMIT_PATTERNS:
        match = re.search(pattern, message or "", re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


def _is_budget_request(message):
    lowered = _normalize_text(message)
    return any(word in lowered for word in BUDGET_REQUEST_WORDS)


def _extract_guest_count_followup(message):
    """Handle short follow-ups like '30 people' or 'make it 30 guests'."""
    text = (message or "").strip().lower()
    patterns = [
        r"^(?:make\s+it\s+|update\s+(?:the\s+)?guest\s+count\s+(?:to\s+)?|set\s+(?:the\s+)?guest\s+count\s+(?:to\s+)?)?(\d{1,5})\s*(?:people|guests|attendees|person)?\.?$",
        r"^(?:we\s+expect|expecting|about|around)\s+(\d{1,5})\s*(?:people|guests|attendees)\.?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value = int(match.group(1))
                return value if value > 0 else None
            except (TypeError, ValueError):
                return None
    return None


def _budget_fit_updates(event, limit=None):
    """Return conservative updates that try to make the current plan fit the max spending limit.

    This keeps selected catering/venue when possible, but trims generated/default optional
    categories first so setting a budget does not just report that the user is over limit.
    """
    if not event:
        return {}
    budget_limit = float(limit if limit is not None else (event.get("budget_limit") or 0))
    if budget_limit <= 0:
        return {}

    working = dict(event)
    # Very low-risk defaults. These are campus-event friendly and avoid adding needless
    # recommendations/costs just because the generator has generic defaults.
    guest_count = max(int(float(working.get("guest_count") or 0)), 1)
    if float(working.get("venue_cost") or 0) > budget_limit * 0.5 and not working.get("selected_venue"):
        working["venue_cost"] = 0
        working["estimated_venue_cost"] = 0

    # First pass: make optional categories lean.
    lean = {
        "decorations_cost": 25.0 if guest_count <= 50 else 50.0,
        "equipment_cost": 35.0 if guest_count <= 50 else 75.0,
        "staff_cost": 0.0 if guest_count <= 50 else 50.0,
        "marketing_cost": 10.0 if guest_count <= 50 else 25.0,
        "misc_cost": 20.0 if guest_count <= 50 else 40.0,
        "contingency_percent": 5.0,
    }
    working.update(lean)
    if calculate_budget_totals(working)["total"] <= budget_limit:
        return lean

    # Second pass: bare minimum optional costs.
    bare = {
        "decorations_cost": 0.0,
        "equipment_cost": 0.0,
        "staff_cost": 0.0,
        "marketing_cost": 0.0,
        "misc_cost": 0.0,
        "contingency_percent": 0.0,
    }
    working.update(bare)
    if calculate_budget_totals(working)["total"] <= budget_limit:
        return bare

    # Third pass: if catering was generated/defaulted rather than explicitly selected,
    # reduce per-person food to fit the remaining budget. Do not silently downgrade a
    # named caterer the user selected.
    if not working.get("selected_catering"):
        venue = float(working.get("venue_cost") or working.get("estimated_venue_cost") or 0)
        max_food_pp = max((budget_limit - venue) / guest_count, 0)
        bare["food_cost_per_person"] = round(max_food_pp, 2)
        bare["estimated_catering_cost"] = round(max_food_pp * guest_count, 2)
        return bare

    return bare


def _get_full_event_for_user(user_id, event_id):
    db = get_db()
    row = db.execute("SELECT * FROM events WHERE id = ? AND user_id = ?", (event_id, user_id)).fetchone()
    return dict(row) if row else None


def _recalculate_and_save_event_budget(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        return None
    event = dict(event)
    totals = calculate_budget_totals(event)
    db.execute(
        """
        UPDATE events
        SET budget_subtotal = ?, budget_contingency = ?, budget_total = ?
        WHERE id = ?
        """,
        (totals["subtotal"], totals["contingency"], totals["total"], event_id),
    )
    db.commit()
    event.update({"budget_subtotal": totals["subtotal"], "budget_contingency": totals["contingency"], "budget_total": totals["total"]})
    return event


def _format_budget_summary(event):
    analysis = analyze_budget(event)
    summary = analysis.get("summary", {})
    health = analysis.get("health", {})
    limit = float(summary.get("budget_limit") or 0)
    total = float(summary.get("total") or 0)
    remaining = summary.get("remaining_budget")
    if limit > 0:
        if float(summary.get("over_budget_by") or 0) > 0:
            status = f"This plan is over your ${limit:.2f} spending limit by ${float(summary.get('over_budget_by') or 0):.2f}."
        else:
            status = f"This plan fits your ${limit:.2f} spending limit with about ${float(remaining or 0):.2f} left."
    else:
        status = "No maximum spending limit is set yet, so I can analyze costs but cannot tell whether the plan fits what you can spend."
    suggestion = (analysis.get("suggestions") or [""])[0]
    return f"Budget status: {health.get('label', 'Not analyzed')}. Estimated total: ${total:.2f}. {status} {suggestion}".strip()


def _set_budget_limit_for_event(user_id, event_id, amount):
    db = get_db()
    db.execute("UPDATE events SET budget_limit = ? WHERE id = ? AND user_id = ?", (float(amount), event_id, user_id))
    db.commit()
    event = _get_full_event_for_user(user_id, event_id)
    fit_updates = _budget_fit_updates(event, amount)
    if fit_updates:
        update_event_in_db(event_id, fit_updates)
    event = _recalculate_and_save_event_budget(event_id)
    return _get_full_event_for_user(user_id, event_id) or event


def _infer_custom_catering_cost_per_person(name):
    lowered = _normalize_text(name)
    if any(word in lowered for word in ["chick", "pizza", "sub", "sandwich", "fast food", "taco", "burger"]):
        return 12.0
    if any(word in lowered for word in ["snack", "dessert", "refreshment"]):
        return 6.0
    if any(word in lowered for word in ["gourmet", "plated", "upscale", "formal"]):
        return 24.0
    return 15.0


def _clean_service_candidate(name):
    name = (name or "").strip(" .!?;:")
    name = re.sub(r"\b(?:to|for|on|in)\s+(?:that|the|this)?\s*(?:event|one|it)\b.*$", "", name, flags=re.IGNORECASE).strip(" .!?;:")
    name = re.sub(r"\b(?:that|the|this)\s*(?:event|one|it)\b", "", name, flags=re.IGNORECASE).strip(" .!?;:")
    # Common spoken/typed variants that otherwise look like broken custom names.
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    for alias, canonical in KNOWN_CATERING_ALIASES.items():
        if alias in normalized or normalized in alias:
            return canonical
    for alias, canonical in KNOWN_VENUE_ALIASES.items():
        if alias in normalized or normalized in alias:
            return canonical
    if normalized in {"that", "this", "the", "event", "thatevent", "theevent"}:
        return ""
    return name


def _extract_custom_service_name(message, service_type):
    cleaned = (message or "").strip()
    # Make typo-style phrases like "chick-fil-catering" parse as a provider,
    # not as "that event" after the word catering.
    cleaned = re.sub(r"(?i)(chick\s*[- ]?fil\s*[- ]?a?)\s*[- ]?(catering|caterer|food)", r"\1 \2", cleaned)
    if service_type == "catering":
        patterns = [
            r"(?:add|use|choose|select|set|make|switch\s+to|change\s+to)\s+(.+?)\s+(?:as\s+)?(?:the\s+)?(?:catering|caterer|food)(?:\s+(?:to|for)\s+.+)?$",
            r"(?:add|use|choose|select|set|make|switch\s+to|change\s+to)\s+(?:the\s+)?(?:catering|caterer|food)\s+(?:to|as|from)?\s*(.+?)(?:\s+(?:to|for)\s+.+)?$",
            r"(?:catering|caterer|food)\s+(?:to|as|from|is)?\s*(.+?)(?:\s+(?:to|for)\s+.+)?$",
        ]
    else:
        patterns = [
            r"(?:set|make|change|switch)\s+(?:the\s+)?(?:venue|location|place)\s+(?:to|as|at)?\s*(.+?)(?:\s+(?:to|for)\s+.+)?$",
            r"(?:use|choose|select|add)\s+(.+?)\s+as\s+(?:the\s+)?(?:venue|location|place)(?:\s+(?:to|for)\s+.+)?$",
            r"(?:venue|location|place)\s+(?:to|as|at|is)?\s*(.+?)(?:\s+(?:to|for)\s+.+)?$",
        ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            name = _clean_service_candidate(match.group(1))
            if name and name.lower() not in {"that", "it", "this", "the", "event", "that event", "the event"}:
                return name
    return None


def _find_service_match(message, service_type):
    normalized_message = _compact(message)

    if service_type == "catering":
        for alias, canonical in KNOWN_CATERING_ALIASES.items():
            if alias in normalized_message:
                # Prefer DB row when it exists, otherwise use a safe local fallback.
                try:
                    rows = get_db().execute("SELECT * FROM caterers ORDER BY LENGTH(name) DESC").fetchall()
                    for row in rows:
                        item = dict(row)
                        if _compact(item.get("name")) == _compact(canonical) or alias in _compact(item.get("name")):
                            item["name"] = canonical if canonical == "Chick-Fil-A" else item.get("name", canonical)
                            return item
                except Exception:
                    pass
                return {"name": canonical, "cost_per_person": _infer_custom_catering_cost_per_person(canonical)}
    else:
        for alias, canonical in KNOWN_VENUE_ALIASES.items():
            if alias in normalized_message:
                try:
                    rows = get_db().execute("SELECT * FROM venues ORDER BY LENGTH(name) DESC").fetchall()
                    for row in rows:
                        item = dict(row)
                        if _compact(item.get("name")) == _compact(canonical) or alias in _compact(item.get("name")):
                            item["name"] = item.get("name", canonical)
                            return item
                except Exception:
                    pass
                return {"name": canonical, "estimated_cost": 0}

    db = get_db()
    if service_type == "venue":
        rows = db.execute("SELECT * FROM venues ORDER BY LENGTH(name) DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM caterers ORDER BY LENGTH(name) DESC").fetchall()

    for row in rows:
        item = dict(row)
        item_norm = _compact(item.get("name"))
        if item_norm and (item_norm in normalized_message or normalized_message in item_norm):
            return item

    custom_name = _extract_custom_service_name(message, service_type)
    if custom_name:
        if service_type == "catering":
            return {"name": custom_name, "cost_per_person": _infer_custom_catering_cost_per_person(custom_name)}
        return {"name": custom_name, "estimated_cost": 0}
    return None

def _looks_like_service_assignment(message):
    lowered = _normalize_text(message)
    has_action = any(word in lowered for word in ["add", "set", "use", "choose", "select", "make", "change", "switch"])
    if not has_action:
        return None
    if any(word in lowered for word in ["catering", "caterer", "food"]):
        return "catering"
    if any(word in lowered for word in ["venue", "location", "place"]):
        return "venue"
    if _looks_like_named_catering(message):
        return "catering"
    if _looks_like_named_venue(message):
        return "venue"
    return None

def _projected_total_with_catering(event, item):
    guest_count = max(int(event.get("guest_count") or 0), 1)
    per_person = float(item.get("cost_per_person") or 0)
    projected = dict(event)
    projected.update({
        "selected_catering": item.get("name"),
        "estimated_catering_cost": per_person * guest_count,
        "food_cost_per_person": per_person,
    })
    return float(calculate_budget_totals(projected).get("total") or 0)


def _filter_catering_results_for_budget(results, event):
    """Only recommend caterers that fit the event's total spending limit.

    This intentionally mirrors the add-catering budget check so advice does not
    suggest options that the AI would refuse to add later.
    """
    if not event:
        return list(results or []), False

    limit = float(event.get("budget_limit") or 0)
    if limit <= 0:
        return list(results or []), False

    filtered = []
    for item in results or []:
        try:
            projected_total = _projected_total_with_catering(event, item)
        except Exception:
            continue
        if projected_total <= limit:
            enriched = dict(item)
            enriched["projected_total"] = round(projected_total, 2)
            filtered.append(enriched)

    filtered.sort(key=lambda item: (float(item.get("cost_per_person") or 0), -float(item.get("rating") or 0)))
    return filtered, True


def _is_starter_task_request(message):
    lowered = _normalize_text(message)
    return (
        "starter task" in lowered
        or "starter tasks" in lowered
        or "add starting tasks" in lowered
        or "add basic tasks" in lowered
        or "add default tasks" in lowered
    )


def _apply_service_assignment(user_id, event, service_type, item):
    event = _get_full_event_for_user(user_id, event["id"])
    if not event:
        return None, "I couldn’t find that event anymore."
    guest_count = int(event.get("guest_count") or 0)
    if service_type == "venue":
        cost = float(item.get("estimated_cost") or item.get("cost") or 0)
        updates = {"selected_venue": item.get("name"), "location": item.get("name"), "estimated_venue_cost": cost, "venue_cost": cost}
    else:
        per_person = float(item.get("cost_per_person") or 0)
        cost = per_person * max(guest_count, 1)
        updates = {"selected_catering": item.get("name"), "estimated_catering_cost": cost, "food_cost_per_person": per_person}
    projected = dict(event)
    projected.update(updates)
    totals = calculate_budget_totals(projected)
    limit = float(projected.get("budget_limit") or 0)
    if limit > 0 and totals["total"] > limit:
        over = totals["total"] - limit
        return None, (
            f"I did not add {item.get('name')} because it would bring the estimated total to ${totals['total']:.2f}, "
            f"which is ${over:.2f} over your ${limit:.2f} spending limit. Try a cheaper option, reduce guest count, or use a free/low-cost venue."
        )
    update_event_in_db(event["id"], updates)
    refreshed = _recalculate_and_save_event_budget(event["id"])
    remaining = float(calculate_budget_totals(refreshed).get("remaining_budget") or 0) if refreshed else 0
    label = "venue" if service_type == "venue" else "catering"
    if limit > 0:
        return refreshed, f"Added {item.get('name')} as the {label}. Estimated total is now ${calculate_budget_totals(refreshed)['total']:.2f}, leaving about ${remaining:.2f}."
    return refreshed, f"Added {item.get('name')} as the {label}. Estimated total is now ${calculate_budget_totals(refreshed)['total']:.2f}."


def _get_event_for_user(user_id, event_id):
    db = get_db()
    row = db.execute(
        """
        SELECT id, title, date, start_datetime, end_datetime, location, description,
               guest_count, budget_total, budget_limit, selected_venue, selected_catering,
               estimated_venue_cost, estimated_catering_cost
        FROM events
        WHERE id = ? AND user_id = ?
        """,
        (event_id, user_id)
    ).fetchone()
    return dict(row) if row else None


def _task_exists_for_event(event_id, title: str):
    db = get_db()
    row = db.execute(
        """
        SELECT id
        FROM tasks
        WHERE event_id = ? AND LOWER(title) = LOWER(?)
        LIMIT 1
        """,
        (event_id, title)
    ).fetchone()
    return row is not None


def _resolve_event_for_new_task(user_message, context, chat_state):
    target_event = resolve_target_event(user_message, context, chat_state)
    if target_event:
        return target_event

    events = context.get("events", [])
    if len(events) == 1:
        return events[0]

    return None


def _find_task_by_reference(task_title, tasks, event_id=None):
    if not task_title:
        return None

    candidate_tasks = tasks
    if event_id is not None:
        candidate_tasks = [task for task in tasks if int(task.get("event_id", 0)) == int(event_id)]

    normalized_query = _normalize_text(task_title)

    for task in candidate_tasks:
        task_name = _normalize_text(task.get("title"))
        if task_name == normalized_query:
            return task

    for task in candidate_tasks:
        task_name = _normalize_text(task.get("title"))
        if normalized_query in task_name or task_name in normalized_query:
            return task

    query_tokens = {token for token in normalized_query.split() if len(token) > 2}
    best_task = None
    best_score = 0

    for task in candidate_tasks:
        task_tokens = {token for token in _normalize_text(task.get("title")).split() if len(token) > 2}
        overlap = len(query_tokens & task_tokens)
        if overlap > best_score:
            best_score = overlap
            best_task = task

    return best_task if best_score >= 1 else None


def _build_starter_task_titles(event):
    title = _normalize_text(event.get("title"))
    description = _normalize_text(event.get("description"))
    location = _normalize_text(event.get("location"))
    guest_count = int(event.get("guest_count") or 0)

    combined = f"{title} {description} {location}"

    tasks = [
        "Confirm venue",
        "Send invitations",
    ]

    if "network" in combined or "mixer" in combined:
        tasks.extend([
            "Prepare guest check-in list",
            "Arrange name tags",
        ])

    if "fundrais" in combined or "donation" in combined or "charity" in combined:
        tasks.extend([
            "Set up donation process",
            "Prepare promotional materials",
            "Reach out to sponsors",
        ])

    if "workshop" in combined or "training" in combined or "seminar" in combined:
        tasks.extend([
            "Prepare presentation materials",
            "Confirm speaker or facilitator",
            "Test room equipment",
        ])

    if "party" in combined or "celebration" in combined:
        tasks.extend([
            "Plan decorations",
            "Prepare music or entertainment",
        ])

    if "cater" in combined or "food" in combined:
        tasks.append("Arrange catering")

    if guest_count >= 75:
        tasks.extend([
            "Assign event staff or volunteers",
            "Review crowd flow and seating",
        ])

    if guest_count >= 150:
        tasks.append("Review security needs")

    deduped = []
    seen = set()
    for task in tasks:
        key = task.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(task)

    return deduped


def _resolve_requested_starter_tasks(message, available_titles):
    lowered = _normalize_text(message)
    selected = []

    for keyword, mapped_titles in FOLLOWUP_TASK_KEYWORDS.items():
        if keyword in lowered:
            for title in mapped_titles:
                if title in available_titles and title not in selected:
                    selected.append(title)

    if "all" in lowered or "starter" in lowered or "them" in lowered:
        return available_titles

    return selected or None


def _add_starter_tasks(user_id, event_id, requested_titles=None):
    event = _get_event_for_user(user_id, event_id)
    if not event:
        return None, "I couldn’t find that event anymore."

    starter_titles = _build_starter_task_titles(event)
    if requested_titles:
        starter_titles = [title for title in starter_titles if title in requested_titles]

    created = []
    for title in starter_titles:
        if _task_exists_for_event(event_id, title):
            continue

        task, error = create_task_for_user(user_id, {
            "event_id": event_id,
            "title": title
        })
        if error:
            return None, error
        created.append(task)

    return {
        "event": event,
        "tasks": created,
        "available_titles": starter_titles,
    }, None


def _handle_pending_followup(user_id, user_message, chat_state):
    pending = chat_state.get("pending_followup")
    if not pending:
        return None

    choice = _normalize_reply_choice(user_message)
    followup_type = pending.get("type")

    if choice == "no":
        chat_state["pending_followup"] = None
        _save_chat_state(chat_state)
        return jsonify({
            "reply": "No problem.",
            "action": "followup_declined"
        }), 200

    if followup_type == "add_starter_tasks":
        event_id = pending.get("event_id")
        event = _get_event_for_user(user_id, event_id)
        if not event:
            chat_state["pending_followup"] = None
            _save_chat_state(chat_state)
            return jsonify({
                "reply": "I couldn’t find that event anymore.",
                "action": "starter_tasks_failed"
            }), 200

        available_titles = _build_starter_task_titles(event)
        requested_titles = None
        if choice != "yes":
            requested_titles = _resolve_requested_starter_tasks(user_message, available_titles)
            if requested_titles is None:
                return None

        result, error = _add_starter_tasks(user_id, event_id, requested_titles=requested_titles)
        chat_state["pending_followup"] = None

        if error:
            _save_chat_state(chat_state)
            return jsonify({
                "reply": error,
                "action": "starter_tasks_failed"
            }), 200

        created_tasks = result["tasks"]
        event = result["event"]

        if created_tasks:
            chat_state["last_event_id"] = event["id"]
            chat_state["last_task_id"] = created_tasks[-1]["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": (
                    f"Added {len(created_tasks)} starter task(s) to '{event['title']}': "
                    + ", ".join(task["title"] for task in created_tasks)
                    + ". You can ask me to add more tasks, mark one complete, or update the event details."
                ),
                "action": "starter_tasks_created",
                "event_id": event["id"],
                "tasks": created_tasks
            }), 200

        _save_chat_state(chat_state)
        return jsonify({
            "reply": f"Those starter tasks already exist for '{event['title']}'.",
            "action": "starter_tasks_already_exist",
            "event_id": event["id"]
        }), 200

    if choice != "yes":
        return None

    if followup_type == "add_another_task":
        event_id = pending.get("event_id")
        event = _get_event_for_user(user_id, event_id)

        chat_state["pending_followup"] = None
        _save_chat_state(chat_state)

        if not event:
            return jsonify({
                "reply": "I couldn’t find that event anymore.",
                "action": "followup_failed"
            }), 200

        return jsonify({
            "reply": f"Sure — what task would you like me to add to '{event['title']}'?",
            "action": "task_create_collecting",
            "event_id": event["id"]
        }), 200

    return None


def _build_update_suggestion(cleaned_updates):
    if "guest_count" in cleaned_updates:
        return " You may also want to review catering or budget for the new headcount."
    if "date" in cleaned_updates or "start_datetime" in cleaned_updates:
        return " You may want to check task deadlines and vendor availability for the new schedule."
    if "location" in cleaned_updates:
        return " You may want to confirm venue logistics, setup, or parking details."
    return ""


@ai_bp.route("/clear-chat", methods=["POST"])
def clear_chat():
    session.pop("chat_state", None)
    session.pop("last_event_id", None)
    session.pop("pending_event_draft", None)
    session.pop("planning_context", None)
    return jsonify({"message": "Chat cleared"}), 200


@ai_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        user_id = session["user_id"]
        context = load_user_context(user_id)
        chat_state = _get_chat_state()

        planning_updates = extract_planning_preferences(user_message)
        direct_dietary = _extract_direct_dietary_need(user_message)
        if direct_dietary:
            planning_updates = dict(planning_updates or {})
            planning_updates["dietary_needs"] = direct_dietary

        target_for_planning = resolve_target_event(user_message, context, chat_state)
        planning_context = _merge_planning_context(chat_state.get("planning_context"), planning_updates)
        planning_context = _seed_planning_context_from_event(planning_context, target_for_planning)
        chat_state["planning_context"] = planning_context

        # Direct create parser must run before generic catering/venue advice so
        # 'create event ... with Chick-Fil-A catering' creates the event first.
        simple_event = _extract_simple_create_event(user_message)
        if simple_event:
            created_event = create_event_for_user(user_id, simple_event)
            if simple_event.get("budget_limit"):
                created_event = _set_budget_limit_for_event(user_id, created_event["id"], simple_event["budget_limit"]) or created_event
            else:
                _recalculate_and_save_event_budget(created_event["id"])
            chat_state["last_event_id"] = created_event["id"]
            chat_state["pending_event_draft"] = {}
            chat_state["pending_followup"] = {"type": "add_starter_tasks", "event_id": created_event["id"]}
            chat_state["planning_context"] = _seed_planning_context_from_event(planning_context, created_event)
            _save_chat_state(chat_state)
            catering_note = f" I also noted {simple_event.get('selected_catering')} as the catering." if simple_event.get("selected_catering") else ""
            return jsonify({
                "reply": (
                    f"Event '{created_event['title']}' was created"
                    f" for {created_event.get('date') or created_event.get('start_datetime') or 'the selected date'}"
                    + (f" at {created_event.get('location')}" if created_event.get('location') else "")
                    + "." + catering_note + " Would you like me to add starter tasks like confirming the venue, arranging catering, or sending invites?"
                ),
                "action": "event_created",
                "event": created_event
            }), 200

        # Only let the pending follow-up consume true yes/no style replies.
        # Otherwise direct commands like 'update guest count' should not become starter tasks.
        if _normalize_reply_choice(user_message) in {"yes", "no"}:
            followup_response = _handle_pending_followup(user_id, user_message, chat_state)
            if followup_response:
                return followup_response

        if _is_guest_count_question(user_message) and target_for_planning:
            count = int(target_for_planning.get("guest_count") or 0)
            chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": f"'{target_for_planning['title']}' currently has {count} guests.",
                "action": "guest_count_summary",
                "event_id": target_for_planning["id"]
            }), 200

        if _is_task_status_request(user_message) and target_for_planning:
            chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": _format_task_status_for_event(user_id, target_for_planning),
                "action": "task_status",
                "event_id": target_for_planning["id"]
            }), 200

        afford_service_type = _service_affordability_question(user_message)
        if afford_service_type and target_for_planning:
            item = _find_service_match(user_message, afford_service_type)
            event = _get_full_event_for_user(user_id, target_for_planning["id"])
            if item and event:
                projected = dict(event)
                if afford_service_type == "catering":
                    guest_count = max(int(event.get("guest_count") or 0), 1)
                    per_person = float(item.get("cost_per_person") or _infer_custom_catering_cost_per_person(item.get("name")))
                    projected.update({"selected_catering": item.get("name"), "food_cost_per_person": per_person, "estimated_catering_cost": per_person * guest_count})
                else:
                    cost = float(item.get("estimated_cost") or item.get("cost") or 0)
                    projected.update({"selected_venue": item.get("name"), "venue_cost": cost, "estimated_venue_cost": cost})
                totals = calculate_budget_totals(projected)
                limit = float(event.get("budget_limit") or 0)
                if limit > 0 and totals["total"] > limit:
                    reply = f"{item.get('name')} would bring the estimated total to ${totals['total']:.2f}, which is ${totals['total'] - limit:.2f} over your ${limit:.2f} spending limit."
                elif limit > 0:
                    reply = f"Yes — {item.get('name')} fits your ${limit:.2f} spending limit. Projected total would be about ${totals['total']:.2f}."
                else:
                    reply = f"{item.get('name')} would bring the estimated total to about ${totals['total']:.2f}. Set a maximum budget if you want me to judge whether it fits."
                chat_state["last_event_id"] = target_for_planning["id"]
                _save_chat_state(chat_state)
                return jsonify({"reply": reply, "action": "affordability_check", "event_id": target_for_planning["id"]}), 200

        guest_count_followup = _extract_guest_count_followup(user_message)
        if guest_count_followup is not None and target_for_planning:
            update_event_in_db(target_for_planning["id"], {"guest_count": guest_count_followup})
            refreshed = _recalculate_and_save_event_budget(target_for_planning["id"])
            chat_state["last_event_id"] = target_for_planning["id"]
            planning_context["guest_count"] = guest_count_followup
            chat_state["planning_context"] = planning_context
            _save_chat_state(chat_state)
            return jsonify({
                "reply": f"Updated '{target_for_planning['title']}' to {guest_count_followup} guests. I also refreshed the budget totals for that event.",
                "action": "event_updated",
                "event": refreshed,
                "event_id": target_for_planning["id"]
            }), 200

        budget_limit_amount = _extract_budget_limit_amount(user_message)
        if budget_limit_amount is not None and target_for_planning:
            event = _set_budget_limit_for_event(user_id, target_for_planning["id"], budget_limit_amount)
            chat_state["last_event_id"] = target_for_planning["id"]
            planning_context["max_budget_total"] = budget_limit_amount
            chat_state["planning_context"] = planning_context
            _save_chat_state(chat_state)
            return jsonify({
                "reply": f"Got it. I’ll keep '{target_for_planning['title']}' at or under ${budget_limit_amount:.2f} where possible. I trimmed generated/default budget categories to fit that limit before saving. " + _format_budget_summary(event),
                "action": "budget_limit_set",
                "event": event
            }), 200

        if _is_starter_task_request(user_message) and target_for_planning:
            result, error = _add_starter_tasks(user_id, target_for_planning["id"])
            chat_state["last_event_id"] = target_for_planning["id"]
            chat_state["pending_followup"] = None
            _save_chat_state(chat_state)
            if error:
                return jsonify({"reply": error, "action": "starter_tasks_failed"}), 200
            created_tasks = result.get("tasks") or []
            if created_tasks:
                return jsonify({
                    "reply": (
                        f"Added {len(created_tasks)} starter task(s) to '{target_for_planning['title']}': "
                        + ", ".join(task["title"] for task in created_tasks)
                        + "."
                    ),
                    "action": "starter_tasks_created",
                    "event_id": target_for_planning["id"],
                    "tasks": created_tasks
                }), 200
            return jsonify({
                "reply": f"Those starter tasks already exist for '{target_for_planning['title']}'.",
                "action": "starter_tasks_already_exist",
                "event_id": target_for_planning["id"]
            }), 200

        service_type = _looks_like_service_assignment(user_message)
        if service_type and target_for_planning:
            item = _find_service_match(user_message, service_type)
            if item:
                updated_event, reply = _apply_service_assignment(user_id, target_for_planning, service_type, item)
                chat_state["last_event_id"] = target_for_planning["id"]
                _save_chat_state(chat_state)
                return jsonify({
                    "reply": reply,
                    "action": f"{service_type}_assigned" if updated_event else f"{service_type}_blocked_by_budget",
                    "event": updated_event,
                    "event_id": target_for_planning["id"]
                }), 200
            chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": f"I can add that as the {service_type}, but I couldn’t identify the provider. Try a name like Chick-Fil-A, Doumar's, Cuisine & Company, or a specific venue name.",
                "action": f"{service_type}_assignment_needs_name",
                "event_id": target_for_planning["id"]
            }), 200

        if _is_budget_request(user_message) and target_for_planning:
            event = _get_full_event_for_user(user_id, target_for_planning["id"])
            chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": _format_budget_summary(event),
                "action": "budget_summary",
                "event": event
            }), 200

        if _is_venue_request(user_message):
            venue_results = search_venues(planning_context, limit=3)
            planning_context["last_recommendations"]["venues"] = [item.get("id") for item in venue_results]
            chat_state["planning_context"] = planning_context
            if target_for_planning:
                chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": _format_venue_reply(venue_results, planning_context),
                "action": "venue_recommendations",
                "planning_context": planning_context,
                "results": venue_results
            }), 200

        if _is_catering_request(user_message):
            event_for_budget = _get_full_event_for_user(user_id, target_for_planning["id"]) if target_for_planning else None
            recommendation_context = dict(planning_context)

            # If the event has a max spending limit, use it as a hard filter for advice.
            # Pull extra rows first, then project each option against the full event total.
            raw_limit = 10 if event_for_budget and float(event_for_budget.get("budget_limit") or 0) > 0 else 3
            catering_results = search_caterers(recommendation_context, limit=raw_limit)
            catering_results, budget_limited = _filter_catering_results_for_budget(catering_results, event_for_budget)
            catering_results = catering_results[:3]

            planning_context["last_recommendations"]["caterers"] = [item.get("id") for item in catering_results if item.get("id") is not None]
            chat_state["planning_context"] = planning_context
            if target_for_planning:
                chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": _format_catering_reply(catering_results, planning_context, budget_limited=budget_limited, event=event_for_budget),
                "action": "catering_recommendations",
                "planning_context": planning_context,
                "results": catering_results
            }), 200

        interpreted = interpret_message(user_message, context=context, state=chat_state)
        action_type = interpreted["type"]

        use_ollama = current_app.config.get("USE_OLLAMA_FALLBACK", False)
        if use_ollama and action_type in {
            "fallback",
            "event_update_no_changes",
            "event_update_needs_target",
            "task_complete_not_found",
        }:
            llm_result = safe_ollama_interpret(
                message=user_message,
                context={
                    "events": context.get("events", []),
                    "tasks": context.get("tasks", []),
                    "last_event_id": chat_state.get("last_event_id"),
                },
                model=current_app.config.get("OLLAMA_MODEL", "qwen2.5:1.5b"),
                url=current_app.config.get("OLLAMA_URL", "http://localhost:11434/api/chat"),
            )

            converted = build_interpret_result_from_llm(llm_result, context, chat_state)
            if converted:
                interpreted = converted
                action_type = interpreted["type"]

        if action_type == "task_create":
            task_fields = interpreted.get("task") or interpreted.get("task_data") or {}
            task_title = (task_fields.get("title") or "").strip()
            if not task_title:
                _save_chat_state(interpreted["state"])
                return jsonify({
                    "reply": "I can add that as a task. Tell me what you want the task to be, like 'remind me to call the caterer' or 'add task to confirm the venue.'",
                    "action": "task_create_missing_title"
                }), 200

            target_event = _resolve_event_for_new_task(user_message, context, chat_state)
            if not target_event:
                _save_chat_state(interpreted["state"])
                return jsonify({
                    "reply": "I can add a task, but I couldn’t tell which event it belongs to. Please mention the event title.",
                    "action": "task_create_needs_event"
                }), 200

            created_task, error = create_task_for_user(user_id, {
                "event_id": target_event["id"],
                "title": task_title,
            })
            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_create_failed"
                }), 200

            new_state = interpreted["state"]
            new_state["last_task_id"] = created_task["id"]
            new_state["last_event_id"] = created_task["event_id"]
            new_state["pending_followup"] = {
                "type": "add_another_task",
                "event_id": created_task["event_id"]
            }
            _save_chat_state(new_state)

            return jsonify({
                "reply": (
                    f"Task '{created_task['title']}' was added to '{created_task['event_title']}'. "
                    "Would you like me to add another task for this event?"
                ),
                "action": "task_created",
                "task": created_task
            }), 200

        if action_type == "task_complete_not_found":
            _save_chat_state(interpreted["state"])
            return jsonify({
                "reply": interpreted["reply"],
                "action": "task_complete_failed"
            }), 200

        if action_type == "task_complete":
            task_fields = interpreted.get("task") or interpreted.get("task_data") or {}
            target_task = interpreted.get("target_task")

            if not target_task and task_fields.get("title"):
                event_hint = resolve_target_event(user_message, context, chat_state)
                target_task = _find_task_by_reference(
                    task_fields.get("title"),
                    context.get("tasks", []),
                    event_hint.get("id") if event_hint else None,
                )

            if not target_task:
                _save_chat_state(interpreted["state"])
                return jsonify({
                    "reply": "I found your task request, but I couldn’t tell which task you meant. Try saying something like 'mark vendor confirmation done' or 'complete catering follow-up.'",
                    "action": "task_complete_failed"
                }), 200

            completed_task, error = complete_task_for_user(user_id, target_task["id"])
            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_complete_failed"
                }), 200

            new_state = interpreted["state"]
            new_state["last_task_id"] = completed_task["id"]
            new_state["last_event_id"] = completed_task["event_id"]
            new_state["pending_followup"] = None
            _save_chat_state(new_state)

            return jsonify({
                "reply": (
                    f"Task '{completed_task['title']}' for '{completed_task['event_title']}' was marked complete. "
                    f"Would you like me to help with the next task?"
                ),
                "action": "task_completed",
                "task": completed_task
            }), 200

        if action_type == "event_create_collecting":
            _save_chat_state(interpreted["state"])
            return jsonify({
                "reply": interpreted["reply"],
                "action": "event_create_collecting",
                "draft": interpreted["draft"],
                "missing_fields": interpreted["missing_fields"]
            }), 200

        if action_type == "event_create":
            draft = dict(interpreted["draft"])
            budget_limit_amount = _extract_budget_limit_amount(user_message)
            if budget_limit_amount is not None:
                draft["budget_limit"] = budget_limit_amount
            created_event = create_event_for_user(user_id, draft)
            if budget_limit_amount is not None:
                created_event = _set_budget_limit_for_event(user_id, created_event["id"], budget_limit_amount) or created_event

            new_state = interpreted["state"]
            new_state["pending_event_draft"] = {}
            new_state["last_event_id"] = created_event["id"]
            new_state["active_flow"] = None
            new_state["awaiting_field"] = None
            new_state["pending_followup"] = {
                "type": "add_starter_tasks",
                "event_id": created_event["id"]
            }
            new_state["planning_context"] = _seed_planning_context_from_event(new_state.get("planning_context"), created_event)
            _save_chat_state(new_state)

            return jsonify({
                "reply": (
                    f"Event '{created_event['title']}' was created"
                    f" for {created_event['date'] or created_event['start_datetime']}"
                    f" at {created_event['location']}. "
                    + (f"I’ll keep it at or under ${created_event.get('budget_limit', 0):.2f}. " if created_event.get('budget_limit') else "")
                    + "Would you like me to add starter tasks like confirming the venue, arranging catering, or sending invites?"
                ),
                "action": "event_created",
                "event": created_event
            }), 200

        if action_type == "event_update_needs_target":
            _save_chat_state(interpreted["state"])
            return jsonify({
                "reply": interpreted["reply"],
                "action": "event_update_needs_title"
            }), 200

        if action_type == "event_update_no_changes":
            _save_chat_state(interpreted["state"])
            return jsonify({
                "reply": interpreted["reply"],
                "action": "event_update_failed"
            }), 200

        if action_type == "event_update":
            target_event = interpreted["target_event"]
            cleaned_updates = dict(interpreted["changes"])
            cleaned_updates = _apply_time_logic(target_event, cleaned_updates)

            updated = update_event_in_db(target_event["id"], cleaned_updates)
            if updated:
                new_state = interpreted["state"]
                new_state["last_event_id"] = target_event["id"]
                new_state["pending_followup"] = None
                refreshed_event = dict(target_event)
                refreshed_event.update(cleaned_updates)
                new_state["planning_context"] = _seed_planning_context_from_event(new_state.get("planning_context"), refreshed_event)
                _save_chat_state(new_state)

                new_title = cleaned_updates.get("title", target_event["title"])
                new_date = cleaned_updates.get("date", target_event.get("date"))
                new_location = cleaned_updates.get("location", target_event.get("location"))
                guest_count = cleaned_updates.get("guest_count", target_event.get("guest_count"))

                summary_bits = []
                if new_date:
                    summary_bits.append(f"for {new_date}")
                if new_location:
                    summary_bits.append(f"at {new_location}")
                if guest_count not in (None, ""):
                    summary_bits.append(f"with {guest_count} guests")

                return jsonify({
                    "reply": f"Updated '{new_title}' " + " ".join(summary_bits) + "." + _build_update_suggestion(cleaned_updates),
                    "action": "event_updated",
                    "event_id": target_event["id"],
                    "updated_fields": cleaned_updates
                }), 200

            return jsonify({
                "reply": "I found the event, but I couldn’t tell what fields to update.",
                "action": "event_update_failed"
            }), 200

        reply = chatbot.get_response(
            user_message,
            context={
                **context,
                "chat_state": chat_state,
                "planning_context": chat_state.get("planning_context", {}),
            }
        )
        if reply is None or str(reply).strip().lower() in {"", "none", "null"}:
            if target_for_planning:
                reply = f"I’m not fully sure how to apply that to '{target_for_planning['title']}', but I can help update the event, add tasks, review budget, or compare venue/catering options."
            else:
                reply = "I’m not fully sure how to apply that yet. Try asking me to create an event, update guest count, set a budget, add catering, add a venue, or list tasks."
        chat_state["pending_followup"] = None
        _save_chat_state(chat_state)

        return jsonify({
            "reply": reply,
            "action": "chat_reply"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
