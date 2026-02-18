"""Helpers for building post view models from Reddit payloads."""

from __future__ import annotations

from typing import Any


def build_post_view_model(post_data: dict[str, Any], media: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Reddit post payload into template/API friendly fields."""
    return {
        "title": post_data.get("title", ""),
        "author": post_data.get("author", "[deleted]"),
        "subreddit": post_data.get("subreddit", ""),
        "score": post_data.get("score", 0),
        "num_comments": post_data.get("num_comments", 0),
        "url": post_data.get("url", ""),
        "permalink": f"https://reddit.com{post_data.get('permalink', '')}",
        "created_utc": post_data.get("created_utc", 0),
        "selftext": post_data.get("selftext", ""),
        "is_self": post_data.get("is_self", False),
        "id": post_data.get("id", ""),
        "image_url": media["image_url"],
        "is_video": media["is_video"],
        "video_url": media["video_url"],
        "audio_url": media["audio_url"],
        "hls_url": media["hls_url"],
        "gallery_urls": media["gallery_urls"],
    }
