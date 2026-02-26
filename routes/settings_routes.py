"""User settings and subreddit preference routes."""

from __future__ import annotations

from flask import redirect, render_template, request, url_for, jsonify, session
from flask_login import current_user, login_required

from services.user_settings_service import (
    get_user_settings,
    normalize_subreddit_name,
    save_user_settings,
)
from forms import (
    AddSubForm,
    ReorderForm,
    RemoveSubForm,
    UnbanForm,
    SidebarForm,
    PlaybackForm,
    BehaviorForm,
)
import time


def register_settings_routes(app) -> None:
    @app.route("/settings/update", methods=["POST"])
    @login_required
    def update_setting():
        # single-field AJAX updates with lightweight rate limiting
        # CSRF token should be sent via header X-CSRFToken (handled by CSRFProtect)
        now = time.time()
        last = session.get("last_setting_update", 0)
        if now - last < 0.5:  # half-second throttle
            return jsonify(success=False, error="rate_limited"), 429
        session["last_setting_update"] = now

        data = request.get_json() or {}
        field = data.get("field")
        value = data.get("value")
        if field is None:
            return jsonify(success=False, error="missing_field"), 400

        settings = get_user_settings(current_user.id)
        if field == "sidebar_position":
            settings.sidebar_position = value
        elif field == "default_volume":
            try:
                settings.default_volume = max(0, min(100, int(value)))
            except Exception:
                pass
        elif field == "default_speed":
            try:
                settings.default_speed = max(0.25, min(2.0, float(value)))
            except Exception:
                pass
        elif field == "title_links":
            settings.title_links = str(value).lower() in ("true", "1", "on")
        else:
            return jsonify(success=False, error="unknown_field"), 400

        save_user_settings(current_user.id, settings)
        return jsonify(success=True)

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        user_settings = get_user_settings(current_user.id)

        form = None
        if request.method == "POST":
            action = request.form.get("intent")
            # choose the form class based on action
            if action == "add":
                form = AddSubForm()
            elif action == "reorder":
                form = ReorderForm()
            elif action == "remove":
                form = RemoveSubForm()
            elif action == "unban":
                form = UnbanForm()
            elif action == "save_sidebar":
                form = SidebarForm()
            elif action == "save_playback":
                form = PlaybackForm()
            elif action == "save_behavior":
                form = BehaviorForm()
            # quick-add uses same "add" action as normal pinned add

            if form and form.validate_on_submit():
                # handle each action using form data
                if action == "add":
                    subreddit_name = normalize_subreddit_name(form.sub.data or "")
                    if subreddit_name and subreddit_name not in user_settings.pinned_subs:
                        user_settings.pinned_subs.append(subreddit_name)
                elif action == "remove":
                    subreddit_name = normalize_subreddit_name(form.sub.data or "")
                    if subreddit_name in user_settings.pinned_subs:
                        user_settings.pinned_subs.remove(subreddit_name)
                elif action == "reorder":
                    new_order = form.order.data or ""
                    if new_order:
                        user_settings.pinned_subs = [sub.strip() for sub in new_order.split(",") if sub.strip()]
                elif action == "unban":
                    subreddit_name = normalize_subreddit_name(form.sub.data or "")
                    if subreddit_name in user_settings.banned_subs:
                        user_settings.banned_subs.remove(subreddit_name)
                elif action == "save_playback":
                    user_settings.default_volume = max(0, min(100, form.default_volume.data or 5))
                    user_settings.default_speed = max(0.25, min(2.0, float(form.default_speed.data or 1.0)))
                elif action == "save_sidebar":
                    user_settings.sidebar_position = form.sidebar_position.data or "left"
                elif action == "save_behavior":
                    user_settings.title_links = bool(form.title_links.data)
                # quick-add handled by same "add" case above

                save_user_settings(current_user.id, user_settings)
                return redirect(url_for("settings"))

        # create fresh/unbound forms for rendering
        add_form = AddSubForm()
        reorder_form = ReorderForm()
        remove_form = RemoveSubForm()
        unban_form = UnbanForm()
        sidebar_form = SidebarForm(sidebar_position=user_settings.sidebar_position)
        playback_form = PlaybackForm(
            default_volume=user_settings.default_volume,
            default_speed=str(user_settings.default_speed),
        )
        behavior_form = BehaviorForm(title_links=user_settings.title_links)

        return render_template(
            "settings.html",
            pinned_subs=user_settings.pinned_subs,
            banned_subs=user_settings.banned_subs,
            default_volume=user_settings.default_volume,
            default_speed=user_settings.default_speed,
            sidebar_position=user_settings.sidebar_position,
            title_links=user_settings.title_links,
            add_form=add_form,
            reorder_form=reorder_form,
            remove_form=remove_form,
            unban_form=unban_form,
            sidebar_form=sidebar_form,
            playback_form=playback_form,
            behavior_form=behavior_form,
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
