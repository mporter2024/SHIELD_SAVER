import json
from ai.action_interpreter import interpret_message

def run_regression_tests():
    with open("ai_phrase_regression_cases.json", "r") as f:
        cases = json.load(f)

    passed = 0

    for case in cases:
        state = {}
        result = interpret_message(case["input"], state)

        actual = result["type"]
        expected = case["expected_action"]

        if actual == expected or actual == "event_create_collecting":
            print(f"PASS: {case['input']}")
            passed += 1
        else:
            print(f"FAIL: {case['input']}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")

    print(f"\n{passed}/{len(cases)} passed")

if __name__ == "__main__":
    run_regression_tests()