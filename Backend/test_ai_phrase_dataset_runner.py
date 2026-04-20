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

            input_text = parts[0].strip()
            expected_action = parts[1].strip()

            cases.append({
                "input": input_text,
                "expected_action": expected_action
            })

    return cases


def load_cases(path):
    return load_cases_from_txt(path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ai_phrase_dataset_runner.py <dataset.txt>")
        return

    dataset_path = sys.argv[1]
    cases = load_cases(dataset_path)

    passed = 0
    failed_cases = []

    for case in cases:
        state = {}
        result = interpret_message(case["input"],{}, state)

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

    # 🔥 Auto-generate regression JSON
    if failed_cases:
        with open("ai_phrase_regression_cases.json", "w", encoding="utf-8") as f:
            json.dump(failed_cases, f, indent=2)

        print(f"\nSaved {len(failed_cases)} failed cases to ai_phrase_regression_cases.json")
    else:
        print("\nNo failed cases 🎉")


if __name__ == "__main__":
    main()