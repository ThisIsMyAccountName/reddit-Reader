"""Main content browsing routes."""

from __future__ import annotations

from flask import redirect, render_template, request, url_for
from flask_login import current_user

import config
from models import get_user_banned_subs
from services.post_builder import build_post_view_model


def register_content_routes(app, reader) -> None:
    @app.route("/")
    def index():
        return redirect(url_for("subreddit", name="all"))

    @app.route("/r/<name>")
    def subreddit(name):
        sort = request.args.get("sort", config.DEFAULT_SORT)
        time_filter = request.args.get("t", "day")
        limit = int(request.args.get("limit", config.DEFAULT_POST_LIMIT))

        listing_data = reader.fetch_subreddit(
            name,
            sort=sort,
            limit=limit,
            t=time_filter if sort == "top" else None,
        )

        posts = reader.parse_posts(listing_data) if listing_data else []

        if current_user.is_authenticated:
            banned_subreddits = get_user_banned_subs(current_user.id)
            if banned_subreddits:
                posts = [post for post in posts if post["subreddit"].lower() not in banned_subreddits]

        after = listing_data["data"].get("after") if listing_data and "data" in listing_data else None

        return render_template(
            "posts.html",
            posts=posts,
            subreddit=name,
            sort=sort,
            time_filter=time_filter,
            after=after,
            comments_limit=config.TOP_COMMENTS_PER_POST,
            reader=reader,
        )

    @app.route("/r/<subreddit>/comments/<post_id>")
    def comments(subreddit, post_id):
        comments_payload = reader.fetch_post_comments(subreddit, post_id)
        if not comments_payload or len(comments_payload) < 2:
            return render_template("error.html", message="Could not load comments"), 404

        post_data = comments_payload[0]["data"]["children"][0]["data"]
        media = reader.extract_media(post_data)
        post = build_post_view_model(post_data, media)
        comments_list = reader.parse_comments(comments_payload)

        return render_template("comments.html", post=post, comments=comments_list, reader=reader)

    @app.route("/r/<subreddit>/comments/<post_id>/share")
    def share_post(subreddit, post_id):
        comments_payload = reader.fetch_post_comments(subreddit, post_id)
        if not comments_payload or len(comments_payload) < 2:
            return render_template("error.html", message="Could not load post"), 404

        post_data = comments_payload[0]["data"]["children"][0]["data"]
        media = reader.extract_media(post_data)
        post = build_post_view_model(post_data, media)
        post_url = url_for("comments", subreddit=subreddit, post_id=post_id)

        return render_template("share.html", post=post, post_url=post_url, reader=reader)

    @app.route("/u/<username>")
    def user_profile(username):
        view = request.args.get("view", "both")
        sort = request.args.get("sort", config.DEFAULT_SORT)
        time_filter = request.args.get("t", "day")
        limit = int(request.args.get("limit", config.DEFAULT_POST_LIMIT))
        only_posts = request.args.get("only_posts", "0") in ("1", "true", "on")

        posts = []
        comments = []

        if view in ("posts", "both") or only_posts:
            submitted_data = reader.fetch_user(
                username,
                content="submitted",
                sort=sort,
                limit=limit,
                t=time_filter if sort == "top" else None,
            )
            if submitted_data:
                posts = reader.parse_posts(submitted_data)

        if view in ("comments", "both") and not only_posts:
            comment_data = reader.fetch_user(
                username,
                content="comments",
                sort=sort,
                limit=limit,
                t=time_filter if sort == "top" else None,
            )
            if comment_data:
                comments = reader.parse_user_comments(comment_data)

        if current_user.is_authenticated:
            banned_subreddits = get_user_banned_subs(current_user.id)
            if banned_subreddits:
                posts = [post for post in posts if post["subreddit"].lower() not in banned_subreddits]
                comments = [comment for comment in comments if comment["subreddit"].lower() not in banned_subreddits]

        reddit_url = f"https://reddit.com/u/{username}"
        combined = []
        if view == "both" and not only_posts:
            for post in posts:
                combined_post = post.copy()
                combined_post["_type"] = "post"
                combined.append(combined_post)
            for comment in comments:
                combined_comment = comment.copy()
                combined_comment["_type"] = "comment"
                combined.append(combined_comment)

        return render_template(
            "user.html",
            username=username,
            reddit_url=reddit_url,
            posts=posts,
            comments=comments,
            combined=combined,
            view=view,
            sort=sort,
            time_filter=time_filter,
            limit=limit,
            only_posts=only_posts,
            reader=reader,
        )

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        if query:
            return redirect(url_for("subreddit", name=query))
        return redirect(url_for("index"))
