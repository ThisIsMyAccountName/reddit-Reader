"""Template context processors."""

from __future__ import annotations

from flask import request
from flask_login import current_user

from services.user_settings_service import get_user_settings


def register_context_processors(app) -> None:
    @app.context_processor
    def inject_user_settings():
        context = {
            "pinned_subs": [],
            "banned_subs": [],
            "feed_pinned_subs": [],
            "is_subreddit_page": False,
            "default_volume": 5,
            "default_speed": 1.0,
            "sidebar_position": "left",
            "title_links": True,
        }

        if request.endpoint in ("subreddit", "comments"):
            context["is_subreddit_page"] = True

        if current_user.is_authenticated:
            settings = get_user_settings(current_user.id)
            context.update(
                {
                    "pinned_subs": settings.pinned_subs,
                    "banned_subs": settings.banned_subs,
                    "feed_pinned_subs": settings.feed_pinned_subs,
                    "default_volume": settings.default_volume,
                    "default_speed": settings.default_speed,
                    "sidebar_position": settings.sidebar_position,
                    "title_links": settings.title_links,
                }
            )

        return context
