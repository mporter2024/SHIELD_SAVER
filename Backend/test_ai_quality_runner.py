import json
import re
import sys
from pathlib import Path

from ai.unified_chatbot import UnifiedChatbot


DEFAULT_CONTEXT = {
    "events": [
        {
            "id": 1,
            "title": "Spring Expo",
            "date": "2026-04-24",
            "location": "Webb Center Ballroom",
            "guest_count": 80,
            "description": "Campus showcase event",
        },
        {
            "id": 2,
            "title": "Tech Summit",
            "date": "2026-05-10",
            "location": "Innovation Hall",
            "guest_count": 150,
            "description": "Technology conference",
        },
        {
            "id": 3,
            "title": "Birthday Dinner",
            "date": "2026-05-20",
            "location": "Harbor Room",
            "guest_count": 15,
            "description": "Small dinner celebration",
        },
    ],
    "tasks": [
        {"id": 1, "event_id": 1, "title": "confirm catering", "completed": 0},
        {"id": 2, "event_id": 1, "title": "send invitations", "completed": 0},
        {"id": 3, "event_id": 2, "title": "finalize venue contract", "completed": 0},
        {"id": 4, "event_id": 3, "title": "book dessert tray", "completed": 0},
        {"id": 5, "event_id": 3, "title": "confirm guest list", "completed": 1},
    ],
}

GENERIC_PHRASES = [
    "break your event into milestones",
    "start with five basics",
    "estimate costs for venue, food, staff, supplies, and marketing",
    "i can help with venues, timelines, logistics, catering, vendors, and more",
]


def deep_copy_context(context):
    return json.loads(json.dumps(context))


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_question(text: str) -> bool:
    if "?" in text:
        return True
    lowered = normalize(text)
    starters = (
        "would you like",
        "do you have",
        "when is",
        "what type",
        "how many",
        "are you",
        "want me to",
        "should i",
        "do you want",
    )
    return any(starter in lowered for starter in starters)


def sentence_count(text: str) -> int:
    parts = [p.strip() for p in re.split(r"[.!?]+", text) if p.strip()]
    return len(parts)


def keyword_hits(response: str, required_keywords: list[str]) -> int:
    lowered = normalize(response)
    hits = 0
    for keyword in required_keywords:
        if normalize(keyword) in lowered:
            hits += 1
    return hits


def score_case(case: dict, response: str, detected_intent: str) -> tuple[int, list[str]]:
    notes = []
    score = 0

    expected_intent = case.get("expected_intent")
    if not expected_intent or detected_intent == expected_intent:
        score += 2
    else:
        notes.append(f"intent expected {expected_intent}, got {detected_intent}")

    required_keywords = case.get("required_keywords", [])
    if required_keywords:
        hits = keyword_hits(response, required_keywords)
        ratio = hits / max(len(required_keywords), 1)
        if ratio >= 0.75:
            score += 2
        elif ratio >= 0.34:
            score += 1
            notes.append(f"partial keyword coverage ({hits}/{len(required_keywords)})")
        else:
            notes.append(f"low keyword coverage ({hits}/{len(required_keywords)})")
    else:
        score += 2

    word_count = len(response.split())
    min_words = case.get("min_words", 20)
    min_sentences = case.get("min_sentences", 2)
    if word_count >= min_words and sentence_count(response) >= min_sentences:
        score += 2
    elif word_count >= max(12, min_words // 2):
        score += 1
        notes.append("response depth is only partial")
    else:
        notes.append("response too short")

    if case.get("requires_followup", False):
        if contains_question(response):
            score += 2
        else:
            notes.append("missing follow-up question")
    else:
        score += 2

    normalized_response = normalize(response)
    if any(phrase in normalized_response for phrase in map(normalize, GENERIC_PHRASES)):
        notes.append("contains old generic phrasing")
    else:
        score += 2

    return score, notes


def run_case(bot: UnifiedChatbot, case: dict):
    context = deep_copy_context(DEFAULT_CONTEXT)
    override_context = case.get("context")
    if override_context:
        context = override_context

    selected_event = None
    event_title = case.get("selected_event")
    if event_title:
        for event in context.get("events", []):
            if normalize(event.get("title", "")) == normalize(event_title):
                selected_event = event
                break

    message = case["input"]
    detected_intent, _ = bot.detect_intent_with_rules(message)
    response = bot.build_response(message, context=context, selected_event=selected_event)
    score, notes = score_case(case, response, detected_intent)

    passing_score = case.get("passing_score", 7)
    passed = score >= passing_score

    return {
        "input": message,
        "response": response,
        "expected_intent": case.get("expected_intent"),
        "actual_intent": detected_intent,
        "score": score,
        "passing_score": passing_score,
        "passed": passed,
        "notes": notes,
    }


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("cases", [])


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ai_quality_runner.py <dataset.json>")
        return

    dataset_path = Path(sys.argv[1])
    cases = load_cases(dataset_path)
    bot = UnifiedChatbot()

    results = []
    passed = 0
    for idx, case in enumerate(cases, start=1):
        result = run_case(bot, case)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} [{idx}/{len(cases)}] {result['input']}")
        print(f"  intent: {result['actual_intent']} | score: {result['score']}/{10}")
        print(f"  response: {result['response']}")
        if result["notes"]:
            print(f"  notes: {'; '.join(result['notes'])}")
        print()
        if result["passed"]:
            passed += 1

    summary = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "average_score": round(sum(r["score"] for r in results) / max(len(results), 1), 2),
        "results": results,
    }

    output_path = dataset_path.with_name(dataset_path.stem + "_results.json")
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"{passed}/{len(results)} passed")
    print(f"Average score: {summary['average_score']}/10")
    print(f"Saved detailed results to {output_path.name}")


if __name__ == "__main__":
    main()
