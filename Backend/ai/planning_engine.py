from .local_data import venues, catering


def get_venues(location=None, max_budget=None):
    results = venues

    if location:
        results = [v for v in results if v["location"].lower() == location.lower()]

    if max_budget:
        results = [v for v in results if v["cost"] <= max_budget]

    return results


def get_catering(max_budget=None):
    results = catering

    if max_budget:
        results = [c for c in results if c["cost_per_person"] <= max_budget]

    return results


def estimate_budget(event):
    attendance = 50  # default (can improve later)

    venue_cost = 300
    food_cost = attendance * 10
    misc = 200

    return {
        "attendance": attendance,
        "venue": venue_cost,
        "food": food_cost,
        "misc": misc,
        "total": venue_cost + food_cost + misc
    }