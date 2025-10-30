# Flask + SQLite Backend Skeleton — Detailed Notes

## Overview
This document explains the backend structure and purpose of each file for the AI-powered Event Planning web app. It covers the Flask application setup, database handling, and modular route design.

---

## Folder Structure
```
backend/
│
├── app.py                ← Main entry point
├── config.py             ← App & DB configuration
│
├── models/
│   └── database.py       ← SQLite connection + table creation
│
└── routes/
    ├── __init__.py       ← Blueprint initialization
    ├── events.py         ← Event CRUD routes
    ├── users.py          ← User CRUD routes
    └── ai.py             ← AI placeholder routes
```

---

## app.py — Application Factory
### Purpose
The central hub that creates your Flask app, initializes the database, and registers modular routes (Blueprints).

### Key Points
- **create_app()**: Builds a new Flask app instance.
- **app.config.from_pyfile('config.py')**: Loads configuration settings.
- **init_db(app)**: Connects Flask with SQLite and creates tables if missing.
- **register_blueprint()**: Mounts route groups under URLs like `/api/events`.

### Code Flow
1. Flask instance created
2. Configuration loaded
3. Database initialized
4. Blueprints registered
5. App runs with debug mode for live reload

---

## config.py — Configuration Settings
### Purpose
Centralized place for defining paths, database names, and other constants.

### Key Lines
```python
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "event_planner.db")
```
- Keeps database path consistent.
- Makes it easy to change environments later (dev, test, prod).

---

## models/database.py — SQLite Management
### Purpose
Handles connecting to, initializing, and closing the SQLite database cleanly.

### Key Functions
- **get_db()** — Returns a per-request database connection via Flask’s `g` context.
- **close_db()** — Closes the DB connection after each request.
- **init_db(app)** — Creates tables for `users` and `events` if they don’t exist.

### Notes
- `row_factory = sqlite3.Row` → allows rows to behave like dicts.
- `app.teardown_appcontext(close_db)` → automatically closes DB connections.

---

## routes/__init__.py — Blueprint Registration
### Purpose
Makes the `routes/` folder a Python package and re-exports all blueprints for easy importing.

### Key Lines
```python
from .events import events_bp
from .users import users_bp
from .ai import ai_bp
__all__ = ["events_bp", "users_bp", "ai_bp"]
```
- Allows simple import syntax in `app.py`:  
  `from routes import events_bp, users_bp, ai_bp`

---

## routes/events.py — Event Routes
### Purpose
Handles all CRUD operations related to events.

### Endpoints
- **GET /** — Fetch all events.
- **POST /** — Create a new event with JSON data.

### Highlights
- Uses `get_db()` to query or insert into the events table.
- Returns responses as JSON with proper HTTP codes.

---

## routes/users.py — User Routes
### Purpose
Handles registration and retrieval of users.

### Endpoints
- **GET /** — Return all users.
- **POST /** — Create a user (name, email).
- **GET /<user_id>** — Fetch a single user by ID.

### Notes
- Uses parameterized SQL queries to prevent injection.
- Returns 404 when user not found.

---

## routes/ai.py — AI Placeholder Routes
### Purpose
Simulates the AI system for now; will later connect to a real ML model.

### Endpoints
- **POST /suggestions** — Accepts user preferences, returns mock event ideas.
- **GET /status** — Confirms the AI route is operational.

---

## Request Lifecycle
1. Client sends request to endpoint.
2. Flask routes it to correct Blueprint.
3. Route handler gets a DB connection from `get_db()`.
4. SQL is executed, response JSON created.
5. Flask auto-closes DB connection via `teardown_appcontext`.

---

## Testing Commands
### Create user
```bash
curl -X POST http://127.0.0.1:5000/api/users/   -H "Content-Type: application/json"   -d '{"name":"Micah Porter","email":"micah@example.com"}'
```
### Create event
```bash
curl -X POST http://127.0.0.1:5000/api/events/   -H "Content-Type: application/json"   -d '{"title":"Hackathon","date":"2025-11-12","location":"NSU Auditorium","description":"Coding event","user_id":1}'
```
### Ask AI for suggestions
```bash
curl -X POST http://127.0.0.1:5000/api/ai/suggestions   -H "Content-Type: application/json"   -d '{"preferences":["on-campus","networking"]}'
```

---

## Why This Design Works for Teams
| Design Choice | Benefit |
|----------------|----------|
| **Blueprints** | Keeps features isolated, avoids conflicts |
| **Factory pattern** | Easier testing and scaling |
| **SQLite via g** | Efficient, one connection per request |
| **config.py** | Single source of truth for settings |
| **AI placeholder** | Ready for future ML integration |

---

## Future Improvements
- Add **models/events_model.py** for cleaner SQL separation.
- Introduce **error handling middleware** (JSON error messages).
- Add **authentication** (JWT or sessions).
- Replace `executescript()` with **migrations** (Alembic).
- Integrate **AI model** logic inside `routes/ai.py`.
