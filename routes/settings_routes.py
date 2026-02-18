"""User settings and subreddit preference routes."""

from __future__ import annotations

from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required

from services.user_settings_service import (
    get_user_settings,
    normalize_subreddit_name,
    save_user_settings,
)


def register_settings_routes(app) -> None:
    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        user_settings = get_user_settings(current_user.id)

        if request.method == "POST":
            action = request.form.get("action")
            subreddit_name = normalize_subreddit_name(request.form.get("sub", ""))

            if action == "add" and subreddit_name and subreddit_name not in user_settings.pinned_subs:
                user_settings.pinned_subs.append(subreddit_name)
            elif action == "remove" and subreddit_name in user_settings.pinned_subs:
                user_settings.pinned_subs.remove(subreddit_name)
            elif action == "move_up" and subreddit_name in user_settings.pinned_subs:
                index = user_settings.pinned_subs.index(subreddit_name)
                if index > 0:
                    user_settings.pinned_subs[index], user_settings.pinned_subs[index - 1] = (
                        user_settings.pinned_subs[index - 1],
                        user_settings.pinned_subs[index],
                    )
            elif action == "move_down" and subreddit_name in user_settings.pinned_subs:
                index = user_settings.pinned_subs.index(subreddit_name)
                if index < len(user_settings.pinned_subs) - 1:
                    user_settings.pinned_subs[index], user_settings.pinned_subs[index + 1] = (
                        user_settings.pinned_subs[index + 1],
                        user_settings.pinned_subs[index],
                    )
            elif action == "save_playback":
                user_settings.default_volume = max(0, min(100, int(request.form.get("default_volume", 5))))
                user_settings.default_speed = max(0.25, min(2.0, float(request.form.get("default_speed", 1.0))))
            elif action == "save_sidebar":
                user_settings.sidebar_position = request.form.get("sidebar_position", "left")
            elif action == "reorder":
                new_order = request.form.get("order", "")
                if new_order:
                    user_settings.pinned_subs = [sub.strip() for sub in new_order.split(",") if sub.strip()]
            elif action == "unban" and subreddit_name in user_settings.banned_subs:
                user_settings.banned_subs.remove(subreddit_name)
            elif action == "save_behavior":
                user_settings.title_links = request.form.get("title_links") in ("on", "1", "true")

            save_user_settings(current_user.id, user_settings)
            return redirect(url_for("settings"))

        return render_template(
            "settings.html",
            pinned_subs=user_settings.pinned_subs,
            banned_subs=user_settings.banned_subs,
            default_volume=user_settings.default_volume,
            default_speed=user_settings.default_speed,
            sidebar_position=user_settings.sidebar_position,
        )

    @app.route("/ban/<subreddit>", methods=["POST"])
    @login_required
    def ban_subreddit(subreddit):
        subreddit_name = normalize_subreddit_name(subreddit)
        if not subreddit_name:
            return redirect(request.referrer or url_for("index"))

        user_settings = get_user_settings(current_user.id)
        if subreddit_name not in user_settings.banned_subs:
            user_settings.banned_subs.append(subreddit_name)
            save_user_settings(current_user.id, user_settings)

        return redirect(request.referrer or url_for("index"))

    @app.route("/pin/<subreddit>", methods=["POST"])
    @login_required
    def pin_subreddit(subreddit):
        subreddit_name = normalize_subreddit_name(subreddit)
        if not subreddit_name:
            return redirect(request.referrer or url_for("index"))

        user_settings = get_user_settings(current_user.id)
        if subreddit_name not in user_settings.pinned_subs:
            user_settings.pinned_subs.append(subreddit_name)
            user_settings.feed_pinned_subs.append(subreddit_name)
            save_user_settings(current_user.id, user_settings)

        return redirect(request.referrer or url_for("index"))

    @app.route("/unpin/<subreddit>", methods=["POST"])
    @login_required
    def unpin_subreddit(subreddit):
        subreddit_name = normalize_subreddit_name(subreddit)
        if not subreddit_name:
            return redirect(request.referrer or url_for("index"))

        user_settings = get_user_settings(current_user.id)
        if subreddit_name in user_settings.feed_pinned_subs:
            if subreddit_name in user_settings.pinned_subs:
                user_settings.pinned_subs.remove(subreddit_name)
            user_settings.feed_pinned_subs.remove(subreddit_name)
            save_user_settings(current_user.id, user_settings)

        return redirect(request.referrer or url_for("index"))
