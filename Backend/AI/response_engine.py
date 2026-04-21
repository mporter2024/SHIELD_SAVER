from .planning_engine import get_venues, get_catering, estimate_budget


def _normalize(text):
    return (text or "").strip().lower()


def _event_tasks(selected_event, all_tasks):
    if not selected_event:
        return []
    event_id = selected_event.get("id")
    return [task for task in all_tasks if int(task.get("event_id", 0)) == int(event_id)]


def _pending_tasks(tasks):
    return [task for task in tasks if int(task.get("completed", 0)) == 0]


def _guest_count(selected_event, text_lower):
    if selected_event and selected_event.get("guest_count"):
        try:
            return int(selected_event.get("guest_count"))
        except Exception:
            return None

    parts = text_lower.replace("guests", "people").replace("attendees", "people").split()
    for i, token in enumerate(parts[:-1]):
        if token.isdigit() and parts[i + 1] == "people":
            return int(token)
    return None


def _small_medium_large(guest_count):
    if not guest_count:
        return ""
    if guest_count <= 25:
        return "small"
    if guest_count <= 75:
        return "medium-sized"
    return "larger"


def _budget_reply(text_lower, selected_event=None):
    estimate = estimate_budget(selected_event or {})
    guest_count = _guest_count(selected_event, text_lower) or estimate.get("attendance") or 50
    venue_known = bool(selected_event and selected_event.get("location"))
    free_venue_hint = any(p in text_lower for p in ["free venue", "not renting", "my house", "at home", "classroom", "school building", "free location"])

    if free_venue_hint:
        estimate["venue"] = 0

    size_text = _small_medium_large(guest_count)
    opener = f"For a {size_text} event" if size_text else "For an event like this"
    if selected_event and selected_event.get("title"):
        opener = f"For '{selected_event['title']}'"

    lines = [
        f"{opener}, I would split the budget into venue, food, and flexible extras like supplies, decor, and contingency.",
    ]

    if free_venue_hint:
        lines.append("Since the venue sounds free, you can shift more of the budget into food, guest experience, or a small backup buffer.")
    elif venue_known:
        lines.append("Your venue cost matters a lot because location and food are usually the two biggest drivers of total cost.")
    else:
        lines.append("The first thing I would lock in is whether the venue is free or paid, because that changes the rest of the budget quickly.")

    lines.append(
        f"A rough starting point for about {guest_count} people is venue around ${estimate['venue']:.0f}, food around ${estimate['food']:.0f}, and about ${estimate['misc']:.0f} for misc costs, for a total near ${estimate['total']:.0f}."
    )

    if any(p in text_lower for p in ["cheap", "cut costs", "save money", "low budget", "affordable", "not too expensive"]):
        lines.append("The easiest ways to cut costs are using a free or low-cost location, simplifying the food format, and keeping decorations or extras minimal.")

    lines.append("Do you want me to make this more conservative, more polished, or as low-cost as possible?")
    return " ".join(lines)


def _timeline_reply(text_lower, selected_event=None):
    guest_count = _guest_count(selected_event, text_lower)
    size_text = _small_medium_large(guest_count)

    lines = [
        "A good event timeline usually moves from core decisions into bookings, then confirmations, then event-day setup and follow-up.",
    ]

    if guest_count:
        lines.append(f"Since this looks like a {size_text} event for about {guest_count} people, I would avoid leaving food, space, and final headcount until the last few days.")

    if "week before" in text_lower:
        lines.append("A week before the event, focus on final headcount, vendor confirmations, supplies, and a simple event-day checklist.")
    elif "event day" in text_lower:
        lines.append("On event day, the essentials are setup items, contact info for any vendors, signage or materials, and a short run-of-show so nothing gets missed.")
    else:
        lines.append("A simple structure is: finalize basics, book venue and food, confirm attendance and materials, then handle setup, execution, and follow-up.")

    lines.append("When is the event happening? I can turn this into a shorter countdown if you already have a date.")
    return " ".join(lines)


def _creation_reply(text_lower, selected_event=None):
    guest_count = _guest_count(selected_event, text_lower)
    size_text = _small_medium_large(guest_count)
    lines = ["The best place to start is with the core details: purpose, guest count, date, location, and spending limit."]

    if guest_count:
        lines.append(f"Because this sounds like a {size_text} event for about {guest_count} people, I would focus first on the date and location, then food and a short checklist.")
    else:
        lines.append("Once those basics are set, the rest becomes much easier to break into venue, food, tasks, promotion, and day-of logistics.")

    if any(p in text_lower for p in ["small", "simple", "nothing crazy", "low effort"]):
        lines.append("If you want to keep it simple, aim for a manageable guest count, an easy location, and food that does not require complicated setup.")

    lines.append("What kind of event are you trying to host?")
    return " ".join(lines)


def _task_reply(text_lower, context, selected_event=None):
    tasks = context.get("tasks", [])
    events = context.get("events", [])
    event_tasks = _event_tasks(selected_event, tasks)
    pending = _pending_tasks(event_tasks if selected_event else tasks)

    if selected_event:
        if pending:
            task_list = ", ".join(task.get("title", "task") for task in pending[:3])
            return (
                f"For '{selected_event['title']}', the next tasks I would prioritize are {task_list}. "
                f"You still have {len(pending)} incomplete task(s) tied to this event. "
                "Do you want a simple first-second-third order for them?"
            )
        return (
            f"'{selected_event['title']}' does not have any open tasks right now. "
            "A good next step would be reviewing event-day logistics, confirmations, and anything easy to overlook. "
            "Do you want me to suggest a checklist?"
        )

    if any(p in text_lower for p in ["checklist", "not forget", "event day", "week before", "first second third"]):
        return (
            "A solid checklist usually includes venue or location confirmation, food, guest communication, supplies, setup, and a short event-day plan. "
            "If you already have an event picked out, I can turn that into a more specific checklist for you."
        )

    if pending:
        task_list = ", ".join(task.get("title", "task") for task in pending[:3])
        return (
            f"Across all events, you currently have {len(pending)} pending task(s). The next few worth handling are {task_list}. "
            "Do you want me to narrow that down to one event?"
        )

    if events:
        return "You do not have open tasks right now, but I can help build a checklist for one of your events. Which event do you want to focus on?"

    return "You do not have tasks yet, but I can help build a starter checklist. What type of event are you planning?"


def _event_help_reply(text_lower, context, selected_event=None):
    if any(p in text_lower for p in ["venue", "location"]):
        venues = get_venues()[:3]
        venue_names = ", ".join(v.get("name", "Venue") for v in venues) if venues else "a few venue options"
        return (
            "A good location should fit your guest count, budget, accessibility needs, and the atmosphere you want. "
            f"A few options from your data are {venue_names}. "
            "Do you want me to focus more on affordability, capacity, or overall feel?"
        )

    if any(p in text_lower for p in ["food", "catering"]):
        caterers = get_catering()[:3]
        if selected_event and selected_event.get("title"):
            prefix = f"For '{selected_event['title']}', "
        else:
            prefix = "For an event like this, "
        if caterers:
            options = "; ".join(
                f"{c.get('name')} ({c.get('type')}, ${c.get('cost_per_person')}/person)" for c in caterers
            )
            return (
                prefix
                + "food decisions usually come down to guest count, serving style, and how much you want to spend per person. "
                + f"Some good options are {options}. "
                + "Do you want the food to feel inexpensive, polished, or somewhere in the middle?"
            )
        return prefix + "food choices usually come down to buffet, trays, boxed meals, or plated service. What feel are you going for?"

    if any(p in text_lower for p in ["timeline", "schedule", "week before", "event day"]):
        return _timeline_reply(text_lower, selected_event)

    return (
        "A good event plan usually covers the basics first, then venue, food, tasks, and day-of logistics. "
        "If you tell me the event type and rough size, I can make the advice much more specific."
    )


def _summary_reply(context, selected_event=None):
    events = context.get("events", [])
    tasks = context.get("tasks", [])
    if selected_event:
        event_tasks = _event_tasks(selected_event, tasks)
        pending = _pending_tasks(event_tasks)
        return (
            f"Here is the current picture for '{selected_event['title']}'. It is scheduled for {selected_event.get('date', 'not set')}. "
            f"The location is {selected_event.get('location', 'not set')}. You are planning for about {selected_event.get('guest_count', 'unknown')} guests. "
            f"There are {len(event_tasks)} task(s) tied to it, with {len(pending)} still open. "
            "Do you want a budget summary or the next recommended actions?"
        )

    pending = _pending_tasks(tasks)
    if events:
        next_event = events[0]
        return (
            f"You currently have {len(events)} event(s) and {len(pending)} open task(s). "
            f"The next event in your list is '{next_event.get('title', 'Untitled Event')}'. "
            "Do you want a summary of that event or help deciding what to work on next?"
        )

    return "You do not have events yet. If you want, I can help you sketch out a new one from scratch."


def _unclear_reply(context):
    if context.get("events"):
        return (
            "I can help with planning, budgeting, food, venues, tasks, or a summary of one of your events. "
            "What part are you thinking through right now?"
        )
    return (
        "I can help you figure out the first steps, budget, venue, food, or checklist for an event. "
        "What kind of event are you trying to plan?"
    )


def get_response(intent, text, context=None, selected_event=None, confidence=None):
    text_lower = _normalize(text)
    context = context or {"events": [], "tasks": []}

    if intent == "greeting":
        if selected_event:
            return (
                f"Hi — I can help you think through '{selected_event['title']}' from a few angles like budget, timeline, food, or tasks. "
                "What do you want to work on first?"
            )
        return (
            "Hi — I can help with event planning, budgeting, venues, catering, timelines, and task planning. "
            "What part do you want to work through first?"
        )

    if intent == "budgeting":
        return _budget_reply(text_lower, selected_event)
    if intent == "timeline_help":
        return _timeline_reply(text_lower, selected_event)
    if intent == "event_creation":
        return _creation_reply(text_lower, selected_event)
    if intent == "task_help":
        return _task_reply(text_lower, context, selected_event)
    if intent == "event_summary":
        return _summary_reply(context, selected_event)
    if intent == "event_help":
        return _event_help_reply(text_lower, context, selected_event)
    if intent == "unclear":
        return _unclear_reply(context)

    return _unclear_reply(context)
