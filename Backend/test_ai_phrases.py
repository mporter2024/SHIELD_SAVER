from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ai.action_interpreter import interpret_message, get_default_chat_state


@dataclass
class PhraseTest:
    category: str
    text: str
    expected_types: List[str]
    notes: str = ""


BASE_CONTEXT: Dict[str, List[Dict[str, Any]]] = {
    "events": [
        {
            "id": 1,
            "title": "Spring Expo",
            "date": "2026-04-24",
            "start_datetime": "2026-04-24T17:00:00",
            "end_datetime": None,
            "location": "Webb Center Ballroom",
            "description": "Campus networking event",
            "guest_count": 80,
            "budget_total": 2500,
        },
        {
            "id": 2,
            "title": "Charity Gala",
            "date": "2026-05-10",
            "start_datetime": "2026-05-10T18:30:00",
            "end_datetime": None,
            "location": "Harbor View Ballroom",
            "description": "Fundraising dinner",
            "guest_count": 150,
            "budget_total": 8000,
        },
    ],
    "tasks": [
        {
            "id": 101,
            "event_id": 1,
            "title": "Call the caterer",
            "completed": 0,
            "due_date": "2026-04-20",
            "start_datetime": None,
            "end_datetime": None,
        },
        {
            "id": 102,
            "event_id": 1,
            "title": "Send invitations",
            "completed": 0,
            "due_date": "2026-04-18",
            "start_datetime": None,
            "end_datetime": None,
        },
        {
            "id": 103,
            "event_id": 2,
            "title": "Confirm venue",
            "completed": 0,
            "due_date": "2026-05-01",
            "start_datetime": None,
            "end_datetime": None,
        },
        {
            "id": 104,
            "event_id": 2,
            "title": "Vendor confirmation",
            "completed": 1,
            "due_date": "2026-04-30",
            "start_datetime": None,
            "end_datetime": None,
        },
    ],
}


TESTS: List[PhraseTest] = [
    # Event creation
    PhraseTest("event_create", "create an event called Spring Mixer on april 24 at 5 pm at Webb Center", ["event_create", "event_create_collecting"]),
    PhraseTest("event_create", "i want to plan a networking event for about 80 people tomorrow at 5 pm in the student center", ["event_create", "event_create_collecting"]),
    PhraseTest("event_create", "help me create an event called Tech Night", ["event_create_collecting"]),

    # Event updates - clean
    PhraseTest("event_update", "change it to 6 pm", ["event_update"]),
    PhraseTest("event_update", "update it to 5 pm", ["event_update"]),
    PhraseTest("event_update", "change the location to Student Center Ballroom", ["event_update"]),
    PhraseTest("event_update", "actually make it 120 people", ["event_update"]),
    PhraseTest("event_update", "call it Spring Expo 2026", ["event_update"]),
    PhraseTest("event_update", "reschedule it to april 25 at 7 pm", ["event_update"]),

    # Event updates - messier
    PhraseTest("event_update_messy", "push it back a little", ["event_update", "event_update_no_changes", "fallback"], "This one often exposes limits in rule-based parsing."),
    PhraseTest("event_update_messy", "make it more formal", ["event_update", "event_update_no_changes", "fallback"]),
    PhraseTest("event_update_messy", "move that one to next friday", ["event_update"]),
    PhraseTest("event_update_messy", "switch to something cheaper", ["event_update", "event_update_no_changes", "fallback"]),

    # Task creation
    PhraseTest("task_create", "remind me to call the caterer", ["task_create"]),
    PhraseTest("task_create", "i need to send invitations", ["task_create"]),
    PhraseTest("task_create", "we should confirm the venue", ["task_create"]),
    PhraseTest("task_create", "remember to finalize the budget", ["task_create"]),
    PhraseTest("task_create", "add a task to confirm the DJ", ["task_create"]),

    # Task completion
    PhraseTest("task_complete", "mark invitations done", ["task_complete", "task_complete_not_found"]),
    PhraseTest("task_complete", "finished call the caterer", ["task_complete", "task_complete_not_found"]),
    PhraseTest("task_complete", "done with venue confirmation", ["task_complete", "task_complete_not_found"]),
    PhraseTest("task_complete", "complete vendor confirmation", ["task_complete", "task_complete_not_found"]),

    # Ambiguous / fallback
    PhraseTest("fallback", "fix that", ["fallback", "event_update_no_changes"]),
    PhraseTest("fallback", "do the same for the other event", ["fallback", "event_update_needs_target"]),
    PhraseTest("fallback", "help", ["fallback"]),
]


def summarize_result(result: Dict[str, Any]) -> str:
    result_type = result.get("type")
    parts = [f"type={result_type}"]

    if result_type in {"event_create", "event_create_collecting"}:
        parts.append(f"draft={result.get('draft')}")
    elif result_type == "event_update":
        target = result.get("target_event", {}).get("title")
        parts.append(f"target={target}")
        parts.append(f"changes={result.get('changes')}")
    elif result_type in {"task_create", "task_complete"}:
        parts.append(f"task={result.get('task') or result.get('task_data')}")
        if result.get("target_task"):
            parts.append(f"target_task={result['target_task'].get('title')}")
    elif result_type:
        if result.get("reply"):
            parts.append(f"reply={result['reply']}")

    return " | ".join(parts)


def main() -> None:
    context = deepcopy(BASE_CONTEXT)
    state = get_default_chat_state()
    state["last_event_id"] = 1

    results_log: List[str] = []
    passed = 0
    failed = 0
    errors = 0

    results_log.append("AI PHRASE TEST RESULTS")
    results_log.append("=" * 80)
    results_log.append(f"Total tests: {len(TESTS)}")
    results_log.append("")

    for index, test in enumerate(TESTS, start=1):
        local_state = deepcopy(state)
        try:
            result = interpret_message(test.text, context=context, state=local_state)
            actual_type = result.get("type")
            ok = actual_type in test.expected_types

            if ok:
                passed += 1
                status = "PASS"
            else:
                failed += 1
                status = "FAIL"

            results_log.append(f"[{index:02d}] {status} | {test.category}")
            results_log.append(f"Input: {test.text}")
            results_log.append(f"Expected: {test.expected_types}")
            results_log.append(f"Actual:   {summarize_result(result)}")
            if test.notes:
                results_log.append(f"Notes:    {test.notes}")
            results_log.append("-" * 80)

        except Exception as exc:  # pragma: no cover - intentionally broad for harnessing
            errors += 1
            results_log.append(f"[{index:02d}] ERROR | {test.category}")
            results_log.append(f"Input: {test.text}")
            results_log.append(f"Error: {type(exc).__name__}: {exc}")
            if test.notes:
                results_log.append(f"Notes: {test.notes}")
            results_log.append("-" * 80)

    results_log.append("")
    results_log.append("SUMMARY")
    results_log.append("=" * 80)
    results_log.append(f"Passed: {passed}")
    results_log.append(f"Failed (wrong type): {failed}")
    results_log.append(f"Errored (exception): {errors}")

    report_path = "ai_phrase_test_report.txt"
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(results_log))

    print("\n".join(results_log))
    print(f"\nSaved detailed report to: {report_path}")


if __name__ == "__main__":
    main()
