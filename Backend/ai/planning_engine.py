from models.database import get_db


def _normalize_text(value):
    return str(value or '').strip().lower()


def _normalize_price_tier(value):
    if not value:
        return None
    value = _normalize_text(value)
    aliases = {
        'cheap': 'budget',
        'low': 'budget',
        'affordable': 'budget',
        '$': 'budget',
        'moderate': 'mid',
        'medium': 'mid',
        '$$': 'mid',
        'premium': 'premium',
        'upscale': 'premium',
        'high': 'premium',
        'luxury': 'premium',
        '$$$': 'premium',
        '$$$$': 'premium',
    }
    return aliases.get(value, value)


def _build_like_clause(value):
    return f"%{str(value).strip().lower()}%"


def _coerce_boolish(value):
    if value in (None, '', []):
        return None
    if isinstance(value, bool):
        return value
    lowered = _normalize_text(value)
    if lowered in {'yes', 'true', '1'}:
        return True
    if lowered in {'no', 'false', '0'}:
        return False
    return None


def get_venues(location=None, max_budget=None, min_capacity=None, price_tier=None, indoor_outdoor=None, venue_type=None, style=None):
    db = get_db()
    query = """
        SELECT
            id,
            name,
            city AS location,
            city,
            capacity,
            estimated_cost AS cost,
            estimated_cost,
            venue_type AS type,
            venue_type,
            price_tier,
            indoor_outdoor,
            style,
            parking,
            accessibility,
            rating,
            phone,
            website,
            description
        FROM venues
        WHERE 1=1
    """
    params = []

    if location:
        query += ' AND LOWER(city) LIKE ?'
        params.append(_build_like_clause(location))

    if max_budget is not None:
        query += ' AND estimated_cost <= ?'
        params.append(max_budget)

    if min_capacity is not None:
        query += ' AND capacity >= ?'
        params.append(min_capacity)

    normalized_tier = _normalize_price_tier(price_tier)
    if normalized_tier:
        query += " AND LOWER(COALESCE(price_tier, '')) = ?"
        params.append(normalized_tier)

    if indoor_outdoor:
        query += " AND LOWER(COALESCE(indoor_outdoor, '')) LIKE ?"
        params.append(_build_like_clause(indoor_outdoor))

    if venue_type:
        query += " AND LOWER(COALESCE(venue_type, '')) LIKE ?"
        params.append(_build_like_clause(venue_type))

    if style:
        query += " AND LOWER(COALESCE(style, '')) LIKE ?"
        params.append(_build_like_clause(style))

    query += ' ORDER BY rating DESC, capacity ASC, estimated_cost ASC, name ASC'
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_catering(location=None, max_budget=None, cuisine=None, price_tier=None, service_type=None, dietary_need=None):
    db = get_db()
    query = """
        SELECT
            id,
            name,
            city,
            city AS location,
            cuisine,
            service_type AS type,
            service_type,
            price_tier,
            cost_per_person,
            dietary_options,
            rating,
            phone,
            website,
            description
        FROM caterers
        WHERE 1=1
    """
    params = []

    if location:
        query += ' AND LOWER(city) LIKE ?'
        params.append(_build_like_clause(location))

    if max_budget is not None:
        query += ' AND cost_per_person <= ?'
        params.append(max_budget)

    if cuisine:
        query += " AND LOWER(COALESCE(cuisine, '')) LIKE ?"
        params.append(_build_like_clause(cuisine))

    normalized_tier = _normalize_price_tier(price_tier)
    if normalized_tier:
        query += " AND LOWER(COALESCE(price_tier, '')) = ?"
        params.append(normalized_tier)

    if service_type:
        query += " AND LOWER(COALESCE(service_type, '')) LIKE ?"
        params.append(_build_like_clause(service_type))

    if dietary_need:
        if isinstance(dietary_need, (list, tuple, set)):
            pieces = [d for d in dietary_need if d]
            if pieces:
                query += ' AND (' + ' OR '.join(["LOWER(COALESCE(dietary_options, '')) LIKE ?"] * len(pieces)) + ')'
                params.extend(_build_like_clause(d) for d in pieces)
        else:
            query += " AND LOWER(COALESCE(dietary_options, '')) LIKE ?"
            params.append(_build_like_clause(dietary_need))

    query += ' ORDER BY rating DESC, cost_per_person ASC, name ASC'
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def search_venues(preferences=None, limit=5):
    preferences = preferences or {}
    rows = get_venues(
        location=preferences.get('location_area'),
        max_budget=preferences.get('max_budget_total'),
        min_capacity=preferences.get('guest_count'),
        price_tier=preferences.get('budget_level'),
        indoor_outdoor=preferences.get('indoor_outdoor'),
        venue_type=preferences.get('venue_type'),
        style=preferences.get('style'),
    )

    if not rows and preferences.get('location_area'):
        rows = get_venues(
            max_budget=preferences.get('max_budget_total'),
            min_capacity=preferences.get('guest_count'),
            price_tier=preferences.get('budget_level'),
            indoor_outdoor=preferences.get('indoor_outdoor'),
            venue_type=preferences.get('venue_type'),
            style=preferences.get('style'),
        )

    results = []
    requested_tier = _normalize_price_tier(preferences.get('budget_level'))
    requested_style = _normalize_text(preferences.get('style'))
    requested_type = _normalize_text(preferences.get('venue_type'))
    requested_io = _normalize_text(preferences.get('indoor_outdoor'))
    guest_count = preferences.get('guest_count')
    needs_parking = _coerce_boolish(preferences.get('parking'))
    needs_accessibility = _coerce_boolish(preferences.get('accessibility'))

    for row in rows:
        score = 0
        reasons = []
        row_io = _normalize_text(row.get('indoor_outdoor'))
        row_tier = _normalize_price_tier(row.get('price_tier'))
        row_type = _normalize_text(row.get('venue_type') or row.get('type'))
        row_style = _normalize_text(row.get('style'))
        row_capacity = int(row.get('capacity') or 0)
        row_cost = float(row.get('estimated_cost') or row.get('cost') or 0)
        rating = float(row.get('rating') or 0)

        if guest_count and row_capacity >= guest_count:
            score += 4
            reasons.append(f"fits {guest_count} guests")
            if row_capacity <= guest_count * 1.5:
                score += 1
        elif guest_count:
            score -= 5

        if requested_tier and row_tier == requested_tier:
            score += 3
            reasons.append(f"matches your {requested_tier} budget")

        if preferences.get('max_budget_total') is not None and row_cost <= preferences['max_budget_total']:
            score += 2
            reasons.append('stays within budget')

        if requested_io and requested_io in row_io:
            score += 3
            reasons.append(f"is {row.get('indoor_outdoor')}")

        if requested_type and requested_type in row_type:
            score += 2
            reasons.append(f"matches your {row.get('venue_type') or row.get('type')} preference")

        if requested_style and requested_style in row_style:
            score += 2
            reasons.append(f"has a {row.get('style')} feel")

        if needs_parking and int(row.get('parking') or 0) == 1:
            score += 1
            reasons.append('includes parking')

        if needs_accessibility and int(row.get('accessibility') or 0) == 1:
            score += 1
            reasons.append('supports accessibility needs')

        score += rating
        enriched = dict(row)
        enriched['score'] = round(score, 2)
        enriched['reasons'] = reasons[:3]
        results.append(enriched)

    results.sort(key=lambda r: (-r['score'], float(r.get('estimated_cost') or r.get('cost') or 0), r.get('name', '')))
    return results[:limit]


def search_caterers(preferences=None, limit=5):
    preferences = preferences or {}
    rows = get_catering(
        location=preferences.get('location_area'),
        max_budget=preferences.get('budget_per_person'),
        cuisine=preferences.get('cuisine'),
        price_tier=preferences.get('budget_level'),
        service_type=preferences.get('service_type'),
        dietary_need=preferences.get('dietary_needs'),
    )

    if not rows and preferences.get('location_area'):
        rows = get_catering(
            max_budget=preferences.get('budget_per_person'),
            cuisine=preferences.get('cuisine'),
            price_tier=preferences.get('budget_level'),
            service_type=preferences.get('service_type'),
            dietary_need=preferences.get('dietary_needs'),
        )

    requested_tier = _normalize_price_tier(preferences.get('budget_level'))
    requested_cuisine = _normalize_text(preferences.get('cuisine'))
    requested_service = _normalize_text(preferences.get('service_type'))
    dietary_needs = [_normalize_text(d) for d in (preferences.get('dietary_needs') or []) if d]

    results = []
    for row in rows:
        score = 0
        reasons = []
        cuisine = _normalize_text(row.get('cuisine'))
        service = _normalize_text(row.get('service_type') or row.get('type'))
        tier = _normalize_price_tier(row.get('price_tier'))
        dietary_text = _normalize_text(row.get('dietary_options'))
        price = float(row.get('cost_per_person') or 0)
        rating = float(row.get('rating') or 0)

        if requested_cuisine and requested_cuisine in cuisine:
            score += 4
            reasons.append(f"offers {row.get('cuisine')} food")

        if requested_service and requested_service in service:
            score += 3
            reasons.append(f"supports {row.get('service_type')} service")

        if requested_tier and requested_tier == tier:
            score += 2
            reasons.append(f"matches your {tier} budget")

        if preferences.get('budget_per_person') is not None and price <= preferences['budget_per_person']:
            score += 2
            reasons.append('fits your per-person budget')

        matched_dietary = [need for need in dietary_needs if need and need in dietary_text]
        if matched_dietary:
            score += len(matched_dietary)
            reasons.append('covers dietary needs')

        score += rating
        enriched = dict(row)
        enriched['score'] = round(score, 2)
        enriched['reasons'] = reasons[:3]
        results.append(enriched)

    results.sort(key=lambda r: (-r['score'], float(r.get('cost_per_person') or 0), r.get('name', '')))
    return results[:limit]


def estimate_budget(event):
    attendance = int((event or {}).get('guest_count') or 50)
    venue_cost = float((event or {}).get('venue_cost') or 300)
    food_cost_per_person = float((event or {}).get('food_cost_per_person') or 10)
    misc = float((event or {}).get('misc_cost') or 200)
    food_cost = attendance * food_cost_per_person

    return {
        'attendance': attendance,
        'venue': venue_cost,
        'food': food_cost,
        'misc': misc,
        'total': venue_cost + food_cost + misc,
    }
