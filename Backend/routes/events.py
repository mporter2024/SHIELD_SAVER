from flask import Blueprint, request, jsonify
from models.database import get_db

events_bp = Blueprint("events", __name__)

@events_bp.route("/", methods=["POST"])
def create_event():
    data = request.get_json(silent=True) or {}

    required = ["title", "date", "location", "description", "user_id"]
    missing = [k for k in required if not data.get(k)]

    if missing:
        return jsonify({
            "error": "Missing required fields",
            "missing": missing
        }), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, date, location, description, user_id)
        VALUES (?, ?, ?, ?, ?)
    """, (data["title"], data["date"], data["location"], data["description"], data["user_id"]))
    db.commit()

    return jsonify({"message": "Event created successfully"}), 201
