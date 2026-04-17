import sqlite3
from flask import current_app, g


def get_db():
    """Return a SQLite connection stored on the Flask app context."""
    if "db" not in g:
        db_path = current_app.config.get("DATABASE", "event_planner.db")
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_column(db, table_name, column_name, column_type):
    """Add a column if it does not already exist."""
    columns = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {column[1] for column in columns}
    if column_name not in existing:
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

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
    agenda_date TEXT,
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

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT,
    capacity INTEGER DEFAULT 0,
    price_tier TEXT,
    estimated_cost REAL DEFAULT 0,
    indoor_outdoor TEXT,
    venue_type TEXT,
    style TEXT,
    parking INTEGER DEFAULT 0,
    accessibility INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    phone TEXT,
    website TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS caterers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT,
    cuisine TEXT,
    price_tier TEXT,
    service_type TEXT,
    cost_per_person REAL DEFAULT 0,
    dietary_options TEXT,
    rating REAL DEFAULT 0,
    phone TEXT,
    website TEXT,
    description TEXT
);
"""


def init_db(app):
    """Create tables and apply lightweight schema migrations."""
    app.teardown_appcontext(close_db)

    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA_SQL)

        # Lightweight migrations for older databases.
        ensure_column(db, "users", "role", "TEXT NOT NULL DEFAULT 'user'")

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

        ensure_column(db, "agenda_items", "agenda_date", "TEXT")

        ensure_column(db, "venues", "city", "TEXT")
        ensure_column(db, "venues", "capacity", "INTEGER DEFAULT 0")
        ensure_column(db, "venues", "price_tier", "TEXT")
        ensure_column(db, "venues", "estimated_cost", "REAL DEFAULT 0")
        ensure_column(db, "venues", "indoor_outdoor", "TEXT")
        ensure_column(db, "venues", "venue_type", "TEXT")
        ensure_column(db, "venues", "style", "TEXT")
        ensure_column(db, "venues", "parking", "INTEGER DEFAULT 0")
        ensure_column(db, "venues", "accessibility", "INTEGER DEFAULT 0")
        ensure_column(db, "venues", "rating", "REAL DEFAULT 0")
        ensure_column(db, "venues", "phone", "TEXT")
        ensure_column(db, "venues", "website", "TEXT")
        ensure_column(db, "venues", "description", "TEXT")

        ensure_column(db, "caterers", "city", "TEXT")
        ensure_column(db, "caterers", "cuisine", "TEXT")
        ensure_column(db, "caterers", "price_tier", "TEXT")
        ensure_column(db, "caterers", "service_type", "TEXT")
        ensure_column(db, "caterers", "cost_per_person", "REAL DEFAULT 0")
        ensure_column(db, "caterers", "dietary_options", "TEXT")
        ensure_column(db, "caterers", "rating", "REAL DEFAULT 0")
        ensure_column(db, "caterers", "phone", "TEXT")
        ensure_column(db, "caterers", "website", "TEXT")
        ensure_column(db, "caterers", "description", "TEXT")

        seed_reference_data(db)
        db.commit()


def seed_reference_data(db):
    """Seed starter venue/caterer reference data if tables are empty."""
    from ai.local_data import venues as seed_venues, catering as seed_caterers

    venue_count = db.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    if venue_count == 0:
        for venue in seed_venues:
            db.execute(
                """
                INSERT INTO venues (
                    name, city, capacity, price_tier, estimated_cost, indoor_outdoor,
                    venue_type, style, parking, accessibility, rating, phone, website, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    venue.get("name"),
                    venue.get("city") or venue.get("location"),
                    int(venue.get("capacity") or 0),
                    venue.get("price_tier"),
                    float(venue.get("estimated_cost") or venue.get("cost") or 0),
                    venue.get("indoor_outdoor"),
                    venue.get("venue_type") or venue.get("type"),
                    venue.get("style"),
                    int(bool(venue.get("parking", False))),
                    int(bool(venue.get("accessibility", False))),
                    float(venue.get("rating") or 0),
                    venue.get("phone"),
                    venue.get("website"),
                    venue.get("description"),
                )
            )

    caterer_count = db.execute("SELECT COUNT(*) FROM caterers").fetchone()[0]
    if caterer_count == 0:
        for caterer in seed_caterers:
            dietary = caterer.get("dietary_options")
            if isinstance(dietary, list):
                dietary = ", ".join(dietary)

            db.execute(
                """
                INSERT INTO caterers (
                    name, city, cuisine, price_tier, service_type, cost_per_person,
                    dietary_options, rating, phone, website, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    caterer.get("name"),
                    caterer.get("city"),
                    caterer.get("cuisine") or caterer.get("type"),
                    caterer.get("price_tier"),
                    caterer.get("service_type") or caterer.get("type"),
                    float(caterer.get("cost_per_person") or 0),
                    dietary,
                    float(caterer.get("rating") or 0),
                    caterer.get("phone"),
                    caterer.get("website"),
                    caterer.get("description"),
                )
            )
