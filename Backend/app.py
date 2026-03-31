from flask import Flask
from flask_cors import CORS
from models.database import init_db
from routes.ai import ai_bp
from routes.agenda import agenda_bp
from routes.events import events_bp
from routes.tasks import tasks_bp
from routes.users import users_bp


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile("config.py")

    CORS(app, supports_credentials=True)
    init_db(app)

    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(agenda_bp, url_prefix="/api/agenda")

    @app.route("/")
    def home():
        return {"message": "Welcome to the Event Planning API!"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
