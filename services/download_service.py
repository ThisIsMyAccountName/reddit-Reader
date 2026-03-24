"""Helpers for media download validation and metadata generation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_ALLOWED_MEDIA_HOSTS: tuple[str, ...] = (
    "reddit.com",
    "redd.it",
    "redditmedia.com",
)

_INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MULTI_DASH = re.compile(r"-+")


def _host_matches_suffix(hostname: str, suffix: str) -> bool:
    return hostname == suffix or hostname.endswith(f".{suffix}")


def parse_allowed_media_hosts(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_ALLOWED_MEDIA_HOSTS
    hosts = [h.strip().lower() for h in value.split(",") if h.strip()]
    return tuple(hosts) if hosts else DEFAULT_ALLOWED_MEDIA_HOSTS


def is_allowed_media_url(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    return any(_host_matches_suffix(hostname, suffix) for suffix in allowed_hosts)


def guess_extension_from_url(url: str, fallback: str = "bin") -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower().lstrip(".")
    if ext:
        return ext
    return fallback


def sanitize_filename(filename: str, fallback: str = "media.bin") -> str:
    candidate = (filename or "").strip()
    if not candidate:
        return fallback

    candidate = candidate.replace(" ", "-")
    candidate = _INVALID_FILENAME_CHARS.sub("-", candidate)
    candidate = _MULTI_DASH.sub("-", candidate).strip("-._")
    return candidate or fallback


def slugify_title(title: str, fallback: str = "post") -> str:
    raw = (title or "").strip().lower()
    raw = raw.replace(" ", "-")
    raw = _INVALID_FILENAME_CHARS.sub("-", raw)
    raw = _MULTI_DASH.sub("-", raw).strip("-")
    return raw or fallback


def build_default_filename(title: str, post_id: str, source_url: str) -> str:
    extension = guess_extension_from_url(source_url, fallback="bin")
    slug = slugify_title(title)
    pid = sanitize_filename(post_id or "post", fallback="post")
    return sanitize_filename(f"{slug}-{pid}.{extension}", fallback=f"post-{pid}.{extension}")


def get_download_source(media: dict) -> tuple[str, str] | tuple[None, None]:
    if media.get("is_video") and media.get("video_url"):
        return "video", media["video_url"]
    if media.get("image_url"):
        return "image", media["image_url"]

    gallery_urls = media.get("gallery_urls") or []
    if gallery_urls:
        return "gallery", gallery_urls[0]

    return None, None


def build_download_metadata(post_data: dict, media: dict) -> dict:
    kind, source_url = get_download_source(media)
    has_downloadable_media = bool(source_url)

    suggested_filename = ""
    if has_downloadable_media:
        suggested_filename = build_default_filename(
            title=post_data.get("title", ""),
            post_id=post_data.get("id", ""),
            source_url=source_url,
        )

    return {
        "has_downloadable_media": has_downloadable_media,
        "download_kind": kind or "",
        "download_url": source_url or "",
        "download_filename": suggested_filename,
    }
