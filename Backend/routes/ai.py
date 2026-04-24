from flask import current_app
from ai.llm_fallback import safe_ollama_interpret
from ai.action_interpreter import build_interpret_result_from_llm
from flask import Blueprint, request, jsonify, session
from ai.unified_chatbot import UnifiedChatbot
from ai.action_interpreter import interpret_message, get_default_chat_state, resolve_target_event
from ai.entity_parser import extract_planning_preferences
from ai.planning_engine import search_venues, search_caterers
from ai.budget_engine import calculate_budget_totals, analyze_budget, generate_budget_estimate
from models.database import get_db
import sqlite3
import re


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
               guest_count, budget_total, selected_venue, selected_catering,
               estimated_venue_cost, estimated_catering_cost, venue_cost, food_cost_per_person
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



def _clean_number(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _find_matching_caterer(name):
    if not name:
        return None
    db = get_db()
    exact = db.execute(
        "SELECT * FROM caterers WHERE lower(name) = lower(?) LIMIT 1",
        (name,),
    ).fetchone()
    if exact:
        return dict(exact)
    like = db.execute(
        "SELECT * FROM caterers WHERE lower(name) LIKE lower(?) ORDER BY cost_per_person ASC LIMIT 1",
        (f"%{name}%",),
    ).fetchone()
    return dict(like) if like else None


def _find_matching_venue(name):
    if not name:
        return None
    db = get_db()
    exact = db.execute(
        "SELECT * FROM venues WHERE lower(name) = lower(?) LIMIT 1",
        (name,),
    ).fetchone()
    if exact:
        return dict(exact)
    like = db.execute(
        "SELECT * FROM venues WHERE lower(name) LIKE lower(?) ORDER BY estimated_cost ASC LIMIT 1",
        (f"%{name}%",),
    ).fetchone()
    return dict(like) if like else None


def _apply_service_fields(event_data):
    event_data = dict(event_data or {})
    guest_count = int(_clean_number(event_data.get("guest_count"), 0))

    catering_name = event_data.get("selected_catering") or event_data.get("catering")
    if catering_name:
        event_data["selected_catering"] = catering_name
        caterer = _find_matching_caterer(catering_name)
        if caterer:
            cost_per_person = _clean_number(caterer.get("cost_per_person"), 0)
            if cost_per_person > 0 and _clean_number(event_data.get("food_cost_per_person"), 0) <= 0:
                event_data["food_cost_per_person"] = cost_per_person
            if guest_count > 0 and _clean_number(event_data.get("estimated_catering_cost"), 0) <= 0:
                event_data["estimated_catering_cost"] = round(guest_count * cost_per_person, 2)
        elif guest_count > 0 and _clean_number(event_data.get("estimated_catering_cost"), 0) <= 0:
            # Unknown caterer: keep the provider linked, but leave costs for the user/budget tool to estimate later.
            event_data["estimated_catering_cost"] = 0

    venue_name = event_data.get("selected_venue")
    location = event_data.get("location")
    venue = _find_matching_venue(venue_name or location)
    if venue:
        event_data["selected_venue"] = venue.get("name")
        estimated_cost = _clean_number(venue.get("estimated_cost"), 0)
        if _clean_number(event_data.get("venue_cost"), 0) <= 0:
            event_data["venue_cost"] = estimated_cost
        if _clean_number(event_data.get("estimated_venue_cost"), 0) <= 0:
            event_data["estimated_venue_cost"] = estimated_cost
    elif venue_name:
        event_data["selected_venue"] = venue_name

    totals = calculate_budget_totals(event_data)
    event_data["budget_subtotal"] = totals["subtotal"]
    event_data["budget_contingency"] = totals["contingency"]
    event_data["budget_total"] = totals["total"]
    return event_data

def create_event_for_user(user_id, event_data):
    db = get_db()
    event_data = _apply_service_fields(event_data)

    start_datetime = event_data.get("start_datetime")
    date = event_data.get("date") or (start_datetime[:10] if start_datetime else None)

    cursor = db.execute(
        """
        INSERT INTO events (
            title, date, start_datetime, end_datetime, location, description,
            guest_count, venue_cost, food_cost_per_person, selected_venue, selected_catering,
            estimated_venue_cost, estimated_catering_cost, decorations_cost,
            equipment_cost, staff_cost, marketing_cost, misc_cost,
            contingency_percent, budget_subtotal, budget_contingency, budget_total,
            user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            event_data.get("selected_venue"),
            event_data.get("selected_catering"),
            float(event_data.get("estimated_venue_cost") or 0),
            float(event_data.get("estimated_catering_cost") or 0),
            float(event_data.get("decorations_cost") or 0),
            float(event_data.get("equipment_cost") or 0),
            float(event_data.get("staff_cost") or 0),
            float(event_data.get("marketing_cost") or 0),
            float(event_data.get("misc_cost") or 0),
            float(event_data.get("contingency_percent") or 0),
            float(event_data.get("budget_subtotal") or 0),
            float(event_data.get("budget_contingency") or 0),
            float(event_data.get("budget_total") or 0),
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
        "selected_venue": event_data.get("selected_venue"),
        "selected_catering": event_data.get("selected_catering"),
        "estimated_venue_cost": float(event_data.get("estimated_venue_cost") or 0),
        "estimated_catering_cost": float(event_data.get("estimated_catering_cost") or 0),
        "catering": event_data.get("selected_catering") or event_data.get("catering"),
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
        "selected_venue",
        "selected_catering",
        "estimated_venue_cost",
        "estimated_catering_cost",
        "decorations_cost",
        "equipment_cost",
        "staff_cost",
        "marketing_cost",
        "misc_cost",
        "contingency_percent",
        "budget_subtotal",
        "budget_contingency",
        "budget_total",
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


def _extract_service_assignment(message):
    """Return a venue/catering assignment when the user is trying to attach a service to an event.

    This prevents messages like "add Chick-fil-A catering" or "set the venue to Local Park"
    from falling through to generic advice.
    """
    cleaned = (message or "").strip()
    lowered = cleaned.lower()

    action_words = r"(?:add|use|set|choose|select|make|change|update|attach|put)"

    catering_patterns = [
        rf"\b{action_words}\s+(?:the\s+)?catering\s+(?:to|as|from|with)?\s*(.+?)(?:\s+to\s+(?:this|that|the)\s+event)?(?:$|\.)",
        rf"\b{action_words}\s+(.+?)\s+catering(?:\s+to\s+(?:this|that|the)\s+event)?(?:$|\.)",
        r"\bcatering\s+(?:is|should be|will be|from|with)\s+(.+?)(?:$|\.)",
        r"\bfood\s+(?:is|should be|will be)?\s*(?:from|with)\s+(.+?)(?:$|\.)",
    ]
    for pattern in catering_patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            value = _clean_service_value(match.group(1))
            if value:
                return {"field": "selected_catering", "value": value}

    venue_patterns = [
        rf"\b{action_words}\s+(?:the\s+)?venue\s+(?:to|as|at|for)?\s*(.+?)(?:\s+to\s+(?:this|that|the)\s+event)?(?:$|\.)",
        rf"\b{action_words}\s+(.+?)\s+(?:as\s+)?(?:the\s+)?venue(?:\s+for\s+(?:this|that|the)\s+event)?(?:$|\.)",
        r"\bvenue\s+(?:is|should be|will be|at)\s+(.+?)(?:$|\.)",
    ]
    for pattern in venue_patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            value = _clean_service_value(match.group(1))
            if value:
                return {"field": "selected_venue", "value": value}

    return None


def _clean_service_value(value):
    if not value:
        return None
    value = re.sub(r"\b(?:to|for)\s+(?:this|that|the)\s+event\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:please|for me|thanks|thank you)\b", "", value, flags=re.IGNORECASE)
    value = value.strip(" .,!?:;\"'\t\n")
    if not value:
        return None
    blocked = {"catering", "venue", "food", "the venue", "the catering"}
    if value.lower() in blocked:
        return None
    return value


def _handle_service_assignment(user_id, user_message, context, chat_state):
    assignment = _extract_service_assignment(user_message)
    if not assignment:
        return None

    target_event = resolve_target_event(user_message, context, chat_state)
    if not target_event:
        return jsonify({
            "reply": "I can add that to an event, but I couldn’t tell which event you meant. Please mention the event title first.",
            "action": "service_assignment_needs_event"
        }), 200

    field = assignment["field"]
    value = assignment["value"]
    updates = {field: value}

    if field == "selected_venue":
        updates["location"] = value
        service_updates = _apply_service_fields({**dict(target_event), **updates})
        updates.update({
            "selected_venue": service_updates.get("selected_venue", value),
            "estimated_venue_cost": service_updates.get("estimated_venue_cost", 0),
            "venue_cost": service_updates.get("venue_cost", 0),
        })
    else:
        service_updates = _apply_service_fields({**dict(target_event), **updates})
        updates.update({
            "selected_catering": service_updates.get("selected_catering", value),
            "estimated_catering_cost": service_updates.get("estimated_catering_cost", 0),
            "food_cost_per_person": service_updates.get("food_cost_per_person", target_event.get("food_cost_per_person") or 0),
        })

    updated = update_event_in_db(target_event["id"], updates)
    if not updated:
        return jsonify({
            "reply": "I found the event, but I couldn’t save that venue/catering update.",
            "action": "service_assignment_failed"
        }), 200

    chat_state["last_event_id"] = target_event["id"]
    chat_state["pending_followup"] = None
    refreshed = dict(target_event)
    refreshed.update(updates)
    chat_state["planning_context"] = _seed_planning_context_from_event(chat_state.get("planning_context"), refreshed)
    _save_chat_state(chat_state)

    if field == "selected_venue":
        cost = updates.get("estimated_venue_cost") or 0
        cost_text = f" Estimated venue cost: ${float(cost):.2f}." if float(cost or 0) > 0 else " Venue cost is currently $0 unless you enter a rental fee."
        reply = f"Added {updates.get('selected_venue', value)} as the venue for '{target_event['title']}'." + cost_text
    else:
        cost = updates.get("estimated_catering_cost") or 0
        cost_text = f" Estimated catering cost: ${float(cost):.2f}." if float(cost or 0) > 0 else " Catering cost is currently $0 unless you enter a cost or matching provider."
        reply = f"Added {updates.get('selected_catering', value)} as the catering for '{target_event['title']}'." + cost_text

    return jsonify({
        "reply": reply,
        "action": "service_assigned",
        "event_id": target_event["id"],
        "updated_fields": updates
    }), 200




BUDGET_REQUEST_WORDS = [
    "budget", "cost", "costs", "spend", "spending", "price", "prices",
    "break down", "breakdown", "how much", "cheaper", "save money", "afford"
]


def _is_budget_request(message):
    lowered = (message or "").lower()
    return any(word in lowered for word in BUDGET_REQUEST_WORDS)


def _format_money(value):
    try:
        return f"${float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _get_full_event_for_user(user_id, event_id):
    if not event_id:
        return None
    db = get_db()
    row = db.execute(
        "SELECT * FROM events WHERE id = ? AND user_id = ?",
        (event_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def _build_budget_reply(event, analysis, generated=False):
    summary = analysis.get("summary", {})
    health = analysis.get("health", {})
    warnings = analysis.get("warnings", []) or []
    suggestions = analysis.get("suggestions", []) or []

    prefix = "I generated and saved a smart budget estimate." if generated else "Here is the current budget breakdown."
    lines = [
        f"{prefix} For '{event.get('title', 'this event')}':",
        f"• Estimated total: {_format_money(summary.get('total'))}",
        f"• Cost per guest: {_format_money(summary.get('cost_per_guest'))}",
        f"• Venue: {_format_money(summary.get('venue_cost'))}",
        f"• Food total: {_format_money(summary.get('food_total'))} ({_format_money(summary.get('food_cost_per_person'))}/person)",
        f"• Largest category: {str(summary.get('largest_category') or 'none').title()}",
        f"• Budget health: {health.get('label', 'Not analyzed')} ({health.get('score', '—')}/100)",
    ]

    if warnings:
        lines.append("Main warning: " + warnings[0])
    if suggestions:
        lines.append("Suggestion: " + suggestions[0])

    lines.append("You can ask me to make it cheaper, generate a smart budget, or update a specific category like venue cost or food per person.")
    return "\n".join(lines)


def _handle_budget_request(user_id, user_message, context, chat_state):
    if not _is_budget_request(user_message):
        return None

    target_event = resolve_target_event(user_message, context, chat_state)
    if not target_event:
        return jsonify({
            "reply": "I can help with the budget, but I couldn’t tell which event you mean. Please mention the event title or select an event first.",
            "action": "budget_needs_event"
        }), 200

    full_event = _get_full_event_for_user(user_id, target_event.get("id"))
    if not full_event:
        return jsonify({
            "reply": "I couldn’t find that event anymore.",
            "action": "budget_failed"
        }), 200

    lowered = (user_message or "").lower()
    should_generate = any(phrase in lowered for phrase in [
        "generate", "estimate", "smart budget", "build a budget", "create a budget", "make a budget"
    ])

    generated = False
    if should_generate:
        estimate = generate_budget_estimate(full_event)
        event_data = estimate.get("event", {})
        update_fields = {
            "guest_count": event_data.get("guest_count", 0),
            "venue_cost": event_data.get("venue_cost", 0),
            "food_cost_per_person": event_data.get("food_cost_per_person", 0),
            "decorations_cost": event_data.get("decorations_cost", 0),
            "equipment_cost": event_data.get("equipment_cost", 0),
            "staff_cost": event_data.get("staff_cost", 0),
            "marketing_cost": event_data.get("marketing_cost", 0),
            "misc_cost": event_data.get("misc_cost", 0),
            "contingency_percent": event_data.get("contingency_percent", 0),
            "budget_subtotal": event_data.get("budget_subtotal", 0),
            "budget_contingency": event_data.get("budget_contingency", 0),
            "budget_total": event_data.get("budget_total", 0),
        }
        update_event_in_db(full_event["id"], update_fields)
        full_event.update(update_fields)
        generated = True

    analysis = analyze_budget(full_event)
    chat_state["last_event_id"] = full_event["id"]
    chat_state["pending_followup"] = None
    chat_state["planning_context"] = _seed_planning_context_from_event(chat_state.get("planning_context"), full_event)
    _save_chat_state(chat_state)

    return jsonify({
        "reply": _build_budget_reply(full_event, analysis, generated=generated),
        "action": "budget_answer",
        "event_id": full_event["id"],
        "analysis": analysis,
        "event": full_event,
    }), 200


def _extract_task_update_request(message):
    cleaned = (message or "").strip()
    patterns = [
        ("title", r"(?:rename|change|update)\s+(?:the\s+)?task\s+(.+?)\s+to\s+(.+)$"),
        ("title", r"(?:rename|change|update)\s+(.+?)\s+task\s+to\s+(.+)$"),
    ]
    for field, pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return {"task_ref": _clean_service_value(match.group(1)), "updates": {field: _clean_service_value(match.group(2))}}

    date_match = re.search(r"(?:schedule|set|change|update)\s+(?:the\s+)?task\s+(.+?)\s+(?:for|on|to|by)\s+([a-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)$", cleaned, re.IGNORECASE)
    if date_match:
        return {"task_ref": _clean_service_value(date_match.group(1)), "updates": {"due_date": _clean_service_value(date_match.group(2))}}

    return None


def update_task_for_user(user_id, task_id, updates):
    db = get_db()
    task = db.execute(
        """
        SELECT tasks.*, events.title AS event_title
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE tasks.id = ? AND events.user_id = ?
        """,
        (task_id, user_id),
    ).fetchone()
    if not task:
        return None, "That task was not found for the current user."

    allowed = {"title", "due_date", "start_datetime", "end_datetime", "completed"}
    set_parts = []
    values = []
    for key, value in (updates or {}).items():
        if key in allowed and value not in (None, ""):
            set_parts.append(f"{key} = ?")
            values.append(value)

    if not set_parts:
        return None, "I found the task, but I couldn’t tell what to change."

    values.append(task_id)
    db.execute(f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?", values)
    db.commit()
    updated = db.execute(
        """
        SELECT tasks.*, events.title AS event_title
        FROM tasks
        INNER JOIN events ON tasks.event_id = events.id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()
    return dict(updated), None


def _handle_task_update(user_id, user_message, context, chat_state):
    request_data = _extract_task_update_request(user_message)
    if not request_data:
        return None

    event_hint = resolve_target_event(user_message, context, chat_state)
    target_task = _find_task_by_reference(
        request_data.get("task_ref"),
        context.get("tasks", []),
        event_hint.get("id") if event_hint else chat_state.get("last_event_id"),
    )
    if not target_task:
        return jsonify({
            "reply": "I can update a task, but I couldn’t tell which task you meant. Try using the task name, like 'rename task Confirm venue to Confirm park reservation.'",
            "action": "task_update_needs_task"
        }), 200

    updated_task, error = update_task_for_user(user_id, target_task["id"], request_data.get("updates", {}))
    if error:
        return jsonify({"reply": error, "action": "task_update_failed"}), 200

    chat_state["last_task_id"] = updated_task["id"]
    chat_state["last_event_id"] = updated_task["event_id"]
    chat_state["pending_followup"] = None
    _save_chat_state(chat_state)

    return jsonify({
        "reply": f"Updated task '{updated_task['title']}' for '{updated_task['event_title']}'.",
        "action": "task_updated",
        "task": updated_task,
    }), 200

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


def _get_event_for_user(user_id, event_id):
    db = get_db()
    row = db.execute(
        """
        SELECT id, title, date, start_datetime, end_datetime, location, description,
               guest_count, budget_total, selected_venue, selected_catering,
               estimated_venue_cost, estimated_catering_cost, venue_cost, food_cost_per_person
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

        service_assignment_response = _handle_service_assignment(user_id, user_message, context, chat_state)
        if service_assignment_response:
            return service_assignment_response

        followup_response = _handle_pending_followup(user_id, user_message, chat_state)
        if followup_response:
            return followup_response

        task_update_response = _handle_task_update(user_id, user_message, context, chat_state)
        if task_update_response:
            return task_update_response

        budget_response = _handle_budget_request(user_id, user_message, context, chat_state)
        if budget_response:
            return budget_response

        planning_updates = extract_planning_preferences(user_message)
        target_for_planning = resolve_target_event(user_message, context, chat_state)
        planning_context = _merge_planning_context(chat_state.get("planning_context"), planning_updates)
        planning_context = _seed_planning_context_from_event(planning_context, target_for_planning)
        chat_state["planning_context"] = planning_context

        interpreted = interpret_message(user_message, context=context, state=chat_state)
        action_type = interpreted["type"]

        service_assignment_response = _handle_service_assignment(user_id, user_message, context, chat_state)
        if service_assignment_response:
            return service_assignment_response

        if action_type == "fallback" and _is_venue_request(user_message):
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

        if action_type == "fallback" and _is_catering_request(user_message):
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
            created_event = create_event_for_user(user_id, interpreted["draft"])

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
                    f"Would you like me to add starter tasks like confirming the venue, arranging catering, or sending invites?"
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
            if cleaned_updates.get("catering") and not cleaned_updates.get("selected_catering"):
                cleaned_updates["selected_catering"] = cleaned_updates.pop("catering")
            cleaned_updates = _apply_time_logic(target_event, cleaned_updates)
            cleaned_updates = _apply_service_fields({**dict(target_event), **cleaned_updates}) | cleaned_updates

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
