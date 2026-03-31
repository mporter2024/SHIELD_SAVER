from flask import Blueprint, jsonify, request, session
from models.database import get_db
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

users_bp = Blueprint("users", __name__)


@users_bp.get("/")
def get_users():
    db = get_db()
    users = db.execute("SELECT id, name, username, email, role FROM users").fetchall()
    return jsonify([dict(row) for row in users]), 200


@users_bp.post("/")
def create_user():
    data = request.get_json(silent=True) or {}
    db = get_db()

    name = (data.get("name") or "").strip()
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    missing = [k for k, v in {"name": name, "username": username, "email": email, "password": password}.items() if not v]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    hashed_password = generate_password_hash(password)

    try:
        db.execute(
            "INSERT INTO users (name, username, email, password, role) VALUES (?, ?, ?, ?, ?)",
            (name, username, email, hashed_password, "user"),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return jsonify({"error": "Database constraint failed", "details": str(e)}), 400

    return jsonify({"message": "User created successfully"}), 201


@users_bp.post("/login")
def login_user():
    data = request.get_json(silent=True) or {}
    db = get_db()

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if user is None or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["name"] = user["name"]
    session["role"] = user["role"]

    return jsonify(
        {
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
            },
        }
    ), 200


@users_bp.get("/<int:user_id>")
def get_user(user_id):
    db = get_db()
    user = db.execute(
        "SELECT id, name, username, email, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(dict(user)), 200


@users_bp.get("/me")
def get_current_user():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    db = get_db()
    user = db.execute(
        "SELECT id, name, username, email, role FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    if user is None:
        session.clear()
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": dict(user)}), 200


@users_bp.post("/logout")
def logout_user():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200
