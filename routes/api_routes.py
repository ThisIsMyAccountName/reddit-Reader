"""JSON API routes."""

from __future__ import annotations

import logging
from urllib.parse import unquote

import requests
from services.cache import ThreadSafeTTLCache
from services.download_service import (
    build_default_filename,
    is_allowed_media_url,
    parse_allowed_media_hosts,
    sanitize_filename,
)

from flask import Response, jsonify, request, stream_with_context
from flask_login import current_user

import config
from models import get_user_banned_subs
from services.comment_formatter import format_comment_tree
from services.user_settings_service import filter_banned_posts

logger = logging.getLogger(__name__)


def register_api_routes(app, reader) -> None:
    # Thread-safe TTL LRU cache for autocomplete responses
    _autocomplete_cache = ThreadSafeTTLCache(maxsize=config.AUTOCOMPLETE_CACHE_MAXSIZE, ttl=config.AUTOCOMPLETE_CACHE_TTL)
    _allowed_hosts = parse_allowed_media_hosts(config.DOWNLOAD_ALLOWED_MEDIA_HOSTS)

    def _iter_upstream_chunks(upstream_response: requests.Response, chunk_size: int = 64 * 1024):
        try:
            for chunk in upstream_response.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        finally:
            upstream_response.close()

    @app.route("/api/comments")
    def api_comments():
        try:
            subreddit_name = request.args.get("subreddit", "").strip()
            post_id = request.args.get("post_id", "").strip()
            limit = min(int(request.args.get("limit", 200)), 500)

            if not subreddit_name or not post_id:
                return jsonify({"error": "Missing subreddit or post_id"}), 400

            fetch_limit = max(limit, config.TOP_COMMENTS_FETCH_LIMIT)
            comments_payload = reader.fetch_post_comments(subreddit_name, post_id, limit=fetch_limit)
            comments_data = reader.parse_comments(comments_payload) if comments_payload else []

            formatted_comments = format_comment_tree(comments_data, limit)
            return jsonify({"comments": formatted_comments})
        except Exception as exc:
            logger.exception("Error in /api/comments")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/posts")
    def api_posts():
        subreddit_name = request.args.get("subreddit", "all").strip()
        sort = request.args.get("sort", config.DEFAULT_SORT)
        time_filter = request.args.get("t", "day")
        after = request.args.get("after", "").strip() or None
        limit = min(int(request.args.get("limit", config.DEFAULT_POST_LIMIT)), config.MAX_POSTS_PER_REQUEST)

        listing_data = reader.fetch_subreddit(
            subreddit_name,
            sort=sort,
            limit=limit,
            after=after,
            t=time_filter if sort == "top" else None,
        )
        posts = reader.parse_posts(listing_data) if listing_data else []

        if current_user.is_authenticated:
            banned_subreddits = get_user_banned_subs(current_user.id)
            posts = filter_banned_posts(posts, banned_subreddits)

        next_after = listing_data["data"].get("after") if listing_data and "data" in listing_data else None

        return jsonify(
            {
                "posts": posts,
                "after": next_after,
                "comments_limit": config.TOP_COMMENTS_PER_POST,
            }
        )

    @app.route("/api/subreddit_autocomplete")
    def api_subreddit_autocomplete():
        try:
            q = (request.args.get("q") or "").strip()
            if not q:
                return jsonify({"results": []})

            limit = min(int(request.args.get("limit", 8)), 25)

            cache_key = (q.lower(), limit)
            cached = _autocomplete_cache.get(cache_key)
            if cached is not None:
                return jsonify({"results": cached})

            data = reader.fetch_subreddit_autocomplete(q, limit=limit) or []

            _autocomplete_cache.set(cache_key, data)

            return jsonify({"results": data})
        except Exception as exc:
            logger.exception("Error in /api/subreddit_autocomplete")
            return jsonify({"results": []}), 500

    @app.route("/api/download")
    def api_download():
        source_url = (request.args.get("url") or "").strip()
        requested_filename = (request.args.get("filename") or "").strip()
        title_hint = (request.args.get("title") or "").strip()
        post_id_hint = (request.args.get("post_id") or "").strip()

        if not source_url:
            return jsonify({"error": "Missing url parameter"}), 400

        source_url = unquote(source_url)
        if not is_allowed_media_url(source_url, _allowed_hosts):
            return jsonify({"error": "Media URL is not allowed"}), 400

        filename = sanitize_filename(requested_filename, fallback="") if requested_filename else ""
        if not filename:
            filename = build_default_filename(title_hint, post_id_hint, source_url)

        try:
            upstream = reader.session.get(
                source_url,
                headers=reader.headers,
                stream=True,
                timeout=config.REQUEST_TIMEOUT,
            )

            if upstream.status_code >= 400:
                status_code = upstream.status_code if upstream.status_code < 500 else 502
                upstream.close()
                return jsonify({"error": f"Upstream media request failed ({upstream.status_code})"}), status_code

            content_type = upstream.headers.get("Content-Type", "application/octet-stream")
            content_length = upstream.headers.get("Content-Length")

            response = Response(
                stream_with_context(_iter_upstream_chunks(upstream)),
                content_type=content_type,
            )
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            response.headers["Cache-Control"] = "no-store"
            if content_length and content_length.isdigit():
                response.headers["Content-Length"] = content_length
            return response
        except requests.RequestException as exc:
            logger.warning("Download proxy failed for %s: %s", source_url, exc)
            return jsonify({"error": "Failed to fetch media from upstream source"}), 502
