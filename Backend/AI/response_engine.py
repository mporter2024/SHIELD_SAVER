def get_response(intent, text):
    text_lower = text.lower()

    # GREETING
    if intent == "greeting":
        return "Hey! I can help you plan events, manage tasks, and estimate costs."

    # EVENT CREATION
    if intent == "event_creation":
        return "Start by defining your goal, audience, budget, date, and location."

    # EVENT HELP (keyword enhanced)
    if intent == "event_help":
        if "venue" in text_lower:
            return "Choose a venue based on size, cost, and accessibility."
        if "timeline" in text_lower:
            return "Break your event into milestones: planning, booking, promotion, execution."
        return "I can help with venues, timelines, vendors, and more."

    # BUDGETING
    if intent == "budgeting":
        return "Estimate costs for venue, food, staff, and marketing. Always add a buffer."

    return "I'm not sure yet, but I can help with event planning if you give me more details."