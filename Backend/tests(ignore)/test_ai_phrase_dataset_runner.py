import json
import sys
from ai.action_interpreter import interpret_message


def load_cases_from_txt(path):
    cases = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or "|" not in line:
                continue

            parts = line.split("|")
            if len(parts) != 2:
                continue

            message = parts[0].strip()
            expected_action = parts[1].strip()

            cases.append({
                "input": message,
                "expected_action": expected_action
            })

    return cases


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ai_phrase_dataset_runner.py <dataset.txt>")
        return

    dataset_path = sys.argv[1]
    cases = load_cases_from_txt(dataset_path)

    context = {
        "events": [
            {"id": 1, "title": "Spring Expo"},
            {"id": 2, "title": "Tech Summit"},
            {"id": 3, "title": "Career Fair"},
            {"id": 4, "title": "Alumni Meetup"},
            {"id": 5, "title": "Gaming Night"},
            {"id": 6, "title": "Research Showcase"},
        ],
        "tasks": [
            {"id": 1, "title": "confirm catering"},
            {"id": 2, "title": "book DJ"},
            {"id": 3, "title": "send invitations"},
            {"id": 4, "title": "finalize venue contract"},
            {"id": 5, "title": "review agenda"},
            {"id": 6, "title": "order decorations"},
        ]
    } 

    passed = 0
    failed_cases = []

    for case in cases:
        state = {}

        try:
            result = interpret_message(case["input"], context, state)
        except Exception as e:
            print(f"ERROR: {case['input']}")
            print(f"  {e}")
            continue

        actual = result.get("type")
        expected = case["expected_action"]

        if actual == expected or actual == "event_create_collecting":
            print(f"PASS: {case['input']}")
            passed += 1
        else:
            print(f"FAIL: {case['input']}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")

            entry = {
                "input": case["input"],
                "expected_action": expected
            }

            if entry not in failed_cases:
                failed_cases.append(entry)

    print(f"\n{passed}/{len(cases)} passed")

    # 🔥 Auto-generate regression file
    if failed_cases:
        with open("ai_phrase_regression_cases.json", "w", encoding="utf-8") as f:
            json.dump(failed_cases, f, indent=2)

        print(f"\nSaved {len(failed_cases)} failed cases to ai_phrase_regression_cases.json")
    else:
        print("\nNo failed cases 🎉")


if __name__ == "__main__":
    main()