from flask import Flask
from models.database import init_db
from routes.events import events_bp
from routes.users import users_bp
from routes.ai import ai_bp

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.py')

    # Initialize the SQLite database
    init_db(app)

    # Register blueprints
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")

    @app.route('/')
    def home():
        return {"message": "Welcome to the Event Planning API!"}

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
