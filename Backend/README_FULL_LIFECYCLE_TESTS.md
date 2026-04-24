# Expanded AI Conversation Full-Lifecycle Test Suite

This dataset is meant to test the AI across complete event-planning conversations instead of one-off interactions.

## What it covers

Each full lifecycle case includes:

- event creation
- event guest count update
- event location/venue update
- budget limit setting
- smart budget generation
- budget status check
- budget-aware catering recommendations
- catering assignment with full and partial names
- vegetarian and gluten-free filtering
- starter task creation
- custom task add, edit, complete, delete
- task status/listing follow-up
- timeline/agenda creation
- agenda edit and delete
- event summary
- paid venue affordability questions

Focused mutation cases also test event renaming, date/time changes, and event deletion.

## How to run

Put these files in your `Backend` folder, start Flask, then run:

```bash
python test_ai_conversation_suite.py --dataset ai_conversation_dataset_full_lifecycle.json --output ai_full_lifecycle_results.json
```

For a quick sample:

```bash
python test_ai_conversation_suite.py --dataset ai_conversation_dataset_full_lifecycle.json --limit 5
```

## Important note

This suite is intentionally stricter and broader than the earlier dataset. It is expected to reveal missing AI capabilities, especially around deleting/editing tasks and agenda items if those intents are not fully implemented yet.
