def get_response(intent, text):
    text_lower = text.lower()

    if intent == "greeting":
        return (
            "Hey! I can help you plan events, estimate budgets, think through venues, "
            "build timelines, and organize tasks. Tell me what kind of event you're working on."
        )

    if intent == "event_creation":
        return (
            "A good place to start is with five basics: event goal, audience, date, "
            "location, and budget. Once you have those, I can help break the event into next steps."
        )

    if intent == "event_help":
        if "venue" in text_lower or "location" in text_lower:
            return (
                "When choosing a venue, think about guest count, cost, parking, accessibility, "
                "availability, and whether the space fits the tone of the event."
            )

        if "timeline" in text_lower or "schedule" in text_lower:
            return (
                "A simple event timeline usually includes: planning, booking, promotion, "
                "final confirmations, event-day setup, and post-event review."
            )

        if "food" in text_lower or "catering" in text_lower:
            return (
                "For catering, estimate guest count first, then decide whether you need meals, "
                "snacks, drinks, or just light refreshments. I can help you estimate that too."
            )

        return (
            "I can help with venues, food planning, timelines, supplies, and task organization. "
            "Tell me which part of the event you want to work on."
        )

    if intent == "budgeting":
        if "100" in text_lower or "200" in text_lower or "300" in text_lower:
            return (
                "For budgeting, break costs into categories like venue, food, decorations, "
                "equipment, staff, and promotion. Also leave extra room for unexpected costs."
            )

        return (
            "A strong event budget usually includes venue, food, decorations, equipment, labor, "
            "marketing, and a backup cushion. Give me your event type and expected attendance and "
            "I can help you think through it."
        )

    return (
        "I’m not fully sure what you mean yet, but I can help with event planning, budgeting, "
        "venues, catering, and timelines. Try telling me what event you're planning."
    )