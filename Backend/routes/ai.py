from flask import Blueprint, request, jsonify, session
from ai.unified_chatbot import UnifiedChatbot
from ai.action_interpreter import interpret_message, get_default_chat_state, resolve_target_event
from ai.entity_parser import extract_planning_preferences
from ai.planning_engine import search_venues, search_caterers
from models.database import get_db
import sqlite3

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
               guest_count, budget_total
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
            user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        "catering": event_data.get("catering"),
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


def _format_venue_reply(results, planning_context):
    if not results:
        area = planning_context.get("location_area") or "your area"
        return f"I couldn't find a strong venue match in {area} with the current filters. Try loosening the budget, guest count, or venue style."

    intro_bits = []
    if planning_context.get("guest_count"):
        intro_bits.append(f"for about {planning_context['guest_count']} guests")
    if planning_context.get("location_area"):
        intro_bits.append(f"near {planning_context['location_area']}")
    if planning_context.get("indoor_outdoor"):
        intro_bits.append(planning_context["indoor_outdoor"])
    if planning_context.get("budget_level"):
        intro_bits.append(f"{planning_context['budget_level']} budget")

    intro = " ".join(intro_bits).strip()
    if intro:
        intro = f"Based on your preferences {intro}, here are the best venue options\n\n"
    else:
        intro = "Here are the best venue options I found\n\n"

    lines = []
    for idx, item in enumerate(results, start=1):
        reasons = "; ".join(item.get("reasons") or [])
        lines.append(
            f"{idx}. {item['name']} — {item.get('venue_type') or item.get('type')} in {item.get('city') or item.get('location')}\n"
            f"   Capacity: {item.get('capacity')} | Estimated cost: ${int(float(item.get('estimated_cost') or item.get('cost') or 0))} | Rating: {item.get('rating')}\n"
            + (f"   Why it fits: {reasons}\n" if reasons else "")
            + (f"   {item.get('description')}" if item.get('description') else "")
        )
    return intro + "\n\n".join(lines)


def _format_catering_reply(results, planning_context):
    if not results:
        area = planning_context.get("location_area") or "your area"
        return f"I couldn't find a strong catering match in {area} with the current filters. Try loosening cuisine, service type, or budget."

    intro_bits = []
    if planning_context.get("cuisine"):
        intro_bits.append(planning_context["cuisine"])
    if planning_context.get("service_type"):
        intro_bits.append(planning_context["service_type"])
    if planning_context.get("budget_per_person"):
        intro_bits.append(f"under ${int(planning_context['budget_per_person'])} per person")
    if planning_context.get("location_area"):
        intro_bits.append(f"near {planning_context['location_area']}")

    intro = " ".join(intro_bits).strip()
    if intro:
        intro = f"Based on your catering preferences {intro}, here are the best options\n\n"
    else:
        intro = "Here are the best catering options I found\n\n"

    lines = []
    for idx, item in enumerate(results, start=1):
        reasons = "; ".join(item.get("reasons") or [])
        dietary = item.get("dietary_options") or "not listed"
        lines.append(
            f"{idx}. {item['name']} — {item.get('cuisine')} | {item.get('service_type')}\n"
            f"   Cost: ${float(item.get('cost_per_person') or 0):.0f} per person | Rating: {item.get('rating')} | Dietary: {dietary}\n"
            + (f"   Why it fits: {reasons}\n" if reasons else "")
            + (f"   {item.get('description')}" if item.get('description') else "")
        )
    return intro + "\n\n".join(lines)


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
               guest_count, budget_total
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

        if _is_venue_request(user_message):
            venue_results = search_venues(planning_context, limit=5)
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
            catering_results = search_caterers(planning_context, limit=5)
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

        add_action = chatbot.parse_add_task_command(user_message, context=context)
        if add_action:
            if "error" in add_action:
                return jsonify({
                    "reply": add_action["error"],
                    "action": "task_create_needs_event"
                }), 200

            created_task, error = create_task_for_user(user_id, add_action)
            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_create_failed"
                }), 200

            chat_state["last_task_id"] = created_task["id"]
            chat_state["last_event_id"] = created_task["event_id"]
            chat_state["last_intent"] = "task_create"
            chat_state["pending_followup"] = {
                "type": "add_another_task",
                "event_id": created_task["event_id"]
            }
            _save_chat_state(chat_state)

            timing_suffix = (
                f" with timing starting {created_task['start_datetime']}."
                if created_task["start_datetime"]
                else (
                    f" with due date {created_task['due_date']}."
                    if created_task["due_date"] else "."
                )
            )

            return jsonify({
                "reply": (
                    f"Task '{created_task['title']}' was added to '{created_task['event_title']}'"
                    + timing_suffix
                    + " Would you like me to add another task for this event?"
                ),
                "action": "task_created",
                "task": created_task
            }), 200

        complete_action = chatbot.parse_complete_task_command(user_message, context=context)
        if complete_action:
            if "error" in complete_action:
                return jsonify({
                    "reply": complete_action["error"],
                    "action": "task_complete_failed"
                }), 200

            completed_task, error = complete_task_for_user(user_id, complete_action["task_id"])
            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_complete_failed"
                }), 200

            chat_state["last_task_id"] = completed_task["id"]
            chat_state["last_event_id"] = completed_task["event_id"]
            chat_state["last_intent"] = "task_complete"
            chat_state["pending_followup"] = None
            _save_chat_state(chat_state)

            return jsonify({
                "reply": (
                    f"Task '{completed_task['title']}' for '{completed_task['event_title']}' was marked complete. "
                    f"Would you like me to help with the next task?"
                ),
                "action": "task_completed",
                "task": completed_task
            }), 200

        interpreted = interpret_message(user_message, context=context, state=chat_state)
        action_type = interpreted["type"]

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

        reply = chatbot.get_response(user_message, context=context)
        chat_state["pending_followup"] = None
        _save_chat_state(chat_state)

        return jsonify({
            "reply": reply,
            "action": "chat_reply"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
