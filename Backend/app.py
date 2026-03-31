"""Flask application entry point for Spartan Shield Saver.

This file wires together configuration, database setup, and API routes.
Keeping the startup logic here makes it easier to understand where the app
is created and which blueprints are available.
"""

from flask import Flask
from flask_cors import CORS

from models.database import init_db
from routes.ai import ai_bp
from routes.agenda import agenda_bp
from routes.events import events_bp
from routes.tasks import tasks_bp
from routes.users import users_bp


def create_app() -> Flask:
    """Create and configure the Flask app."""
    app = Flask(__name__)
    app.config.from_pyfile("config.py")

    # Allow the frontend to send cookies/session data during local development.
    CORS(app, supports_credentials=True)

    # Ensure tables exist before handling requests.
    init_db(app)

    # Register API blueprints.
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(agenda_bp, url_prefix="/api/agenda")

    @app.get("/")
    def home():
        return {"message": "Welcome to the Event Planning API!"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
