"""
We don't want to give dash all the creadit for the app magic, so we use the
underlying Flask app factory pattern to create and init our app and include
Dash as a rout into it.
See: https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/
"""

from flask import Flask

__version__ = '0.1.0'


def init_app():
    """Construct core Flask application."""
    app = Flask(__name__, instance_relative_config=False)

    with app.app_context():
        # Include our dash app. Import is needed here, because the init needs
        # the Flask app instance from app_context
        from .dashboard import init_dashboard
        app = init_dashboard(app)

        return app
