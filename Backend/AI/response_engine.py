import re
from .planning_engine import search_venues, search_caterers, estimate_budget


def get_event_tasks(selected_event, all_tasks):
    if not selected_event:
        return []

    event_id = selected_event.get("id")
    return [
        task for task in all_tasks
        if int(task.get("event_id", 0)) == int(event_id)
    ]


def _extract_guest_count(text, selected_event=None):
    if selected_event and selected_event.get("guest_count"):
        try:
            return int(selected_event.get("guest_count"))
        except (TypeError, ValueError):
            pass

    match = re.search(r"(\d{1,4})\s*(people|guests|attendees|ppl)", text)
    if match:
        return int(match.group(1))

    if "small" in text:
        return 20
    if "medium" in text:
        return 75
    if "large" in text:
        return 200
    return None


def _detect_budget_level(text):
    if any(phrase in text for phrase in ["cheap", "low budget", "affordable", "not too expensive", "budget-friendly", "save money"]):
        return "budget"
    if any(phrase in text for phrase in ["formal", "upscale", "premium", "polished", "high-end"]):
        return "premium"
    if "mid" in text or "moderate" in text:
        return "mid"
    return None


def _detect_service_type(text):
    if any(word in text for word in ["tray", "trays", "pickup", "boxed"]):
        return "trays"
    if "buffet" in text:
        return "buffet"
    if "plated" in text or "formal" in text:
        return "plated"
    return None


def _detect_cuisine(text):
    options = ["bbq", "italian", "mexican", "mediterranean", "indian", "seafood", "american", "korean"]
    for option in options:
        if option in text:
            return option
    return None


def _detect_venue_type(text):
    if any(word in text for word in ["restaurant", "dinner"]):
        return "restaurant"
    if any(word in text for word in ["ballroom", "banquet"]):
        return "ballroom"
    if any(word in text for word in ["classroom", "meeting room"]):
        return "classroom"
    if any(word in text for word in ["theater", "theatre"]):
        return "theater"
    if "arena" in text:
        return "arena"
    if "outdoor" in text or "park" in text:
        return "outdoor"
    return None


def _detect_indoor_outdoor(text):
    if "outdoor" in text:
        return "outdoor"
    if "indoor" in text:
        return "indoor"
    return None


def _context_snapshot(text, selected_event=None):
    location = None
    if selected_event:
        location = selected_event.get("location")
    return {
        "guest_count": _extract_guest_count(text, selected_event),
        "budget_level": _detect_budget_level(text),
        "service_type": _detect_service_type(text),
        "cuisine": _detect_cuisine(text),
        "venue_type": _detect_venue_type(text),
        "indoor_outdoor": _detect_indoor_outdoor(text),
        "location_area": location,
    }


def _summarize_caterer(option):
    bits = [option.get("name", "Unknown caterer")]
    cuisine = option.get("cuisine")
    service = option.get("service_type") or option.get("type")
    price = option.get("cost_per_person")
    reason = None
    reasons = option.get("reasons") or []
    if reasons:
        reason = reasons[0]

    details = []
    if cuisine:
        details.append(cuisine)
    if service:
        details.append(service)
    if price not in (None, ""):
        details.append(f"${price}/person")

    summary = " — ".join([bits[0], ", ".join(details)]) if details else bits[0]
    if reason:
        summary += f" ({reason})"
    return summary


def _summarize_venue(option):
    name = option.get("name", "Unknown venue")
    venue_type = option.get("venue_type") or option.get("type")
    capacity = option.get("capacity")
    cost = option.get("estimated_cost") or option.get("cost")
    reasons = option.get("reasons") or []

    details = []
    if venue_type:
        details.append(venue_type)
    if capacity:
        details.append(f"capacity {capacity}")
    if cost not in (None, ""):
        details.append(f"about ${cost}")

    summary = f"{name} — {', '.join(details)}" if details else name
    if reasons:
        summary += f" ({reasons[0]})"
    return summary


def _generic_catering_reply():
    return (
        "Catering usually comes down to event size, budget, and how polished you want the food to feel. "
        "For smaller casual events, trays are usually easiest. For medium groups, buffet service is often the safest choice. "
        "For more formal events, plated service feels more polished. About how many people are you expecting?"
    )


def _generic_venue_reply():
    return (
        "The best venue depends mostly on guest count, budget, and the kind of atmosphere you want. "
        "For smaller events, simple spaces are usually easier and cheaper. For medium events, halls or ballrooms tend to work well. "
        "For larger events, you need capacity and parking to matter more. About how many people are you expecting?"
    )


def _tailored_catering_reply(text, selected_event=None):
    prefs = _context_snapshot(text, selected_event)
    has_context = any([prefs.get("guest_count"), prefs.get("budget_level"), prefs.get("service_type"), prefs.get("cuisine")])
    if not has_context:
        return _generic_catering_reply()

    options = search_caterers(prefs, limit=3)
    if not options:
        return (
            "I can narrow catering down once I know a little more about the event. "
            "Do you want something casual and budget-friendly, or something more polished?"
        )

    count = prefs.get("guest_count")
    opener = "For this event, I would narrow it down to a few options"
    if count:
        opener = f"For about {count} guests, I would narrow it down to a few options"

    formatted = "\n".join(f"• {_summarize_caterer(option)}" for option in options)

    follow_up = "Do you want the food to feel more casual, more polished, or as affordable as possible?"
    if prefs.get("service_type") == "trays":
        follow_up = "Do you want me to keep this tray-based and budget-friendly, or compare it to buffet options?"
    elif prefs.get("budget_level") == "premium":
        follow_up = "Do you want me to keep this more formal, or bring in a couple more mid-range options too?"

    return f"{opener}:\n{formatted}\n\n{follow_up}"


def _tailored_venue_reply(text, selected_event=None):
    prefs = _context_snapshot(text, selected_event)
    has_context = any([prefs.get("guest_count"), prefs.get("budget_level"), prefs.get("venue_type"), prefs.get("indoor_outdoor")])
    if not has_context:
        return _generic_venue_reply()

    options = search_venues(prefs, limit=3)
    if not options:
        return (
            "I can narrow venue options down once I know a little more about the event. "
            "Do you want something smaller and affordable, or something more polished?"
        )

    count = prefs.get("guest_count")
    opener = "For this kind of event, these venues look like the best fit"
    if count:
        opener = f"For about {count} guests, these venues look like the best fit"

    formatted = "\n".join(f"• {_summarize_venue(option)}" for option in options)
    follow_up = "Do you want me to narrow this down by affordability, vibe, or capacity?"
    if prefs.get("indoor_outdoor") == "outdoor":
        follow_up = "Do you want to keep this focused on outdoor-friendly spaces, or compare them to indoor backups too?"

    return f"{opener}:\n{formatted}\n\n{follow_up}"


def _budget_reply(selected_event=None):
    result = estimate_budget(selected_event)
    return (
        f"A simple starting budget is venue around ${result['venue']}, food around ${result['food']}, and misc costs around ${result['misc']}. "
        f"That puts the total near ${result['total']}. Do you want me to make this more budget-friendly or more polished?"
    )


def get_response(intent, text, context=None, selected_event=None, confidence=None):
    text_lower = text.lower()
    context = context or {"events": [], "tasks": []}

    events = context.get("events", [])
    tasks = context.get("tasks", [])

    total_events = len(events)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if int(task.get("completed", 0)) == 1)
    pending_tasks = total_tasks - completed_tasks

    event_tasks = get_event_tasks(selected_event, tasks)
    pending_event_tasks = [task for task in event_tasks if int(task.get("completed", 0)) == 0]

    if intent == "unclear":
        return "I can help with planning, budget, venues, catering, tasks, or a summary of one of your events. What part are you thinking through right now?"

    if "venue" in text_lower or "location" in text_lower:
        return _tailored_venue_reply(text_lower, selected_event)

    if "catering" in text_lower or "food" in text_lower:
        return _tailored_catering_reply(text_lower, selected_event)

    if "budget" in text_lower or "estimate" in text_lower or intent == "budgeting":
        return _budget_reply(selected_event)

    if intent == "greeting":
        if selected_event:
            return (
                f"Hi! I can help with '{selected_event['title']}'. "
                f"Do you want to talk through budget, venue, catering, timeline, or next tasks?"
            )
        if events:
            return (
                f"Hi! You currently have {total_events} event(s) and {pending_tasks} pending task(s). "
                f"What part do you want to work through first?"
            )
        return "Hi! I can help you plan an event, estimate a budget, compare venues, or look at catering. What do you want to start with?"

    if intent == "event_creation":
        return (
            "The best place to start is with the core details: purpose, guest count, date, location, and spending limit. "
            "Once those basics are set, the rest gets much easier. What kind of event are you trying to host?"
        )

    if intent == "event_summary":
        if not events:
            return "You do not have any events yet. Create one first and I can summarize it."

        if selected_event:
            return (
                f"Here is the current picture for '{selected_event['title']}'. "
                f"It is scheduled for {selected_event.get('date', 'not set')}. "
                f"The location is {selected_event.get('location', 'not set')}. "
                f"There are {len(event_tasks)} task(s) tied to it, with {len(pending_event_tasks)} still open. "
                f"Do you want a budget summary or the next recommended actions?"
            )

        next_event = events[0]
        return (
            f"You currently have {total_events} event(s), {total_tasks} total task(s), and {pending_tasks} pending task(s). "
            f"Your next event appears to be '{next_event.get('title', 'Untitled Event')}'. "
            f"Do you want a quick summary of that one?"
        )

    if intent == "task_help":
        if selected_event:
            if pending_event_tasks:
                next_tasks = pending_event_tasks[:3]
                task_list = ", ".join(task["title"] for task in next_tasks)
                return (
                    f"For '{selected_event['title']}', the next tasks I would prioritize are {task_list}. "
                    f"You still have {len(pending_event_tasks)} incomplete task(s). Do you want a simple first-second-third order for them?"
                )

            return (
                f"'{selected_event['title']}' does not have any pending tasks right now. "
                f"A smart next step would be reviewing event-day logistics and confirmations."
            )

        if pending_tasks:
            next_tasks = [task for task in tasks if int(task.get("completed", 0)) == 0][:3]
            task_list = ", ".join(task["title"] for task in next_tasks) if next_tasks else "your pending tasks"
            return (
                f"Across all events, you currently have {pending_tasks} pending task(s). "
                f"The next few worth handling are {task_list}. Do you want me to narrow that down to one event?"
            )

        return "You do not have any tasks yet. Add a few tasks and I can help prioritize them."

    if intent == "event_help":
        if "timeline" in text_lower or "schedule" in text_lower:
            return (
                "A good event timeline usually moves from core decisions into bookings, then confirmations, then event-day setup and follow-up. "
                "When is the event happening? I can turn that into a shorter countdown if you already have a date."
            )

        return (
            "A good event plan usually covers the basics first, then venue, food, tasks, and day-of logistics. "
            "What part do you want to narrow down first?"
        )

    return "I’m not sure yet, but I can help with event planning if you give me a little more detail."
