from flask import Blueprint, request, jsonify

# Blueprint for AI-related routes (recommendations, predictions, etc.)
ai_bp = Blueprint("ai", __name__)

@ai_bp.route("/suggestions", methods=["POST"])
def generate_suggestions():
    """
    Placeholder endpoint for AI event planning suggestions.
    Accepts user preferences and returns mock recommendations.
    Later, this will integrate with your machine learning model.
    """
    data = request.get_json()

    # Example mock logic (to replace with real AI later)
    preferences = data.get("preferences", [])
    mock_suggestions = [
        {"event_type": "Workshop", "location": "Library Conference Room"},
        {"event_type": "Social Mixer", "location": "Student Center"},
        {"event_type": "Fundraiser", "location": "Campus Courtyard"}
    ]

    return jsonify({
        "input_preferences": preferences,
        "suggestions": mock_suggestions
    })

@ai_bp.route("/status", methods=["GET"])
def ai_status():
    """Simple test endpoint to confirm AI module is reachable."""
    return jsonify({"status": "AI service operational"})
