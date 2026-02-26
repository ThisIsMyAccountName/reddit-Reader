"""Authentication-related routes."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models import User
from forms import LoginForm, RegisterForm


def register_auth_routes(app) -> None:
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        form = LoginForm()
        if form.validate_on_submit():
            username = form.username.data.strip()
            password = form.password.data
            remember = form.remember.data

            user_data = User.get_by_username(username)
            if user_data and check_password_hash(user_data["password_hash"], password):
                user = User(user_data["id"], user_data["username"])
                login_user(user, remember=bool(remember))
                next_page = request.args.get("next")
                return redirect(next_page or url_for("index"))

            flash("Invalid username or password.", "error")

        return render_template("login.html", form=form)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        form = RegisterForm()
        if form.validate_on_submit():
            username = form.username.data.strip()
            password = form.password.data
            confirm_password = form.confirm.data

            if password != confirm_password:
                flash("Passwords do not match.", "error")
            else:
                if User.create(username, password):
                    flash("Account created! Please log in.", "success")
                    return redirect(url_for("login"))
                flash("Username already exists.", "error")

        return render_template("register.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))
