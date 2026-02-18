"""Authentication-related routes."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models import User


def register_auth_routes(app) -> None:
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = request.form.get("remember", False)

            if not username or not password:
                flash("Please fill in all fields.", "error")
                return render_template("login.html")

            user_data = User.get_by_username(username)
            if user_data and check_password_hash(user_data["password_hash"], password):
                user = User(user_data["id"], user_data["username"])
                login_user(user, remember=bool(remember))
                next_page = request.args.get("next")
                return redirect(next_page or url_for("index"))

            flash("Invalid username or password.", "error")

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm", "")

            if not username or not password:
                flash("Please fill in all fields.", "error")
                return render_template("register.html")
            if len(username) < 3:
                flash("Username must be at least 3 characters.", "error")
                return render_template("register.html")
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
                return render_template("register.html")
            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template("register.html")

            if User.create(username, password):
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))

            flash("Username already exists.", "error")

        return render_template("register.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))
