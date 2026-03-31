lineup_bp = Blueprint("lineup", __name__)

@lineup_bp.route("/", methods=["POST"])
def add_lineup():
    db = get_db()
    data = request.json

    db.execute("""
        INSERT INTO lineup_items (agenda_item_id, name, role)
        VALUES (?, ?, ?)
    """, (
        data["agenda_item_id"],
        data["name"],
        data.get("role")
    ))

    db.commit()

    return jsonify({"message": "Added"}), 201


@lineup_bp.route("/<int:agenda_item_id>", methods=["GET"])
def get_lineup(agenda_item_id):
    db = get_db()

    lineup = db.execute("""
        SELECT * FROM lineup_items
        WHERE agenda_item_id = ?
    """, (agenda_item_id,)).fetchall()

    return jsonify([dict(row) for row in lineup])