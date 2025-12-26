import sqlite3
from flask import g, current_app

def get_db():
    if "db" not in g:
        db_path = current_app.config.get("DATABASE", "event_planner.db")
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row

        # Enforce FK constraints in SQLite (off by default)
        g.db.execute("PRAGMA foreign_keys = ON;")

    return g.db


def close_db(e=None):
    db = g.pop("db", None)  # <-- key matches if "db" in g
    if db is not None:
        db.close()


def init_db(app):
    # Close DB connection at end of each request
    app.teardown_appcontext(close_db)

    # Create tables if they don’t exist
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT,
            location TEXT,
            description TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            due_date TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );
        """)
        db.commit()
