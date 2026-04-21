from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AdviceDecision:
    mode: str
    missing_fields: list[str]
    focus: str | None = None


class ConversationManager:
    """Small stateful helper that turns raw context into response-ready context."""

    def __init__(self, context: dict[str, Any] | None = None, selected_event: dict[str, Any] | None = None):
        self.context = context or {}
        self.selected_event = selected_event or {}
        self.events = list(self.context.get('events', []))
        self.tasks = list(self.context.get('tasks', []))
        self.chat_state = self.context.get('chat_state') or {}
        self.planning_context = self.context.get('planning_context') or self.chat_state.get('planning_context') or {}

    def build_snapshot(self) -> dict[str, Any]:
        snapshot = {
            'selected_event': self.selected_event or None,
            'events': self.events,
            'tasks': self.tasks,
            'planning_context': self.planning_context,
            'known_values': {},
            'pending_tasks': [],
            'completed_tasks': [],
            'current_event_tasks': [],
            'current_event_pending_tasks': [],
            'current_event_completed_tasks': [],
            'stats': {},
            'advice_hooks': self._build_advice_hooks(),
        }

        selected_event_id = None
        if self.selected_event and self.selected_event.get('id') is not None:
            try:
                selected_event_id = int(self.selected_event.get('id'))
            except (TypeError, ValueError):
                selected_event_id = None

        for task in self.tasks:
            completed = int(task.get('completed', 0) or 0) == 1
            if completed:
                snapshot['completed_tasks'].append(task)
            else:
                snapshot['pending_tasks'].append(task)

            if selected_event_id is not None:
                try:
                    belongs = int(task.get('event_id', 0) or 0) == selected_event_id
                except (TypeError, ValueError):
                    belongs = False
                if belongs:
                    snapshot['current_event_tasks'].append(task)
                    if completed:
                        snapshot['current_event_completed_tasks'].append(task)
                    else:
                        snapshot['current_event_pending_tasks'].append(task)

        snapshot['known_values'] = self._collect_known_values()
        snapshot['stats'] = {
            'total_events': len(self.events),
            'total_tasks': len(self.tasks),
            'pending_tasks': len(snapshot['pending_tasks']),
            'completed_tasks': len(snapshot['completed_tasks']),
            'current_event_tasks': len(snapshot['current_event_tasks']),
            'current_event_pending_tasks': len(snapshot['current_event_pending_tasks']),
        }
        return snapshot

    def decide(self, intent: str, message: str) -> AdviceDecision:
        lowered = (message or '').lower()
        known = self._collect_known_values()

        if intent == 'event_creation':
            missing = [field for field in ['event_type', 'guest_count', 'date', 'location'] if not known.get(field)]
            return AdviceDecision(mode='guided_creation', missing_fields=missing, focus='event_setup')

        if intent == 'budgeting' or any(word in lowered for word in ['budget', 'cost', 'price', 'expense']):
            missing = [field for field in ['guest_count', 'location'] if not known.get(field)]
            return AdviceDecision(mode='budget_advice', missing_fields=missing, focus='budget')

        if any(word in lowered for word in ['timeline', 'schedule', 'when should', 'milestone']):
            missing = [field for field in ['date'] if not known.get(field)]
            return AdviceDecision(mode='timeline_advice', missing_fields=missing, focus='timeline')

        if any(word in lowered for word in ['venue', 'location']):
            missing = [field for field in ['guest_count'] if not known.get(field)]
            return AdviceDecision(mode='venue_advice', missing_fields=missing, focus='venue')

        if any(word in lowered for word in ['catering', 'food', 'menu']):
            missing = [field for field in ['guest_count'] if not known.get(field)]
            return AdviceDecision(mode='catering_advice', missing_fields=missing, focus='catering')

        if intent == 'task_help':
            return AdviceDecision(mode='task_guidance', missing_fields=[], focus='tasks')

        if intent == 'event_summary':
            return AdviceDecision(mode='event_summary', missing_fields=[], focus='summary')

        if intent == 'greeting':
            return AdviceDecision(mode='greeting', missing_fields=[], focus='intro')

        return AdviceDecision(mode='general_help', missing_fields=[], focus='general')

    def _collect_known_values(self) -> dict[str, Any]:
        event = self.selected_event or {}
        planning = self.planning_context or {}
        return {
            'event_type': planning.get('event_type') or self._infer_event_type(event),
            'guest_count': planning.get('guest_count') or self._clean_positive_int(event.get('guest_count')),
            'date': planning.get('date') or event.get('date') or (event.get('start_datetime') or '')[:10] or None,
            'location': planning.get('location_area') or event.get('location'),
            'budget_level': planning.get('budget_level'),
            'budget_total': event.get('budget_total') or planning.get('max_budget_total'),
            'budget_per_person': planning.get('budget_per_person'),
            'cuisine': planning.get('cuisine'),
            'service_type': planning.get('service_type'),
            'indoor_outdoor': planning.get('indoor_outdoor'),
            'venue_type': planning.get('venue_type'),
        }

    def _infer_event_type(self, event: dict[str, Any]) -> str | None:
        haystack = ' '.join(
            str(part or '') for part in [event.get('title'), event.get('description')]
        ).lower()
        keywords = {
            'networking': ['network', 'mixer'],
            'fundraiser': ['fundraiser', 'fund-raiser', 'donation'],
            'birthday': ['birthday'],
            'meeting': ['meeting', 'board', 'committee'],
            'conference': ['conference', 'summit', 'symposium'],
            'social': ['social', 'celebration', 'party'],
            'workshop': ['workshop', 'training'],
        }
        for label, words in keywords.items():
            if any(word in haystack for word in words):
                return label
        return None

    def _build_advice_hooks(self) -> dict[str, str | None]:
        known = self._collect_known_values()
        hooks = {
            'cost_sensitivity': None,
            'schedule_pressure': None,
            'size_band': None,
        }
        guest_count = self._clean_positive_int(known.get('guest_count'))
        if guest_count:
            if guest_count <= 25:
                hooks['size_band'] = 'small'
            elif guest_count <= 80:
                hooks['size_band'] = 'medium'
            else:
                hooks['size_band'] = 'large'

        if known.get('budget_level') in {'budget', 'low', 'affordable'} or known.get('budget_per_person'):
            hooks['cost_sensitivity'] = 'high'

        if known.get('date'):
            hooks['schedule_pressure'] = 'dated'
        return hooks

    @staticmethod
    def _clean_positive_int(value: Any) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None
