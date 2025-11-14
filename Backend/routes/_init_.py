"""
Initialize all route blueprints for the Flask app.
This allows you to import routes easily inside app.py.
"""

from .events import events_bp
from .users import users_bp
from .ai import ai_bp
from .tasks import tasks_bp


# The __all__ list tells Python what can be imported
__all__ = ["events_bp", "users_bp", "ai_bp", "tasks_bp"]
