from flask import Blueprint, request, jsonify, session
from ai.unified_chatbot import UnifiedChatbot
from models.database import get_db
import sqlite3
from ai.entity_parser import (
    extract_event_fields,
    extract_event_update_fields,
    looks_like_event_creation,
    looks_like_event_update,
    merge_event_draft,
    missing_required_event_fields,
    build_missing_fields_prompt,
)

ai_bp = Blueprint("ai", __name__)
chatbot = UnifiedChatbot()


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


def get_user_events(user_id):
    db = get_db()
    rows = db.execute(
        """
        SELECT id, title, date, start_datetime, end_datetime, location, description,
               guest_count, venue_cost, food_cost_per_person, decorations_cost,
               equipment_cost, staff_cost, marketing_cost, misc_cost,
               contingency_percent, budget_subtotal, budget_contingency, budget_total
        FROM events
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    return [dict(row) for row in rows]


def find_event_by_title_reference(user_message, events):
    lowered_message = user_message.lower()

    for event in events:
        title = (event.get("title") or "").strip()
        if title and title.lower() in lowered_message:
            return event

    return None


def looks_like_existing_event_edit(message: str):
    lowered = message.lower()

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
        "set the catering",
        "change the catering",
        "update the catering",
        "catering is",
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
    ]

    return any(phrase in lowered for phrase in edit_phrases)


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


def find_event_from_session_reference(user_id, user_message):
    db = get_db()
    lowered = user_message.lower()

    referenced_words = ["it", "that event", "this event", "the event", "that one", "this one"]

    if not any(word in lowered for word in referenced_words):
        return None

    last_event_id = session.get("last_event_id")
    if not last_event_id:
        return None

    row = db.execute(
        """
        SELECT id, title, date, start_datetime, end_datetime, location, description,
               guest_count, venue_cost, food_cost_per_person, decorations_cost,
               equipment_cost, staff_cost, marketing_cost, misc_cost,
               contingency_percent, budget_subtotal, budget_contingency, budget_total
        FROM events
        WHERE id = ? AND user_id = ?
        """,
        (last_event_id, user_id)
    ).fetchone()

    return dict(row) if row else None


@ai_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        context = load_user_context(session["user_id"])

        pending_event_draft = session.get("pending_event_draft")
        event_creation_triggered = (
            looks_like_event_creation(user_message)
            or (pending_event_draft is not None)
            or looks_like_event_update(user_message)
        )

        # Handle pending/new event draft first so follow-up answers
        # do not get mistaken for edits to an already-saved event.
        if event_creation_triggered:
            extracted = extract_event_fields(user_message)
            draft = merge_event_draft(pending_event_draft or {}, extracted)

            missing = missing_required_event_fields(draft)

            if missing:
                session["pending_event_draft"] = draft
                return jsonify({
                    "reply": build_missing_fields_prompt(draft),
                    "action": "event_create_collecting",
                    "draft": draft
                }), 200

            created_event = create_event_for_user(session["user_id"], draft)
            session.pop("pending_event_draft", None)
            session["last_event_id"] = created_event["id"]

            return jsonify({
                "reply": (
                    f"Event '{created_event['title']}' was created"
                    f" for {created_event['date'] or created_event['start_datetime']}"
                    f" at {created_event['location']}."
                ),
                "action": "event_created",
                "event": created_event
            }), 200

        user_events = get_user_events(session["user_id"])

        if looks_like_existing_event_edit(user_message):
            target_event = find_event_by_title_reference(user_message, user_events)

            if not target_event:
                last_event_id = session.get("last_event_id")
                if last_event_id:
                    target_event = next(
                        (event for event in user_events if event["id"] == last_event_id),
                        None
                    )
            if target_event:
                update_data = extract_event_update_fields(user_message)

                cleaned_updates = {
                    key: value
                    for key, value in update_data.items()
                    if value not in (None, "", [])
                }

                cleaned_updates.pop("catering", None)
                cleaned_updates.pop("event_size_hint", None)

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

                updated = update_event_in_db(target_event["id"], cleaned_updates)

                if updated:
                    session["last_event_id"] = target_event["id"]

                    new_title = cleaned_updates.get("title", target_event["title"])
                    new_date = cleaned_updates.get("date", target_event.get("date"))
                    new_location = cleaned_updates.get("location", target_event.get("location"))

                    return jsonify({
                        "reply": f"Updated '{new_title}' for {new_date} at {new_location}.",
                        "action": "event_updated",
                        "event_id": target_event["id"],
                        "updated_fields": cleaned_updates
                    }), 200

                return jsonify({
                    "reply": "I found the event, but I couldn’t tell what fields to update.",
                    "action": "event_update_failed"
                }), 200

            return jsonify({
                "reply": "I couldn’t tell which event you wanted to update. Please mention the event title.",
                "action": "event_update_needs_title"
            }), 200

        add_action = chatbot.parse_add_task_command(user_message, context=context)
        if add_action:
            if "error" in add_action:
                return jsonify({
                    "reply": add_action["error"],
                    "action": "task_create_needs_event"
                }), 200

            created_task, error = create_task_for_user(session["user_id"], add_action)

            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_create_failed"
                }), 200

            return jsonify({
                "reply": (
                    f"Task '{created_task['title']}' was added to "
                    f"'{created_task['event_title']}'"
                    + (f" with timing starting {created_task['start_datetime']}." if created_task["start_datetime"] else (f" with due date {created_task['due_date']}." if created_task["due_date"] else "."))
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

            completed_task, error = complete_task_for_user(session["user_id"], complete_action["task_id"])

            if error:
                return jsonify({
                    "reply": error,
                    "action": "task_complete_failed"
                }), 200

            return jsonify({
                "reply": (
                    f"Task '{completed_task['title']}' for "
                    f"'{completed_task['event_title']}' was marked complete."
                ),
                "action": "task_completed",
                "task": completed_task
            }), 200

        reply = chatbot.get_response(user_message, context=context)

        return jsonify({
            "reply": reply,
            "action": "chat_reply"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/clear-chat", methods=["POST"])
def clear_chat():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    session.pop("pending_event_draft", None)
    session.pop("last_event_id", None)

    return jsonify({
        "message": "Chat state cleared"
    }), 200