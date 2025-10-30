from flask import Blueprint, request, jsonify
from models.database import get_db

events_bp = Blueprint("events", __name__)

@events_bp.route("/", methods=["GET"])
def get_events():
    db = get_db()
    events = db.execute("SELECT * FROM events").fetchall()
    return jsonify([dict(row) for row in events])

@events_bp.route("/", methods=["POST"])
def create_event():
    data = request.get_json()
    db = get_db()
    db.execute(
        "INSERT INTO events (title, date, location, description, user_id) VALUES (?, ?, ?, ?, ?)",
        (data["title"], data["date"], data["location"], data["description"], data["user_id"])
    )
    db.commit()
    return jsonify({"message": "Event created successfully"}), 201
