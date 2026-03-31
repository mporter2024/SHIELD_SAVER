from functools import wraps
from flask import request, jsonify

def admin_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        user_role = request.headers.get("X-User-Role")

        if user_role != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return route_function(*args, **kwargs)
    return wrapper