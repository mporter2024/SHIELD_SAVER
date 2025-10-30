from flask import Blueprint, request, jsonify
from models.database import get_db

# Blueprint for user-related endpoints
users_bp = Blueprint("users", __name__)

@users_bp.route("/", methods=["GET"])
def get_users():
    """Return a list of all registered users."""
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    return jsonify([dict(row) for row in users])

@users_bp.route("/", methods=["POST"])
def create_user():
    """Register a new user."""
    data = request.get_json()
    db = get_db()
    db.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        (data["name"], data["email"])
    )
    db.commit()
    return jsonify({"message": "User created successfully"}), 201

@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Retrieve a single user by ID."""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user))
