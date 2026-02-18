"""JSON API routes."""

from __future__ import annotations

import time

from flask import jsonify, request
from flask_login import current_user

import config
from models import get_user_banned_subs
from services.comment_formatter import format_comment_tree


def register_api_routes(app, reader) -> None:
    @app.route("/api/comments")
    def api_comments():
        try:
            subreddit_name = request.args.get("subreddit", "").strip()
            post_id = request.args.get("post_id", "").strip()
            limit = int(request.args.get("limit", 200))

            if not subreddit_name or not post_id:
                return jsonify({"error": "Missing subreddit or post_id"}), 400

            fetch_limit = max(limit, config.TOP_COMMENTS_FETCH_LIMIT)
            comments_payload = reader.fetch_post_comments(subreddit_name, post_id, limit=fetch_limit)
            comments_data = reader.parse_comments(comments_payload) if comments_payload else []
            time.sleep(config.RATE_LIMIT_DELAY)

            formatted_comments = format_comment_tree(comments_data, limit)
            return jsonify({"comments": formatted_comments})
        except Exception as exc:
            import traceback

            traceback.print_exc()
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/posts")
    def api_posts():
        subreddit_name = request.args.get("subreddit", "all").strip()
        sort = request.args.get("sort", config.DEFAULT_SORT)
        time_filter = request.args.get("t", "day")
        after = request.args.get("after", "").strip() or None
        limit = int(request.args.get("limit", config.DEFAULT_POST_LIMIT))

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
            if banned_subreddits:
                posts = [post for post in posts if post["subreddit"].lower() not in banned_subreddits]

        next_after = listing_data["data"].get("after") if listing_data and "data" in listing_data else None

        return jsonify(
            {
                "posts": posts,
                "after": next_after,
                "comments_limit": config.TOP_COMMENTS_PER_POST,
            }
        )
