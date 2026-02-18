"""User settings persistence and mapping helpers."""

from __future__ import annotations

from dataclasses import dataclass

from models import get_db


@dataclass
class UserSettings:
    pinned_subs: list[str]
    banned_subs: list[str]
    feed_pinned_subs: list[str]
    default_volume: int
    default_speed: float
    sidebar_position: str
    title_links: bool


_ALLOWED_SIDEBAR_POSITIONS = {"left", "right", "off"}


def _parse_subreddit_csv(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [sub.strip() for sub in raw_value.split(",") if sub.strip()]


def _serialize_subreddit_list(subreddits: list[str]) -> str:
    return ",".join(subreddits)


def get_user_settings(user_id: int) -> UserSettings:
    conn = get_db()
    row = conn.execute(
        "SELECT pinned_subs, banned_subs, default_volume, default_speed, sidebar_position, feed_pinned_subs, title_links "
        "FROM user_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if not row:
        return UserSettings([], [], [], 5, 1.0, "left", True)

    return UserSettings(
        pinned_subs=_parse_subreddit_csv(row["pinned_subs"]),
        banned_subs=_parse_subreddit_csv(row["banned_subs"]),
        feed_pinned_subs=_parse_subreddit_csv(row["feed_pinned_subs"]),
        default_volume=row["default_volume"] if row["default_volume"] is not None else 5,
        default_speed=row["default_speed"] if row["default_speed"] is not None else 1.0,
        sidebar_position=row["sidebar_position"] or "left",
        title_links=bool(row["title_links"]) if row["title_links"] is not None else True,
    )


def save_user_settings(user_id: int, settings: UserSettings) -> None:
    if settings.sidebar_position not in _ALLOWED_SIDEBAR_POSITIONS:
        settings.sidebar_position = "left"

    conn = get_db()
    conn.execute(
        """
        INSERT INTO user_settings (user_id, pinned_subs, banned_subs, default_volume, default_speed, sidebar_position, title_links, feed_pinned_subs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            pinned_subs = excluded.pinned_subs,
            banned_subs = excluded.banned_subs,
            default_volume = excluded.default_volume,
            default_speed = excluded.default_speed,
            sidebar_position = excluded.sidebar_position,
            title_links = excluded.title_links,
            feed_pinned_subs = excluded.feed_pinned_subs
        """,
        (
            user_id,
            _serialize_subreddit_list(settings.pinned_subs),
            _serialize_subreddit_list(settings.banned_subs),
            settings.default_volume,
            settings.default_speed,
            settings.sidebar_position,
            1 if settings.title_links else 0,
            _serialize_subreddit_list(settings.feed_pinned_subs),
        ),
    )
    conn.commit()
    conn.close()


def normalize_subreddit_name(subreddit: str) -> str:
    return subreddit.strip().lstrip("r/").lower()
