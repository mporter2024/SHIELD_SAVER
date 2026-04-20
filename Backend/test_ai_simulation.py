
"""
AI simulation harness for Spartan Shield Saver.

Purpose:
- Simulate dozens of event-creation and event-update requests
- Reuse your real interpreter logic
- Track misclassifications and crashes
- Write a readable report

How to run:
    python test_ai_simulation.py

Place this file in your Backend/ folder.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import traceback

from ai.action_interpreter import interpret_message, get_default_chat_state


BASE_EVENT_TITLES = [
    "Spring Expo",
    "Cybersecurity Mixer",
    "Alumni Networking Night",
    "Fundraiser Gala",
    "STEM Workshop",
    "Career Fair",
    "Leadership Summit",
    "Volunteer Appreciation Event",
    "Student Showcase",
    "Tech Panel",
]

LOCATIONS = [
    "Webb Center Ballroom",
    "Student Center Ballroom",
    "Engineering Auditorium",
    "Library Conference Room",
    "Campus Lawn",
    "Dining Hall Annex",
    "Norfolk Hall",
    "Innovation Lab",
]

DESCRIPTIONS = [
    "Networking event",
    "Fundraising event",
    "Student leadership program",
    "Tech discussion event",
    "Workshop for students",
    "Community outreach event",
]

TASK_TITLES = [
    "Call the caterer",
    "Send invitations",
    "Confirm venue",
    "Prepare name tags",
    "Review budget",
    "Confirm speaker",
]

CREATION_TEMPLATES = [
    "create an event called {title} on {date_text} at {time_text} at {location} for {guest_count} people",
    "plan an event called {title} for {guest_count} people on {date_text} at {time_text} in {location}",
    "i want to create {title} on {date_text} at {time_text} at {location} for about {guest_count} people",
    "help me plan an event called {title} at {location} on {date_text} at {time_text} for {guest_count} guests",
]

UPDATE_SCENARIOS = [
    ("change it to {new_time}", {"event_update"}),
    ("update it to {new_time}", {"event_update"}),
    ("set it to {new_time}", {"event_update"}),
    ("actually make it {new_guest_count} people", {"event_update"}),
    ("change the location to {new_location}", {"event_update"}),
    ("call it {new_title}", {"event_update"}),
    ("reschedule it to {new_date_text} at {new_time}", {"event_update"}),
    ("move it to {new_time}", {"event_update"}),
    ("make it {new_guest_count} guests", {"event_update"}),
    # intentionally messy / likely weaker
    ("push it back a little", {"fallback", "event_update_no_changes", "event_update"}),
    ("make it bigger", {"fallback", "event_update_no_changes", "event_update"}),
    ("switch to something cheaper", {"fallback", "event_update_no_changes", "event_update"}),
]

TASK_SCENARIOS = [
    ("remind me to call the caterer", {"task_create"}),
    ("i need to send invitations", {"task_create"}),
    ("we should confirm the venue", {"task_create"}),
    ("mark invitations done", {"task_complete", "task_complete_not_found"}),
    ("finished call the caterer", {"task_complete", "task_complete_not_found"}),
]

AMBIGUOUS_SCENARIOS = [
    ("fix it", {"fallback", "event_update_no_changes"}),
    ("do that", {"fallback"}),
    ("make it better", {"fallback", "event_update_no_changes"}),
]


def fmt_date(dt: datetime) -> str:
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def fmt_time(hour24: int, minute: int = 0) -> str:
    suffix = "am" if hour24 < 12 else "pm"
    h = hour24 % 12
    if h == 0:
        h = 12
    if minute:
        return f"{h}:{minute:02d} {suffix}"
    return f"{h} {suffix}"


def build_seed_events(n: int = 30):
    base = datetime.now() + timedelta(days=7)
    events = []
    for i in range(n):
        title = f"{BASE_EVENT_TITLES[i % len(BASE_EVENT_TITLES)]} {2026 + (i % 3)} #{i+1}"
        date_dt = base + timedelta(days=i)
        hour = 17 + (i % 3)
        minute = 30 if i % 4 == 0 else 0
        location = LOCATIONS[i % len(LOCATIONS)]
        description = DESCRIPTIONS[i % len(DESCRIPTIONS)]
        guest_count = 40 + (i * 7)

        events.append({
            "id": i + 1,
            "title": title,
            "date": date_dt.strftime("%Y-%m-%d"),
            "start_datetime": f"{date_dt.strftime('%Y-%m-%d')}T{hour:02d}:{minute:02d}:00",
            "location": location,
            "description": description,
            "guest_count": guest_count,
        })
    return events


def build_seed_tasks(events):
    tasks = []
    tid = 1
    for ev in events:
        for t in TASK_TITLES[:3]:
            tasks.append({
                "id": tid,
                "event_id": ev["id"],
                "title": t,
                "completed": 0,
            })
            tid += 1
    return tasks


def run_case(message, context, state, expected_types, category, label):
    try:
        result = interpret_message(message, context=context, state=state)
        actual = result.get("type")
        ok = actual in expected_types
        return {
            "ok": ok,
            "category": category,
            "label": label,
            "message": message,
            "expected": sorted(expected_types),
            "actual": actual,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "category": category,
            "label": label,
            "message": message,
            "expected": sorted(expected_types),
            "actual": "ERROR",
            "result": None,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def simulate():
    events = build_seed_events(36)
    tasks = build_seed_tasks(events)
    context = {"events": events, "tasks": tasks}

    results = []

    # Creation simulations
    for i, ev in enumerate(events[:20]):
        dt = datetime.strptime(ev["date"], "%Y-%m-%d")
        hour = int(ev["start_datetime"][11:13])
        minute = int(ev["start_datetime"][14:16])

        template = CREATION_TEMPLATES[i % len(CREATION_TEMPLATES)]
        msg = template.format(
            title=ev["title"],
            date_text=fmt_date(dt),
            time_text=fmt_time(hour, minute),
            location=ev["location"],
            guest_count=ev["guest_count"],
        )
        state = get_default_chat_state()
        results.append(run_case(
            msg, context, state, {"event_create", "event_create_collecting"},
            "creation", f"create_{i+1}"
        ))

    # Update simulations tied to existing events
    for i, ev in enumerate(events[:24]):
        base_dt = datetime.strptime(ev["date"], "%Y-%m-%d")
        new_dt = base_dt + timedelta(days=3)
        new_time = fmt_time(18 + (i % 2), 30 if i % 3 == 0 else 0)
        new_location = LOCATIONS[(i + 3) % len(LOCATIONS)]
        new_guest_count = ev["guest_count"] + 25
        new_title = ev["title"] + " Revised"

        state = get_default_chat_state()
        state["last_event_id"] = ev["id"]

        template, expected = UPDATE_SCENARIOS[i % len(UPDATE_SCENARIOS)]
        msg = template.format(
            new_time=new_time,
            new_guest_count=new_guest_count,
            new_location=new_location,
            new_title=new_title,
            new_date_text=fmt_date(new_dt),
        )
        results.append(run_case(
            msg, context, state, expected, "update", f"update_{i+1}"
        ))

    # Task simulations
    for i, (template, expected) in enumerate(TASK_SCENARIOS, start=1):
        state = get_default_chat_state()
        state["last_event_id"] = events[0]["id"]
        results.append(run_case(
            template, context, state, expected, "task", f"task_{i}"
        ))

    # Ambiguous tests
    for i, (template, expected) in enumerate(AMBIGUOUS_SCENARIOS, start=1):
        state = get_default_chat_state()
        state["last_event_id"] = events[0]["id"]
        results.append(run_case(
            template, context, state, expected, "ambiguous", f"ambiguous_{i}"
        ))

    return results


def write_report(results, output_path="ai_simulation_report.txt"):
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed

    by_category = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r)

    actual_counts = Counter(r["actual"] for r in results)

    lines = []
    lines.append("AI Simulation Report")
    lines.append("=" * 80)
    lines.append(f"Total cases: {total}")
    lines.append(f"Passed: {passed}")
    lines.append(f"Failed: {failed}")
    lines.append("")

    lines.append("Returned action counts:")
    for action, count in actual_counts.most_common():
        lines.append(f"  - {action}: {count}")
    lines.append("")

    for category, items in by_category.items():
        cat_pass = sum(1 for r in items if r["ok"])
        lines.append(f"[{category.upper()}] {cat_pass}/{len(items)} passed")
        for r in items:
            status = "PASS" if r["ok"] else "FAIL"
            lines.append(f"{status} | {r['label']} | input: {r['message']}")
            lines.append(f"  expected: {r['expected']}")
            lines.append(f"  actual:   {r['actual']}")
            if r["error"]:
                lines.append(f"  error:    {r['error']}")
            else:
                lines.append(f"  result:   {r['result']}")
        lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path, passed, failed, total


if __name__ == "__main__":
    results = simulate()
    output_path, passed, failed, total = write_report(results)

    print("=" * 80)
    print("AI SIMULATION COMPLETE")
    print(f"Total cases: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Report written to: {output_path}")
    print("=" * 80)
