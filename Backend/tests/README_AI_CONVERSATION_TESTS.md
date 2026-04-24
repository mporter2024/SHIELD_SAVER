# Spartan Shield-Saver AI Conversation Test Suite

This package gives you a reusable way to test your chatbot across many realistic multi-turn conversations instead of patching one interaction at a time.

## Files

- `ai_conversation_dataset_large.json` — 78 scenarios / 405 prompt turns.
- `test_ai_conversation_suite.py` — sends each prompt to your running Flask backend and checks the replies.

## How to use

1. Start your Flask backend normally.
2. In another terminal, run:

```bash
python test_ai_conversation_suite.py --dataset ai_conversation_dataset_large.json
```

For a quick smoke test:

```bash
python test_ai_conversation_suite.py --dataset ai_conversation_dataset_large.json --limit 10
```

The runner creates/logs into a test user, clears chat before each scenario, sends each message to:

```text
POST http://127.0.0.1:5000/api/ai/chat
```

Then it writes a report:

```text
ai_conversation_test_results.json
```

## What it checks

Each turn can define:

- `must_include`: phrases that should appear in the AI response.
- `must_not_include`: phrases that must not appear.
- global bad phrases like `No reply received`, `undefined`, `Traceback`, and `Internal Server Error`.

The dataset focuses on:

- event creation intent taking priority over catering/venue words
- follow-up guest count updates like “30 people”
- budget phrases like “my limit is,” “keep it under,” and “I can only spend”
- budget-aware catering recommendations
- partial provider names like “Doumar’s”
- vegetarian / dietary option requests
- starter task creation
- venue assignment
- budget generation not changing guest count unnecessarily
- fallback consistency so the AI always responds

## How to expand it

Add a new scenario object to `ai_conversation_dataset_large.json`:

```json
{
  "name": "my new scenario",
  "category": "budget",
  "turns": [
    {
      "user": "Create an event called Example Event for 20 people on May 1st",
      "must_include": ["Example Event", "created"],
      "must_not_include": ["No reply received"]
    }
  ]
}
```


