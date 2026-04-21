from __future__ import annotations

from typing import Any

from .budget_engine import analyze_budget, generate_budget_estimate
from .conversation_manager import ConversationManager
from .planning_engine import get_catering, get_venues


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return '$0'


def _event_label(selected_event: dict[str, Any] | None) -> str:
    if not selected_event:
        return 'your event'
    return f"'{selected_event.get('title', 'Untitled Event')}'"


def _join_bits(bits: list[str]) -> str:
    return ' '.join(bit.strip() for bit in bits if bit and bit.strip())


def _next_question(options: list[str]) -> str:
    if not options:
        return ''
    return options[0]


def _pick_top_tasks(tasks: list[dict[str, Any]], limit: int = 3) -> str:
    titles = [task.get('title', 'Untitled task') for task in tasks[:limit]]
    return ', '.join(titles)


def _budget_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    known = snapshot['known_values']
    label = _event_label(selected_event)
    estimate = generate_budget_estimate(selected_event or known)
    totals = estimate['totals']
    analysis = analyze_budget(estimate['event'])
    venue_context = estimate['venue_context']

    size_phrase = ''
    guest_count = _safe_int(known.get('guest_count'))
    if guest_count > 0:
        size_phrase = f"for around {guest_count} guests"

    intro = _join_bits([
        f"A realistic starting budget for {label}",
        size_phrase,
        "should center on venue, food, and a small safety buffer.",
    ])

    breakdown = (
        f"Right now a smart estimate would be about {_format_money(totals['total'])} total "
        f"({_format_money(totals['venue_cost'])} venue, {_format_money(totals['food_total'])} food, "
        f"and {_format_money(totals['budget_contingency'])} contingency)."
    )

    context_line = ''
    if venue_context.get('message'):
        context_line = venue_context['message']

    warnings = analysis.get('warnings', [])
    suggestions = analysis.get('suggestions', [])
    guidance = ''
    if warnings:
        guidance = warnings[0]
    elif suggestions:
        guidance = suggestions[0]

    followups = []
    if not known.get('guest_count'):
        followups.append('About how many people are you expecting?')
    elif not known.get('location'):
        followups.append('Do you already have a location in mind, or should I assume a free campus-style space?')
    else:
        followups.append('I can turn this into a more detailed category-by-category budget if you want.')

    return _join_bits([intro, breakdown, context_line, guidance, _next_question(followups)])


def _timeline_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    known = snapshot['known_values']
    label = _event_label(selected_event)
    guest_count = _safe_int(known.get('guest_count'))

    intro = f"A good timeline for {label} should move from setup decisions into booking, then confirmations, then event-day execution."
    if guest_count and guest_count <= 30:
        detail = 'Since this looks like a smaller event, you can usually move faster as long as the location and food are decided early.'
    elif guest_count >= 80:
        detail = 'Because this is a larger event, venue, catering, staffing, and final headcount should be locked down earlier than usual.'
    else:
        detail = 'A medium-sized event usually benefits from a clear week-by-week checklist rather than leaving all prep to the last few days.'

    checklist = 'A simple sequence is: finalize basics, book space and food, confirm attendance and supplies, then run setup, event execution, and follow-up.'

    if known.get('date'):
        close = f"Since you already have a date in mind ({known['date']}), I can help turn that into a countdown checklist next."
    else:
        close = 'When is the event happening? Once I know that, I can compress or expand the timeline for you.'

    return _join_bits([intro, detail, checklist, close])


def _creation_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None, missing_fields: list[str]) -> str:
    known = snapshot['known_values']
    label = _event_label(selected_event) if selected_event else 'a new event'
    opening = f"The fastest way to build {label} is to lock in the purpose, guest count, date, location, and budget first."

    tailored = []
    if known.get('event_type'):
        tailored.append(f"Because this seems like a {known['event_type']} event, the tone of the venue and food choices should match that style.")
    if known.get('guest_count'):
        tailored.append(f"With about {known['guest_count']} guests, your venue and catering decisions will drive most of the plan.")

    next_prompt_map = {
        'event_type': 'What kind of event are you trying to host?',
        'guest_count': 'About how many people are you expecting?',
        'date': 'What date are you aiming for?',
        'location': 'Do you already know where you want to hold it?',
    }
    next_step = next_prompt_map.get(missing_fields[0], 'I can help you turn those basics into a full plan.') if missing_fields else 'I can turn those basics into a draft event plan for you next.'
    return _join_bits([opening, *tailored, next_step])


def _venue_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    known = snapshot['known_values']
    guest_count = _safe_int(known.get('guest_count'))
    venue_options = get_venues(
        location=known.get('location'),
        min_capacity=guest_count if guest_count else None,
        max_budget=known.get('budget_total'),
        price_tier=known.get('budget_level'),
        venue_type=known.get('venue_type'),
        indoor_outdoor=known.get('indoor_outdoor'),
        style=known.get('event_type'),
    )
    intro = f"The best venue for {_event_label(selected_event)} depends mostly on headcount, budget, accessibility, and the kind of atmosphere you want."
    if venue_options:
        preview = '; '.join(
            f"{item['name']} ({item.get('capacity', 'n/a')} cap, {_format_money(item.get('cost', 0))})"
            for item in venue_options[:3]
        )
        close = f"A few matches from your current data are: {preview}."
    else:
        close = 'I do not have a tight match yet, so I would narrow it first by guest count and whether you want something indoor, outdoor, formal, or casual.'

    question = 'Do you want me to focus more on affordability, atmosphere, or capacity?' if not known.get('guest_count') else 'I can also recommend a few venue styles if you want.'
    return _join_bits([intro, close, question])


def _catering_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    known = snapshot['known_values']
    catering_options = get_catering(
        location=known.get('location'),
        max_budget=known.get('budget_per_person'),
        cuisine=known.get('cuisine'),
        price_tier=known.get('budget_level'),
        service_type=known.get('service_type'),
    )
    intro = f"For {_event_label(selected_event)}, catering decisions usually come down to guest count, serving style, and how much you want to spend per person."
    if known.get('guest_count'):
        intro += f" For about {known['guest_count']} guests, simple buffet or tray-based service is often easier to manage than fully plated service."
    preview = ''
    if catering_options:
        preview = 'Some options that fit your current info are: ' + '; '.join(
            f"{item['name']} ({item.get('type', 'service')}, {_format_money(item.get('cost_per_person', 0))}/person)"
            for item in catering_options[:3]
        ) + '.'
    guidance = 'If you want to keep costs down, food format usually matters more than cuisine.'
    question = 'Do you want the food to feel inexpensive, polished, or somewhere in the middle?'
    return _join_bits([intro, preview, guidance, question])


def _task_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    current_pending = snapshot['current_event_pending_tasks']
    overall_pending = snapshot['pending_tasks']
    if selected_event:
        if current_pending:
            return _join_bits([
                f"For {_event_label(selected_event)}, the next tasks I would prioritize are {_pick_top_tasks(current_pending)}.",
                f"You still have {len(current_pending)} incomplete task(s) tied to this event.",
                'I can also help you decide what should happen first if the list feels crowded.'
            ])
        return _join_bits([
            f"{_event_label(selected_event)} does not have any open tasks right now.",
            'A smart next step would be confirmations, final logistics, or a quick event-day checklist.'
        ])

    if overall_pending:
        return _join_bits([
            f"Across all events, you currently have {len(overall_pending)} pending task(s).",
            f"The next few worth handling are {_pick_top_tasks(overall_pending)}.",
            'I can narrow that down to a single event if you want.'
        ])
    return 'You do not have any open tasks yet. Once you create a few, I can help prioritize them.'


def _summary_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    stats = snapshot['stats']
    if selected_event:
        known = snapshot['known_values']
        bits = [f"Here is the current picture for {_event_label(selected_event)}."]
        if known.get('date'):
            bits.append(f"It is scheduled for {known['date']}.")
        if known.get('location'):
            bits.append(f"The location is {known['location']}.")
        if known.get('guest_count'):
            bits.append(f"You are planning for about {known['guest_count']} guests.")
        bits.append(f"There are {stats['current_event_tasks']} task(s) tied to it, with {stats['current_event_pending_tasks']} still open.")
        bits.append('I can also summarize the budget or next actions for this event if that would help.')
        return _join_bits(bits)

    if stats['total_events'] <= 0:
        return 'You do not have any events yet. Once one is created, I can summarize its status, tasks, and budget.'
    return _join_bits([
        f"You currently have {stats['total_events']} event(s) and {stats['pending_tasks']} pending task(s) across them.",
        'If you mention an event by name, I can give you a much more useful status summary.'
    ])


def _greeting_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    stats = snapshot['stats']
    if selected_event:
        return _join_bits([
            f"Hi — I can help with {_event_label(selected_event)}.",
            f"It currently has {stats['current_event_pending_tasks']} open task(s).",
            'You can ask about budget, timeline, venue, catering, or next steps.'
        ])
    if stats['total_events'] > 0:
        return _join_bits([
            f"Hi — you currently have {stats['total_events']} event(s) and {stats['pending_tasks']} open task(s).",
            'Ask me about budget, timelines, venues, catering, or what to work on next.'
        ])
    return 'Hi! I can help you plan events, think through costs, organize tasks, and give more tailored advice as you add details.'


def _general_reply(snapshot: dict[str, Any], selected_event: dict[str, Any] | None) -> str:
    known = snapshot['known_values']
    if selected_event:
        return _join_bits([
            f"I can help you think through {_event_label(selected_event)} from a few angles: budget, timeline, venue, catering, logistics, or task priorities.",
            'Tell me which part you want to work on and I will make the advice specific to that event.'
        ])
    if known.get('event_type') or known.get('guest_count'):
        return _join_bits([
            'I have enough context to give more specific planning advice now.',
            'Ask me about budget, venue, catering, timeline, or next steps and I will tailor it to what you have already told me.'
        ])
    return 'I can help with event creation, budgeting, venues, catering, timelines, and task planning. Tell me what part you are thinking through and I will guide you from there.'



def get_response(intent, text, context=None, selected_event=None, confidence=None):
    context = context or {'events': [], 'tasks': []}
    manager = ConversationManager(context=context, selected_event=selected_event)
    snapshot = manager.build_snapshot()
    decision = manager.decide(intent=intent, message=text)

    if intent == 'unclear' and confidence is not None and confidence < 0.45:
        return _general_reply(snapshot, selected_event)

    if decision.mode == 'budget_advice':
        return _budget_reply(snapshot, selected_event)
    if decision.mode == 'timeline_advice':
        return _timeline_reply(snapshot, selected_event)
    if decision.mode == 'guided_creation':
        return _creation_reply(snapshot, selected_event, decision.missing_fields)
    if decision.mode == 'venue_advice':
        return _venue_reply(snapshot, selected_event)
    if decision.mode == 'catering_advice':
        return _catering_reply(snapshot, selected_event)
    if decision.mode == 'task_guidance':
        return _task_reply(snapshot, selected_event)
    if decision.mode == 'event_summary':
        return _summary_reply(snapshot, selected_event)
    if decision.mode == 'greeting':
        return _greeting_reply(snapshot, selected_event)
    return _general_reply(snapshot, selected_event)
