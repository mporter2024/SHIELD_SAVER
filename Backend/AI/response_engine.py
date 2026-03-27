from .planning_engine import get_venues, get_catering, estimate_budget


def get_event_tasks(selected_event, all_tasks):
    if not selected_event:
        return []

    event_id = selected_event.get("id")
    return [
        task for task in all_tasks
        if int(task.get("event_id", 0)) == int(event_id)
    ]


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
        if len(events) > 1:
            return (
                "I’m not fully sure what you want yet. You can ask about budget, venue, timeline, "
                "tasks, or summarize one of your events by name."
            )
        return (
            "I’m not fully sure what you want yet. You can ask me about event planning, budgeting, "
            "venue selection, timelines, or tasks."
        )

    if "venue" in text_lower and ("suggest" in text_lower or "find" in text_lower):
        venue_list = get_venues()

        formatted = "\n\n".join(
            f"{v['name']} ({v['type']})\n"
            f"Capacity: {v['capacity']}\n"
            f"Estimated Cost: ${v['cost']}\n"
            f"{v['description']}"
            for v in venue_list
        )

        return f"Here are some venue options in Norfolk:\n\n{formatted}"

    if "catering" in text_lower or "food" in text_lower:
        options = get_catering()

        formatted = "\n".join(
            f"- {c['name']} ({c['type']}, ${c['cost_per_person']} per person)"
            for c in options
        )

        return f"Here are some catering options:\n{formatted}"

    if "budget" in text_lower or "estimate" in text_lower:
        result = estimate_budget(selected_event)

        return (
            f"Estimated budget:\n"
            f"- Venue: ${result['venue']}\n"
            f"- Food: ${result['food']}\n"
            f"- Misc: ${result['misc']}\n"
            f"Total: ${result['total']}"
        )

    if intent == "greeting":
        if selected_event:
            return (
                f"Hey! I can help with '{selected_event['title']}'. "
                f"It has {len(event_tasks)} task(s), with {len(pending_event_tasks)} still pending."
            )

        if events:
            return (
                f"Hey! You currently have {total_events} event(s) and {pending_tasks} pending task(s). "
                f"Ask me what you should work on next."
            )

        return "Hey! I can help you plan events, organize tasks, and estimate costs."

    if intent == "event_creation":
        return (
            "Start with five basics: event goal, audience, date, location, and budget. "
            "Then break the work into tasks like venue, food, promotion, and setup."
        )

    if intent == "event_summary":
        if not events:
            return "You do not have any events yet. Create one first and I can summarize it."

        if selected_event:
            return (
                f"Summary for '{selected_event['title']}': "
                f"date: {selected_event.get('date', 'not set')}, "
                f"location: {selected_event.get('location', 'not set')}, "
                f"{len(event_tasks)} total task(s), and {len(pending_event_tasks)} still incomplete."
            )

        next_event = events[0]
        return (
            f"You currently have {total_events} event(s), {total_tasks} total task(s), and "
            f"{pending_tasks} pending task(s). Your next event appears to be "
            f"'{next_event.get('title', 'Untitled Event')}'."
        )

    if intent == "task_help":
        if selected_event:
            if pending_event_tasks:
                next_tasks = pending_event_tasks[:3]
                task_list = ", ".join(task["title"] for task in next_tasks)
                return (
                    f"For '{selected_event['title']}', your next tasks are: {task_list}. "
                    f"You still have {len(pending_event_tasks)} incomplete task(s)."
                )

            return (
                f"'{selected_event['title']}' has no pending tasks right now. "
                f"A smart next step would be reviewing event-day logistics and confirmations."
            )

        if pending_tasks:
            next_tasks = [task for task in tasks if int(task.get("completed", 0)) == 0][:3]
            task_list = ", ".join(task["title"] for task in next_tasks) if next_tasks else "your pending tasks"
            return (
                f"You currently have {pending_tasks} pending task(s). "
                f"Some next ones to handle are: {task_list}."
            )

        return "You do not have any tasks yet. Add a few tasks and I can help prioritize them."

    if intent == "event_help":
        if "venue" in text_lower or "location" in text_lower:
            if selected_event:
                return (
                    f"For '{selected_event['title']}', choose a venue based on guest count, cost, "
                    f"parking, accessibility, and overall event style."
                )
            return "Choose a venue based on size, cost, accessibility, and location."

        if "timeline" in text_lower or "schedule" in text_lower:
            if selected_event:
                return (
                    f"For '{selected_event['title']}', build a timeline with planning, booking, "
                    f"promotion, confirmations, setup, and post-event follow-up."
                )
            return "Break your event into milestones: planning, booking, promotion, execution, and follow-up."

        return "I can help with venues, timelines, logistics, catering, vendors, and more."

    if intent == "budgeting":
        if selected_event:
            return (
                f"For '{selected_event['title']}', budget by category: venue, food, supplies, equipment, "
                f"marketing, and an emergency buffer."
            )
        return "Estimate costs for venue, food, staff, supplies, and marketing. Always add a backup buffer."

    return "I’m not sure yet, but I can help with event planning if you give me more details."