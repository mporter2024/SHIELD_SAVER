def get_event_tasks(selected_event, all_tasks):
    if not selected_event:
        return []

    event_id = selected_event.get("id")
    return [task for task in all_tasks if int(task.get("event_id", 0)) == int(event_id)]


def get_response(intent, text, context=None, selected_event=None):
    text_lower = text.lower()
    context = context or {"events": [], "tasks": []}

    events = context.get("events", [])
    tasks = context.get("tasks", [])

    total_events = len(events)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if int(task.get("completed", 0)) == 1)
    pending_tasks = total_tasks - completed_tasks

    event_tasks = get_event_tasks(selected_event, tasks)
    pending_event_tasks = [t for t in event_tasks if int(t.get("completed", 0)) == 0]

    if intent == "greeting":
        if selected_event:
            return (
                f"Hey! I can help you plan '{selected_event['title']}'. "
                f"It currently has {len(event_tasks)} task(s), with {len(pending_event_tasks)} still pending. "
                f"Ask me about the budget, venue, timeline, or what to do next."
            )

        if events:
            return (
                f"Hey! You currently have {total_events} event(s) and {pending_tasks} pending task(s). "
                f"Ask me about one of your events, or ask what you should work on next."
            )

        return (
            "Hey! I can help you plan events, estimate budgets, build timelines, and organize tasks. "
            "Create an event first, or tell me what kind of event you're planning."
        )

    if intent == "event_summary":
        if not events:
            return "You do not have any events yet. Start by creating one with a title, date, location, and description."

        if selected_event:
            return (
                f"Here is a quick summary for '{selected_event['title']}': "
                f"date: {selected_event.get('date', 'not set')}, "
                f"location: {selected_event.get('location', 'not set')}, "
                f"{len(event_tasks)} task(s) total, and {len(pending_event_tasks)} still incomplete."
            )

        next_event = events[0]
        return (
            f"You currently have {total_events} event(s), {total_tasks} total task(s), "
            f"and {pending_tasks} pending task(s). Your next event appears to be "
            f"'{next_event.get('title', 'Untitled Event')}' on {next_event.get('date', 'no date set')}."
        )

    if intent == "task_help":
        if selected_event:
            if pending_event_tasks:
                next_three = pending_event_tasks[:3]
                task_list = ", ".join(task["title"] for task in next_three)
                return (
                    f"For '{selected_event['title']}', your best next step is to work on: {task_list}. "
                    f"You still have {len(pending_event_tasks)} incomplete task(s) for this event."
                )

            return (
                f"'{selected_event['title']}' does not have any pending tasks right now. "
                f"A smart next move would be reviewing venue details, guest communication, and day-of logistics."
            )

        if pending_tasks:
            next_three = [task for task in tasks if int(task.get("completed", 0)) == 0][:3]
            task_list = ", ".join(task["title"] for task in next_three) if next_three else "your pending tasks"
            return (
                f"You currently have {pending_tasks} pending task(s). "
                f"Some of the next ones to handle are: {task_list}."
            )

        return "You do not have any tasks yet. Once you add tasks to an event, I can help you decide what to do next."

    if intent == "event_creation":
        if "school" in text_lower:
            return "For a school event, start with the event goal, expected attendance, date, location, required approvals, and budget."

        return (
            "A strong event plan starts with five basics: goal, audience, date, location, and budget. "
            "After that, break it into tasks like venue, promotion, supplies, food, and day-of setup."
        )

    if intent == "event_help":
        if "venue" in text_lower or "location" in text_lower:
            if selected_event:
                return (
                    f"For '{selected_event['title']}', make sure the venue matches your guest count, budget, "
                    f"parking needs, accessibility needs, and event style."
                )
            return (
                "When choosing a venue, think about guest count, cost, parking, accessibility, availability, "
                "and whether the space fits the tone of the event."
            )

        if "timeline" in text_lower or "schedule" in text_lower:
            if selected_event:
                return (
                    f"A simple timeline for '{selected_event['title']}' should include booking, promotion, "
                    f"final confirmations, setup, event-day execution, and post-event review."
                )
            return (
                "A simple event timeline usually includes planning, booking, promotion, final confirmations, "
                "event-day setup, and post-event review."
            )

        if "food" in text_lower or "catering" in text_lower:
            return (
                "For catering, estimate guest count first, then decide whether you need meals, snacks, drinks, "
                "or light refreshments. Also account for dietary restrictions and serving supplies."
            )

        return (
            "I can help with venues, food planning, timelines, supplies, and task organization. "
            "Tell me which part of the event you want help with."
        )

    if intent == "budgeting":
        if selected_event:
            return (
                f"For '{selected_event['title']}', build your budget in categories: venue, food, decorations, "
                f"equipment, labor, marketing, and emergency cushion."
            )

        return (
            "A strong event budget usually includes venue, food, decorations, equipment, labor, marketing, "
            "and a backup cushion. Tell me your event type and expected attendance, and I can help you break it down."
        )

    if events:
        return (
            f"I’m not fully sure what you mean yet, but you currently have {total_events} event(s) in the system. "
            f"Ask me about an event’s budget, venue, tasks, timeline, or next steps."
        )

    return "I’m not fully sure what you mean yet, but I can help with event planning, budgeting, venues, catering, timelines, and tasks."