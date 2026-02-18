"""Error handlers."""

from flask import render_template


def register_error_handlers(app) -> None:
    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="Page not found"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", message="Server error occurred"), 500
