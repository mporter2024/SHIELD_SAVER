# AI quality testing patch

This patch adds a second test runner for your chatbot's **response quality**.



## Included files
- `test_ai_quality_runner.py`
- `ai_quality_test_dataset.json`

## What it scores
Each response is scored out of 10 using simple heuristics:
- intent alignment
- required keyword coverage
- depth / minimum length
- follow-up question presence
- penalty for old canned phrasing

## Run it
```bash
cd Backend
python test_ai_quality_runner.py ai_quality_test_dataset.json
```

## Output
It prints PASS/FAIL per case and writes a detailed JSON report next to the dataset:
- `ai_quality_test_dataset_results.json`

## Why this is the next best step
This gives you a second lane of testing:
1. **Action correctness** with your existing runner
2. **Advice quality** with the new runner

That means you can improve the AI's conversational responses without breaking your current event/task command tests.
