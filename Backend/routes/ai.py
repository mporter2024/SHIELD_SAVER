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
    return any(word in lowered for word in ["catering", "caterer", "food", "buffet", "plated", "food truck"])


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


def _format_catering_reply(results, planning_context):
    if not results:
        area = planning_context.get("location_area") or "your area"
        return f"I couldn't find a strong catering match in {area} with the current filters. Try loosening cuisine, service type, or budget."

    signal_count = _planning_signal_count(planning_context, ["guest_count", "cuisine", "service_type", "budget_per_person", "budget_level", "location_area"])
    if signal_count < 2:
        return _generic_catering_reply(planning_context)

    guest_count = planning_context.get("guest_count")
    if guest_count:
        intro = f"For about {guest_count} guests, these look like the best catering fits:"
    else:
        intro = "Here are a few catering options that look like the best fit:"

    lines = [_summarize_catering_option(item) for item in results[:3]]
    return intro + "\n" + "\n".join(lines) + "\n\nDo you want me to narrow this down by budget, formality, or cuisine?"


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
    if normalized in {"chickfil", "chickfila", "chickfilacatering", "chickfilfood"} or normalized.startswith("chickfil"):
        return "Chick-Fil-A"
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
    # Fast path for common provider variants, including typo forms like
    # "chick-fil-catering".
    normalized_message = re.sub(r"[^a-z0-9]", "", (message or "").lower())
    if service_type == "catering" and "chickfil" in normalized_message:
        return {"name": "Chick-Fil-A", "cost_per_person": 12.0}

    db = get_db()
    if service_type == "venue":
        rows = db.execute("SELECT * FROM venues ORDER BY LENGTH(name) DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM caterers ORDER BY LENGTH(name) DESC").fetchall()
    lowered = _normalize_text(message)
    for row in rows:
        item = dict(row)
        if _normalize_text(item.get("name")) in lowered:
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
    return None


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

        followup_response = _handle_pending_followup(user_id, user_message, chat_state)
        if followup_response:
            return followup_response

        planning_updates = extract_planning_preferences(user_message)
        target_for_planning = resolve_target_event(user_message, context, chat_state)
        planning_context = _merge_planning_context(chat_state.get("planning_context"), planning_updates)
        planning_context = _seed_planning_context_from_event(planning_context, target_for_planning)
        chat_state["planning_context"] = planning_context

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
            catering_results = search_caterers(planning_context, limit=3)
            planning_context["last_recommendations"]["caterers"] = [item.get("id") for item in catering_results]
            chat_state["planning_context"] = planning_context
            if target_for_planning:
                chat_state["last_event_id"] = target_for_planning["id"]
            _save_chat_state(chat_state)
            return jsonify({
                "reply": _format_catering_reply(catering_results, planning_context),
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
        chat_state["pending_followup"] = None
        _save_chat_state(chat_state)

        return jsonify({
            "reply": reply,
            "action": "chat_reply"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
