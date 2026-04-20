"""
Phrase-variation parser stress test for Spartan Shield Saver.

Goal:
- Test MANY wording variations, not just field values
- Show which phrasings are caught by the parser/interpreter
- Highlight slips through the parser

How to run:
    python test_ai_phrase_variants.py

Put this file in Backend/
"""

from pathlib import Path
from collections import Counter, defaultdict
import traceback

from ai.action_interpreter import interpret_message, get_default_chat_state


BASE_CONTEXT = {
    "events": [
        {
            "id": 1,
            "title": "Spring Expo",
            "date": "2026-04-24",
            "start_datetime": "2026-04-24T17:00:00",
            "location": "Webb Center Ballroom",
            "description": "Networking event",
            "guest_count": 80,
        },
        {
            "id": 2,
            "title": "Cybersecurity Mixer",
            "date": "2026-05-02",
            "start_datetime": "2026-05-02T18:30:00",
            "location": "Engineering Auditorium",
            "description": "Student mixer",
            "guest_count": 120,
        },
    ],
    "tasks": [
        {"id": 1, "event_id": 1, "title": "Call the caterer", "completed": 0},
        {"id": 2, "event_id": 1, "title": "Send invitations", "completed": 0},
        {"id": 3, "event_id": 1, "title": "Confirm venue", "completed": 0},
    ],
}


def run_case(message, expected_types, label, state=None, context=None):
    context = context or BASE_CONTEXT
    state = state or get_default_chat_state()
    try:
        result = interpret_message(message, context=context, state=state)
        actual = result.get("type")
        status = "PASS" if actual in expected_types else "FAIL"
        return {
            "label": label,
            "message": message,
            "expected": sorted(expected_types),
            "actual": actual,
            "status": status,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {
            "label": label,
            "message": message,
            "expected": sorted(expected_types),
            "actual": "ERROR",
            "status": "ERROR",
            "result": None,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def build_cases():
    cases = []

    # CREATE wording variants
    create_phrases = [
        "create an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "create a new event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "create event Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "plan an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "plan a new event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "help me plan an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "i want to create an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "i want to plan an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "set up an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "organize an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        # more natural / riskier
        "i need to set up Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "can you make an event called Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "let's plan Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "i'm putting together Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
        "we're hosting Spring Expo on April 24 at 5 pm at Webb Center Ballroom for 80 people",
    ]
    for i, msg in enumerate(create_phrases, 1):
        cases.append((msg, {"event_create", "event_create_collecting"}, f"create_wording_{i}", None))

    # UPDATE wording variants - time
    update_time_phrases = [
        "change it to 6 pm",
        "update it to 6 pm",
        "set it to 6 pm",
        "move it to 6 pm",
        "push it to 6 pm",
        "switch it to 6 pm",
        "reschedule it to 6 pm",
        "make it start at 6 pm",
        "change the time to 6 pm",
        "update the time to 6 pm",
        "set the time to 6 pm",
        "change the start time to 6 pm",
        "update the start time to 6 pm",
        "set the start time to 6 pm",
        # natural / riskier
        "can you move it to 6 pm",
        "let's move it to 6 pm",
        "actually put it at 6 pm",
        "bump it to 6 pm",
        "have it start at 6 pm",
        "make it 6 pm instead",
    ]
    for i, msg in enumerate(update_time_phrases, 1):
        st = get_default_chat_state()
        st["last_event_id"] = 1
        cases.append((msg, {"event_update", "event_update_no_changes"}, f"update_time_wording_{i}", st))

    # UPDATE wording variants - guest count
    update_guest_phrases = [
        "actually make it 120 people",
        "make it 120 guests",
        "change it to 120 people",
        "set it to 120 people",
        "bump it to 120",
        "bump attendance to 120",
        "bump guest count to 120",
        "change the guest count to 120",
        "update the guest count to 120",
        "set the guest count to 120",
        "guest count is 120",
        "we're expecting 120",
        # natural / riskier
        "make it bigger",
        "increase attendance to 120",
        "raise the guest count to 120",
        "have 120 people come",
    ]
    for i, msg in enumerate(update_guest_phrases, 1):
        st = get_default_chat_state()
        st["last_event_id"] = 1
        cases.append((msg, {"event_update", "event_update_no_changes", "fallback"}, f"update_guest_wording_{i}", st))

    # UPDATE wording variants - location
    update_location_phrases = [
        "change the location to Student Center Ballroom",
        "update the location to Student Center Ballroom",
        "set the location to Student Center Ballroom",
        "location is Student Center Ballroom",
        "move the event to Student Center Ballroom",
        # natural / riskier
        "put it in Student Center Ballroom",
        "have it at Student Center Ballroom instead",
        "move it to Student Center Ballroom",
        "switch the venue to Student Center Ballroom",
    ]
    for i, msg in enumerate(update_location_phrases, 1):
        st = get_default_chat_state()
        st["last_event_id"] = 1
        cases.append((msg, {"event_update", "event_update_no_changes", "fallback"}, f"update_location_wording_{i}", st))

    # UPDATE wording variants - title
    update_title_phrases = [
        "call it Spring Expo 2026",
        "rename it to Spring Expo 2026",
        "change the title to Spring Expo 2026",
        "update the title to Spring Expo 2026",
        "set the title to Spring Expo 2026",
        "it's called Spring Expo 2026",
        # natural / riskier
        "name it Spring Expo 2026",
        "change the name to Spring Expo 2026",
        "update the name to Spring Expo 2026",
        "set the name to Spring Expo 2026",
    ]
    for i, msg in enumerate(update_title_phrases, 1):
        st = get_default_chat_state()
        st["last_event_id"] = 1
        cases.append((msg, {"event_update", "event_update_no_changes", "fallback"}, f"update_title_wording_{i}", st))

    # TASK CREATE wording variants
    task_create_phrases = [
        "add task call the caterer",
        "add a task to call the caterer",
        "create task call the caterer",
        "create a task to call the caterer",
        "remind me to call the caterer",
        "i need to call the caterer",
        "we need to call the caterer",
        "we should call the caterer",
        "remember to call the caterer",
        "make a note to call the caterer",
        "put call the caterer on my task list",
        "add call the caterer to my to-do list",
        # natural / riskier
        "don't let me forget to call the caterer",
        "I should probably call the caterer",
        "calling the caterer still needs to happen",
    ]
    for i, msg in enumerate(task_create_phrases, 1):
        st = get_default_chat_state()
        st["last_event_id"] = 1
        cases.append((msg, {"task_create", "fallback"}, f"task_create_wording_{i}", st))

    # TASK COMPLETE wording variants
    task_complete_phrases = [
        "mark invitations done",
        "complete send invitations",
        "finish send invitations",
        "finished send invitations",
        "done with send invitations",
        "check off send invitations",
        "cross off send invitations",
        "mark task send invitations done",
        "complete the task send invitations",
        # natural / riskier
        "i already sent invitations",
        "invitations are done",
        "that task is finished",
    ]
    for i, msg in enumerate(task_complete_phrases, 1):
        st = get_default_chat_state()
        st["last_event_id"] = 1
        cases.append((msg, {"task_complete", "task_complete_not_found", "fallback"}, f"task_complete_wording_{i}", st))

    return cases


def summarize(results):
    counts = Counter(r["status"] for r in results)
    actuals = Counter(r["actual"] for r in results)
    return counts, actuals


def write_report(results, output_path="ai_phrase_variants_report.txt"):
    counts, actuals = summarize(results)
    by_prefix = defaultdict(list)
    for r in results:
        prefix = r["label"].rsplit("_", 1)[0]
        by_prefix[prefix].append(r)

    lines = []
    lines.append("AI Phrase Variants Report")
    lines.append("=" * 100)
    lines.append(f"Total cases: {len(results)}")
    lines.append(f"PASS: {counts.get('PASS', 0)}")
    lines.append(f"FAIL: {counts.get('FAIL', 0)}")
    lines.append(f"ERROR: {counts.get('ERROR', 0)}")
    lines.append("")
    lines.append("Returned action counts:")
    for k, v in actuals.most_common():
        lines.append(f"  - {k}: {v}")
    lines.append("")

    lines.append("Summary by wording family:")
    for family, items in sorted(by_prefix.items()):
        fam_counts = Counter(r["status"] for r in items)
        lines.append(
            f"  - {family}: PASS {fam_counts.get('PASS', 0)}, FAIL {fam_counts.get('FAIL', 0)}, ERROR {fam_counts.get('ERROR', 0)}"
        )
    lines.append("")

    failed = [r for r in results if r["status"] != "PASS"]
    if failed:
        lines.append("Failures / slips:")
        for r in failed:
            lines.append(f"[{r['status']}] {r['label']}")
            lines.append(f"  input:    {r['message']}")
            lines.append(f"  expected: {r['expected']}")
            lines.append(f"  actual:   {r['actual']}")
            if r["error"]:
                lines.append(f"  error:    {r['error']}")
        lines.append("")

    lines.append("Detailed results:")
    for r in results:
        lines.append(f"{r['status']} | {r['label']}")
        lines.append(f"  input:    {r['message']}")
        lines.append(f"  expected: {r['expected']}")
        lines.append(f"  actual:   {r['actual']}")
        if r["error"]:
            lines.append(f"  error:    {r['error']}")
        else:
            lines.append(f"  result:   {r['result']}")
        lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    cases = build_cases()
    results = [run_case(message, expected, label, state=state) for message, expected, label, state in cases]
    output_path = write_report(results)
    counts, _ = summarize(results)

    print("=" * 100)
    print("AI PHRASE VARIANTS COMPLETE")
    print(f"Total cases: {len(results)}")
    print(f"PASS: {counts.get('PASS', 0)}")
    print(f"FAIL: {counts.get('FAIL', 0)}")
    print(f"ERROR: {counts.get('ERROR', 0)}")
    print(f"Report written to: {output_path}")
    print("=" * 100)
