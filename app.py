"""Reddit Reader Flask application bootstrap."""

from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask
from flask_wtf import CSRFProtect
from flask_login import LoginManager

import config
from filters import register_filters
from models import User, init_db
from reddit_reader import RedditReader
from routes.api_routes import register_api_routes
from routes.auth_routes import register_auth_routes
from routes.content_routes import register_content_routes
from routes.context import register_context_processors
from routes.error_routes import register_error_handlers
from routes.settings_routes import register_settings_routes


def create_app() -> Flask:

    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(
        seconds=config.REMEMBER_COOKIE_DURATION
    )
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # Optional: disables CSRF token expiration

    csrf = CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(int(user_id))

    register_filters(app)
    register_context_processors(app)

    reader = RedditReader(user_agent=config.USER_AGENT)
    register_auth_routes(app)
    register_settings_routes(app)
    register_content_routes(app, reader)
    register_api_routes(app, reader)
    register_error_handlers(app)

    init_db()
    return app


app = create_app()


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
