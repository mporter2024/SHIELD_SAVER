from flask import Blueprint, request, jsonify
from models.database import get_db

agenda_bp = Blueprint("agenda", __name__)

# Create agenda item
@agenda_bp.route("/", methods=["POST"])
def create_agenda_item():
    db = get_db()
    data = request.json

    cursor = db.execute("""
        INSERT INTO agenda_items (event_id, title, description, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["event_id"],
        data["title"],
        data.get("description"),
        data["start_time"],
        data["end_time"]
    ))

    db.commit()

    return jsonify({"id": cursor.lastrowid}), 201


# Get agenda for event
@agenda_bp.route("/<int:event_id>", methods=["GET"])
def get_agenda(event_id):
    db = get_db()

    agenda = db.execute("""
        SELECT * FROM agenda_items
        WHERE event_id = ?
        ORDER BY start_time
    """, (event_id,)).fetchall()

    return jsonify([dict(row) for row in agenda])