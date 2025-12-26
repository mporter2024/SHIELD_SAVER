from flask import Blueprint, request, jsonify
from models.database import get_db
import sqlite3

# Blueprint for user-related endpoints
users_bp = Blueprint("users", __name__)

@users_bp.get("/")
def get_users():
    """Return a list of all registered users."""
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    return jsonify([dict(row) for row in users]), 200


@users_bp.post("/")
def create_user():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    db = get_db()

    name = data.get("name")
    email = data.get("email")

    # Basic validation
    missing = [k for k in ("name", "email") if not data.get(k)]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    try:
        db.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)",
            (name, email)
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        # If you later add UNIQUE(email), this will return a clean error instead of 500
        return jsonify({"error": "Database constraint failed", "details": str(e)}), 400

    return jsonify({"message": "User created successfully"}), 201


@users_bp.get("/<int:user_id>")
def get_user(user_id):
    """Retrieve a single user by ID."""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user)), 200

