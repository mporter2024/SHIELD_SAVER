import sqlite3
from flask import g, current_app


def get_db():
    if "db" not in g:
        db_path = current_app.config.get("DATABASE", "event_planner.db")
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")

    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_column(db, table_name, column_name, column_type):
    columns = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {column[1] for column in columns}
    if column_name not in existing:
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def init_db(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
            role TEXT NOT NULL DEFAULT 'user'
        );

   columns = db.execute("PRAGMA table_info(users)").fetchall()
column_names = [column["name"] for column in columns]

if "role" not in column_names:
    db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")                      

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT,
            start_datetime TEXT,
            end_datetime TEXT,
            location TEXT,
            description TEXT,
            guest_count INTEGER DEFAULT 0,
            venue_cost REAL DEFAULT 0,
            food_cost_per_person REAL DEFAULT 0,
            decorations_cost REAL DEFAULT 0,
            equipment_cost REAL DEFAULT 0,
            staff_cost REAL DEFAULT 0,
            marketing_cost REAL DEFAULT 0,
            misc_cost REAL DEFAULT 0,
            contingency_percent REAL DEFAULT 0,
            budget_subtotal REAL DEFAULT 0,
            budget_contingency REAL DEFAULT 0,
            budget_total REAL DEFAULT 0,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            due_date TEXT,
            start_datetime TEXT,
            end_datetime TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );

        CREATE TABLE IF NOT EXISTS agenda_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );

        CREATE TABLE IF NOT EXISTS lineup_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agenda_item_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            role TEXT,
            FOREIGN KEY (agenda_item_id) REFERENCES agenda_items(id)
        );
        """)

        ensure_column(db, "events", "start_datetime", "TEXT")
        ensure_column(db, "events", "end_datetime", "TEXT")
        ensure_column(db, "events", "guest_count", "INTEGER DEFAULT 0")
        ensure_column(db, "events", "venue_cost", "REAL DEFAULT 0")
        ensure_column(db, "events", "food_cost_per_person", "REAL DEFAULT 0")
        ensure_column(db, "events", "decorations_cost", "REAL DEFAULT 0")
        ensure_column(db, "events", "equipment_cost", "REAL DEFAULT 0")
        ensure_column(db, "events", "staff_cost", "REAL DEFAULT 0")
        ensure_column(db, "events", "marketing_cost", "REAL DEFAULT 0")
        ensure_column(db, "events", "misc_cost", "REAL DEFAULT 0")
        ensure_column(db, "events", "contingency_percent", "REAL DEFAULT 0")
        ensure_column(db, "events", "budget_subtotal", "REAL DEFAULT 0")
        ensure_column(db, "events", "budget_contingency", "REAL DEFAULT 0")
        ensure_column(db, "events", "budget_total", "REAL DEFAULT 0")

        ensure_column(db, "tasks", "start_datetime", "TEXT")
        ensure_column(db, "tasks", "end_datetime", "TEXT")

        db.commit()
