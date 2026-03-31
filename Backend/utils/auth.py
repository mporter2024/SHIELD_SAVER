from functools import wraps
from flask import jsonify, session


def admin_required(route_function):
    """Only allow logged-in admins to access a route."""
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401

        if session.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return route_function(*args, **kwargs)

    return wrapper
