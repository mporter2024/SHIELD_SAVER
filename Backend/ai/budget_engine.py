from __future__ import annotations

from typing import Any

from models.database import get_db


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _infer_event_style(event: dict[str, Any]) -> str:
    title = (event.get("title") or "").lower()
    description = (event.get("description") or "").lower()
    text = f"{title} {description}"

    if any(word in text for word in ["gala", "banquet", "formal", "awards"]):
        return "formal"
    if any(word in text for word in ["career", "summit", "showcase", "forum", "expo", "network", "conference"]):
        return "professional"
    if any(word in text for word in ["gaming", "student", "meetup", "social", "campus"]):
        return "casual"
    return "standard"


def _style_defaults(style: str) -> dict[str, float]:
    defaults = {
        "casual": {
            "food_cost_per_person": 10.0,
            "decorations_cost": 75.0,
            "equipment_cost": 100.0,
            "staff_cost": 80.0,
            "marketing_cost": 35.0,
            "misc_cost": 40.0,
            "contingency_percent": 8.0,
        },
        "professional": {
            "food_cost_per_person": 16.0,
            "decorations_cost": 140.0,
            "equipment_cost": 180.0,
            "staff_cost": 160.0,
            "marketing_cost": 90.0,
            "misc_cost": 60.0,
            "contingency_percent": 10.0,
        },
        "formal": {
            "food_cost_per_person": 24.0,
            "decorations_cost": 250.0,
            "equipment_cost": 220.0,
            "staff_cost": 250.0,
            "marketing_cost": 120.0,
            "misc_cost": 100.0,
            "contingency_percent": 12.0,
        },
        "standard": {
            "food_cost_per_person": 14.0,
            "decorations_cost": 120.0,
            "equipment_cost": 150.0,
            "staff_cost": 120.0,
            "marketing_cost": 60.0,
            "misc_cost": 50.0,
            "contingency_percent": 10.0,
        },
    }
    return defaults.get(style, defaults["standard"]).copy()


def _recommended_ranges(guest_count: int, style: str) -> dict[str, float]:
    base = {
        "casual": (8.0, 16.0),
        "professional": (12.0, 24.0),
        "formal": (20.0, 40.0),
        "standard": (10.0, 20.0),
    }
    low, high = base.get(style, base["standard"])
    if guest_count >= 150:
        high += 5.0
    elif guest_count <= 40:
        low = max(6.0, low - 2.0)
    return {"food_low": low, "food_high": high}


def _find_matching_venue(event: dict[str, Any]):
    db = get_db()
    location = (event.get("location") or "").strip()
    if not location:
        return None

    exact = db.execute(
        "SELECT * FROM venues WHERE lower(name) = lower(?) LIMIT 1",
        (location,),
    ).fetchone()
    if exact:
        return dict(exact)

    like = db.execute(
        "SELECT * FROM venues WHERE lower(name) LIKE lower(?) ORDER BY estimated_cost ASC LIMIT 1",
        (f"%{location}%",),
    ).fetchone()
    return dict(like) if like else None


def _find_best_venue_for_event(event: dict[str, Any]):
    db = get_db()
    guests = max(_to_int(event.get("guest_count"), 0), 1)
    row = db.execute(
        """
        SELECT * FROM venues
        WHERE capacity = 0 OR capacity >= ?
        ORDER BY CASE WHEN capacity >= ? THEN capacity ELSE 999999 END ASC,
                 estimated_cost ASC,
                 rating DESC
        LIMIT 1
        """,
        (guests, guests),
    ).fetchone()
    return dict(row) if row else None


def _find_best_caterer_for_event(event: dict[str, Any]):
    db = get_db()
    style = _infer_event_style(event)
    ranges = _recommended_ranges(_to_int(event.get("guest_count"), 0), style)

    row = db.execute(
        """
        SELECT * FROM caterers
        WHERE cost_per_person BETWEEN ? AND ?
        ORDER BY rating DESC, cost_per_person ASC
        LIMIT 1
        """,
        (ranges["food_low"], ranges["food_high"]),
    ).fetchone()
    if row:
        return dict(row)

    fallback = db.execute(
        "SELECT * FROM caterers ORDER BY rating DESC, cost_per_person ASC LIMIT 1"
    ).fetchone()
    return dict(fallback) if fallback else None


def calculate_budget_totals(event: dict[str, Any]) -> dict[str, Any]:
    guest_count = max(_to_int(event.get("guest_count"), 0), 0)
    venue_cost = _to_float(event.get("venue_cost"), 0.0)
    # Prefer the event-linked venue/catering estimates when present.
    venue_cost = max(venue_cost, _to_float(event.get("estimated_venue_cost"), 0.0))
    food_cost_per_person = _to_float(event.get("food_cost_per_person"), 0.0)
    decorations_cost = _to_float(event.get("decorations_cost"), 0.0)
    equipment_cost = _to_float(event.get("equipment_cost"), 0.0)
    staff_cost = _to_float(event.get("staff_cost"), 0.0)
    marketing_cost = _to_float(event.get("marketing_cost"), 0.0)
    misc_cost = _to_float(event.get("misc_cost"), 0.0)
    contingency_percent = _to_float(event.get("contingency_percent"), 0.0)

    food_total = guest_count * food_cost_per_person
    subtotal = venue_cost + food_total + decorations_cost + equipment_cost + staff_cost + marketing_cost + misc_cost
    contingency = subtotal * (contingency_percent / 100.0)
    total = subtotal + contingency
    cost_per_guest = _safe_div(total, guest_count)

    breakdown_amounts = {
        "venue": venue_cost,
        "food": food_total,
        "decorations": decorations_cost,
        "equipment": equipment_cost,
        "staff": staff_cost,
        "marketing": marketing_cost,
        "misc": misc_cost,
    }
    largest_category = max(breakdown_amounts, key=breakdown_amounts.get) if breakdown_amounts else "venue"
    breakdown_percentages = {
        key: round(_safe_div(value, subtotal) * 100.0, 1) if subtotal else 0.0
        for key, value in breakdown_amounts.items()
    }

    budget_limit = _to_float(event.get("budget_limit"), 0.0)
    remaining_budget = budget_limit - total if budget_limit > 0 else None

    return {
        "guest_count": guest_count,
        "venue_cost": round(venue_cost, 2),
        "food_cost_per_person": round(food_cost_per_person, 2),
        "food_total": round(food_total, 2),
        "decorations_cost": round(decorations_cost, 2),
        "equipment_cost": round(equipment_cost, 2),
        "staff_cost": round(staff_cost, 2),
        "marketing_cost": round(marketing_cost, 2),
        "misc_cost": round(misc_cost, 2),
        "contingency_percent": round(contingency_percent, 2),
        "subtotal": round(subtotal, 2),
        "contingency": round(contingency, 2),
        "total": round(total, 2),
        "cost_per_guest": round(cost_per_guest, 2),
        "largest_category": largest_category,
        "breakdown_percentages": breakdown_percentages,
        "budget_limit": round(budget_limit, 2),
        "remaining_budget": round(remaining_budget, 2) if remaining_budget is not None else None,
        "over_budget_by": round(abs(remaining_budget), 2) if remaining_budget is not None and remaining_budget < 0 else 0,
    }


def _fit_estimate_to_limit(estimate: dict[str, Any], budget_limit: float) -> dict[str, Any]:
    """Trim generated/default costs so Generate Budget respects max spending power."""
    if budget_limit <= 0:
        return estimate

    working = dict(estimate)
    guest_count = max(_to_int(working.get("guest_count"), 0), 1)

    def total() -> float:
        return calculate_budget_totals(working)["total"]

    if total() <= budget_limit:
        return working

    # Keep selected venue/catering if possible, but make the rest lean.
    if not working.get("selected_venue") and _to_float(working.get("estimated_venue_cost"), 0) <= 0:
        # Custom classroom/student-center style locations are often free in this project.
        if (working.get("location") or "").strip():
            working["venue_cost"] = 0.0
            working["estimated_venue_cost"] = 0.0

    lean = {
        "decorations_cost": 25.0 if guest_count <= 50 else 50.0,
        "equipment_cost": 35.0 if guest_count <= 50 else 75.0,
        "staff_cost": 0.0 if guest_count <= 50 else 50.0,
        "marketing_cost": 10.0 if guest_count <= 50 else 25.0,
        "misc_cost": 20.0 if guest_count <= 50 else 40.0,
        "contingency_percent": 5.0,
    }
    working.update(lean)
    if total() <= budget_limit:
        return working

    # Bare minimum if the limit is tight.
    working.update({
        "decorations_cost": 0.0,
        "equipment_cost": 0.0,
        "staff_cost": 0.0,
        "marketing_cost": 0.0,
        "misc_cost": 0.0,
        "contingency_percent": 0.0,
    })
    if total() <= budget_limit:
        return working

    # Only lower catering if it was generated/defaulted. Do not silently replace a named caterer.
    if not working.get("selected_catering"):
        venue = max(_to_float(working.get("venue_cost"), 0), _to_float(working.get("estimated_venue_cost"), 0))
        affordable_food_pp = max((budget_limit - venue) / guest_count, 0.0)
        working["food_cost_per_person"] = round(affordable_food_pp, 2)
        working["estimated_catering_cost"] = round(affordable_food_pp * guest_count, 2)

    return working


def generate_budget_estimate(event: dict[str, Any]) -> dict[str, Any]:
    style = _infer_event_style(event)
    defaults = _style_defaults(style)
    guest_count = max(_to_int(event.get("guest_count"), 0), 25)

    estimate = dict(event)
    estimate["guest_count"] = guest_count

    matching_venue = _find_matching_venue(event)
    recommended_venue = matching_venue or _find_best_venue_for_event({**event, "guest_count": guest_count})
    recommended_caterer = _find_best_caterer_for_event({**event, "guest_count": guest_count})

    location = (estimate.get("location") or "").strip()
    venue_context = {
        "source": "database" if matching_venue else "default",
        "assumption": None,
        "message": "",
    }

    if _to_float(estimate.get("venue_cost"), 0.0) <= 0:
        if matching_venue:
            estimate["venue_cost"] = _to_float(matching_venue.get("estimated_cost"), 0.0)
            venue_context.update({
                "source": "database",
                "message": f"Matched venue database entry: {matching_venue.get('name', location)}.",
            })
        elif location:
            estimate["venue_cost"] = 0.0
            venue_context.update({
                "source": "custom_location",
                "assumption": "assumed_free",
                "message": "This location is not in the venue database, so the venue cost was assumed to be $0. Update it manually if the space has a rental fee.",
            })
        elif recommended_venue:
            estimate["venue_cost"] = _to_float(recommended_venue.get("estimated_cost"), 0.0)
            venue_context.update({
                "source": "recommendation",
                "message": f"No venue was selected, so a typical venue estimate was used based on event size: {recommended_venue.get('name', 'Recommended venue') }.",
            })

    if _to_float(estimate.get("food_cost_per_person"), 0.0) <= 0:
        if recommended_caterer and _to_float(recommended_caterer.get("cost_per_person"), 0.0) > 0:
            estimate["food_cost_per_person"] = _to_float(recommended_caterer.get("cost_per_person"))
        else:
            estimate["food_cost_per_person"] = defaults["food_cost_per_person"]

    scaled = 1.0
    if guest_count >= 150:
        scaled = 1.6
    elif guest_count >= 80:
        scaled = 1.25
    elif guest_count <= 35:
        scaled = 0.85

    for key in ["decorations_cost", "equipment_cost", "staff_cost", "marketing_cost", "misc_cost"]:
        if _to_float(estimate.get(key), 0.0) <= 0:
            estimate[key] = round(defaults[key] * scaled, 2)

    if _to_float(estimate.get("contingency_percent"), 0.0) <= 0:
        estimate["contingency_percent"] = defaults["contingency_percent"]

    # If the user set a max spending limit, Generate Budget should work around it
    # instead of generating a plan that immediately exceeds it.
    estimate = _fit_estimate_to_limit(estimate, _to_float(estimate.get("budget_limit"), 0.0))

    totals = calculate_budget_totals(estimate)
    estimate.update({
        "budget_subtotal": totals["subtotal"],
        "budget_contingency": totals["contingency"],
        "budget_total": totals["total"],
    })

    return {
        "event": estimate,
        "totals": totals,
        "recommended_venue": recommended_venue,
        "recommended_caterer": recommended_caterer,
        "style": style,
        "venue_context": venue_context,
    }


def analyze_budget(event: dict[str, Any]) -> dict[str, Any]:
    style = _infer_event_style(event)
    totals = calculate_budget_totals(event)
    ranges = _recommended_ranges(totals["guest_count"], style)
    warnings: list[str] = []
    suggestions: list[str] = []
    location = (event.get("location") or "").strip()
    matching_venue = _find_matching_venue(event)

    if totals["guest_count"] <= 0:
        warnings.append("Guest count is zero, so food and per-person estimates may be misleading.")
        suggestions.append("Add an expected guest count to make the budget smarter.")

    if location and not matching_venue and totals["venue_cost"] <= 0:
        warnings.append("This location is not in the venue database, so venue cost is currently assumed to be free.")
        suggestions.append("If this location has a fee, enter a manual venue cost to make the total more realistic.")

    if totals["contingency_percent"] <= 0:
        warnings.append("No contingency has been added for surprise costs.")
        suggestions.append("Add a contingency of about 8% to 12% to protect the budget.")

    if totals["breakdown_percentages"]["food"] > 55:
        warnings.append("Catering is taking up a large share of the total budget.")
        savings = max(totals["guest_count"], 1) * 3
        suggestions.append(f"Reducing food cost by $3 per guest would save about ${savings:.2f}.")

    if totals["breakdown_percentages"]["venue"] > 45:
        warnings.append("Venue cost is high relative to the overall event budget.")
        suggestions.append("Consider a lower-cost venue or moving more spending into food, staff, or attendee experience.")

    if 0 < totals["food_cost_per_person"] < ranges["food_low"]:
        warnings.append("Food cost per person is lower than expected for this event style, so confirm that catering is realistic.")
    elif totals["food_cost_per_person"] > ranges["food_high"]:
        warnings.append("Food cost per person is on the high end for this event style.")
        suggestions.append("Switching to a simpler catering tier could lower the total without changing guest count.")

    if totals["guest_count"] >= 75 and totals["staff_cost"] <= 0:
        warnings.append("Larger events usually need at least some staffing or volunteer support budget.")
        suggestions.append("Add staff or volunteer coordination costs so the budget reflects event operations more accurately.")

    zero_optional = [
        name for name, amount in [
            ("decorations", totals["decorations_cost"]),
            ("equipment", totals["equipment_cost"]),
            ("marketing", totals["marketing_cost"]),
            ("miscellaneous", totals["misc_cost"]),
        ] if amount <= 0
    ]
    if len(zero_optional) >= 3:
        warnings.append("Several optional categories are still zero, which may mean the budget is incomplete.")
        suggestions.append("Review decorations, equipment, marketing, and miscellaneous costs before finalizing the plan.")

    if totals["cost_per_guest"] >= 40:
        warnings.append("Cost per guest is high for a typical campus event.")
        suggestions.append("Lowering venue or catering costs will usually have the biggest effect on cost per guest.")
    elif 0 < totals["cost_per_guest"] <= 8:
        warnings.append("Cost per guest is very low, so double-check that all major categories are included.")

    budget_limit = totals.get("budget_limit", 0) or 0
    remaining_budget = totals.get("remaining_budget")
    over_budget_by = totals.get("over_budget_by", 0) or 0

    if budget_limit > 0:
        used_ratio = _safe_div(totals["total"], budget_limit)
        if over_budget_by > 0:
            warnings.insert(0, f"This plan is ${over_budget_by:.2f} over the user's maximum spending limit.")
            suggestions.insert(0, "Reduce venue, catering, or optional costs before adding more expenses.")
            score = max(0, int(70 - (_safe_div(over_budget_by, budget_limit) * 100)))
        else:
            # Budget fit is intentionally not just "money left percent." A plan can be healthy
            # while using most of the budget, but it becomes tighter as the remaining cushion shrinks.
            score = max(0, min(100, int(100 - (used_ratio * 25))))
            if remaining_budget is not None:
                suggestions.insert(0, f"You have about ${remaining_budget:.2f} left before reaching the spending limit.")
            if used_ratio >= 0.9:
                warnings.insert(0, "This event is within budget, but there is very little room left for changes.")
            elif used_ratio <= 0.65:
                suggestions.insert(0, "This event has strong budget flexibility. You can keep the savings or improve food, venue, or supplies.")

        if over_budget_by > 0:
            label = "Over Limit"
        elif used_ratio >= 0.9:
            label = "Tight"
        elif used_ratio >= 0.75:
            label = "Manageable"
        else:
            label = "Comfortable"
    else:
        score = 100
        score -= 18 if totals["contingency_percent"] <= 0 else 0
        score -= 15 if totals["breakdown_percentages"]["food"] > 55 else 0
        score -= 12 if totals["breakdown_percentages"]["venue"] > 45 else 0
        score -= 10 if len(zero_optional) >= 3 else 0
        score -= 10 if totals["cost_per_guest"] >= 40 else 0
        score -= 8 if totals["guest_count"] >= 75 and totals["staff_cost"] <= 0 else 0
        score = max(0, min(100, score))

        if score >= 85:
            label = "Healthy"
        elif score >= 65:
            label = "Watch"
        elif score >= 45:
            label = "Over Budget Risk"
        else:
            label = "High Risk"

        suggestions.insert(0, "Set a maximum spending limit so I can judge whether the plan actually fits what you can spend.")

    if not suggestions:
        suggestions.append("This budget looks balanced. Save it and revisit after venue or catering changes.")

    return {
        "summary": totals,
        "health": {
            "score": score,
            "label": label,
            "style": style,
            "budget_limit": budget_limit,
            "remaining_budget": remaining_budget,
            "over_budget_by": over_budget_by,
        },
        "warnings": warnings,
        "suggestions": suggestions,
    }
