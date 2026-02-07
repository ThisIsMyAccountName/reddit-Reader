"""
Reddit Reader Web App
A minimal dark-mode web interface for browsing Reddit.
"""

import os
import time
from datetime import timedelta

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

import config
from cache import (
    comment_cache,
    get_cached,
    post_comments_cache,
    set_cache,
    subreddit_cache,
)
from filters import register_filters
from models import User, get_db, get_user_banned_subs, init_db
from reddit_reader import RedditReader

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(
    seconds=config.REMEMBER_COOKIE_DURATION
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

register_filters(app)

reader = RedditReader(user_agent=config.USER_AGENT)

init_db()


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


# ---------------------------------------------------------------------------
# Context processor — inject settings into every template
# ---------------------------------------------------------------------------


@app.context_processor
def inject_user_settings():
    context = {
        "pinned_subs": [],
        "banned_subs": [],
        "is_subreddit_page": False,
        "default_volume": 5,
        "default_speed": 1.0,
        "sidebar_position": "left",
    }

    if request.endpoint in ("subreddit", "comments"):
        context["is_subreddit_page"] = True

    if current_user.is_authenticated:
        conn = get_db()
        row = conn.execute(
            "SELECT pinned_subs, banned_subs, default_volume, default_speed, sidebar_position "
            "FROM user_settings WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()
        conn.close()
        if row:
            if row["pinned_subs"]:
                context["pinned_subs"] = [
                    s.strip() for s in row["pinned_subs"].split(",") if s.strip()
                ]
            if row["banned_subs"]:
                context["banned_subs"] = [
                    s.strip() for s in row["banned_subs"].split(",") if s.strip()
                ]
            context["default_volume"] = row["default_volume"] or 5
            context["default_speed"] = row["default_speed"] or 1.0
            context["sidebar_position"] = row["sidebar_position"] or "left"
    return context


# ===================================================================
# Authentication routes
# ===================================================================


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember", False)

        if not username or not password:
            flash("Please fill in all fields.", "error")
            return render_template("login.html")

        user_data = User.get_by_username(username)
        if user_data and check_password_hash(user_data["password_hash"], password):
            user = User(user_data["id"], user_data["username"])
            login_user(user, remember=bool(remember))
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")
        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if User.create(username, password):
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Username already exists.", "error")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ===================================================================
# User settings
# ===================================================================


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db()
    row = conn.execute(
        "SELECT pinned_subs, banned_subs, default_volume, default_speed, sidebar_position "
        "FROM user_settings WHERE user_id = ?",
        (current_user.id,),
    ).fetchone()

    current_subs: list[str] = []
    banned_subs: list[str] = []
    if row and row["pinned_subs"]:
        current_subs = [s.strip() for s in row["pinned_subs"].split(",") if s.strip()]
    if row and row["banned_subs"]:
        banned_subs = [s.strip() for s in row["banned_subs"].split(",") if s.strip()]
    default_volume = (row["default_volume"] if row and row["default_volume"] is not None else 5)
    default_speed = (row["default_speed"] if row and row["default_speed"] is not None else 1.0)
    sidebar_position = (row["sidebar_position"] if row and row["sidebar_position"] else "left")

    if request.method == "POST":
        action = request.form.get("action")
        sub = request.form.get("sub", "").strip().lstrip("r/").lower()

        if action == "add" and sub and sub not in current_subs:
            current_subs.append(sub)
        elif action == "remove" and sub in current_subs:
            current_subs.remove(sub)
        elif action == "move_up" and sub in current_subs:
            idx = current_subs.index(sub)
            if idx > 0:
                current_subs[idx], current_subs[idx - 1] = (
                    current_subs[idx - 1],
                    current_subs[idx],
                )
        elif action == "move_down" and sub in current_subs:
            idx = current_subs.index(sub)
            if idx < len(current_subs) - 1:
                current_subs[idx], current_subs[idx + 1] = (
                    current_subs[idx + 1],
                    current_subs[idx],
                )
        elif action == "save_playback":
            default_volume = max(0, min(100, int(request.form.get("default_volume", 5))))
            default_speed = max(0.25, min(2.0, float(request.form.get("default_speed", 1.0))))
        elif action == "save_sidebar":
            sidebar_position = request.form.get("sidebar_position", "left")
            if sidebar_position not in ["left", "right", "off"]:
                sidebar_position = "left"
        elif action == "reorder":
            new_order = request.form.get("order", "")
            if new_order:
                current_subs = [s.strip() for s in new_order.split(",") if s.strip()]
        elif action == "unban" and sub in banned_subs:
            banned_subs.remove(sub)

        conn.execute(
            """
            INSERT INTO user_settings (user_id, pinned_subs, banned_subs, default_volume, default_speed, sidebar_position)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                pinned_subs = excluded.pinned_subs,
                banned_subs = excluded.banned_subs,
                default_volume = excluded.default_volume,
                default_speed = excluded.default_speed,
                sidebar_position = excluded.sidebar_position
            """,
            (current_user.id, ",".join(current_subs), ",".join(banned_subs), default_volume, default_speed, sidebar_position),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("settings"))

    conn.close()
    return render_template(
        "settings.html",
        pinned_subs=current_subs,
        banned_subs=banned_subs,
        default_volume=default_volume,
        default_speed=default_speed,        sidebar_position=sidebar_position,    )


@app.route("/ban/<subreddit>", methods=["POST"])
@login_required
def ban_subreddit(subreddit):
    subreddit = subreddit.strip().lower()
    if not subreddit:
        return redirect(request.referrer or url_for("index"))

    conn = get_db()
    row = conn.execute(
        "SELECT banned_subs FROM user_settings WHERE user_id = ?",
        (current_user.id,),
    ).fetchone()
    banned_subs: list[str] = []
    if row and row["banned_subs"]:
        banned_subs = [s.strip() for s in row["banned_subs"].split(",") if s.strip()]

    if subreddit not in banned_subs:
        banned_subs.append(subreddit)
        conn.execute(
            """
            INSERT INTO user_settings (user_id, banned_subs)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET banned_subs = excluded.banned_subs
            """,
            (current_user.id, ",".join(banned_subs)),
        )
        conn.commit()

    conn.close()
    return redirect(request.referrer or url_for("index"))


# ===================================================================
# Content routes
# ===================================================================


@app.route("/")
def index():
    return redirect(url_for("subreddit", name="all"))


@app.route("/r/<name>")
def subreddit(name):
    sort = request.args.get("sort", config.DEFAULT_SORT)
    t = request.args.get("t", "day")
    limit = int(request.args.get("limit", config.DEFAULT_POST_LIMIT))

    cache_key = (name, sort, limit, t if sort == "top" else None)
    data = get_cached(subreddit_cache, "subreddit", cache_key, config.SUBREDDIT_CACHE_TTL)
    if data is None:
        data = reader.fetch_subreddit(name, sort=sort, limit=limit, t=t if sort == "top" else None)
        if data:
            set_cache(subreddit_cache, "subreddit", cache_key, data)

    posts = reader.parse_posts(data) if data else []

    if current_user.is_authenticated:
        banned = get_user_banned_subs(current_user.id)
        if banned:
            posts = [p for p in posts if p["subreddit"].lower() not in banned]

    after = None
    if data and "data" in data:
        after = data["data"].get("after")

    return render_template(
        "posts.html",
        posts=posts,
        subreddit=name,
        sort=sort,
        time_filter=t,
        after=after,
        comments_limit=config.TOP_COMMENTS_PER_POST,
        reader=reader,
    )


@app.route("/r/<subreddit>/comments/<post_id>")
def comments(subreddit, post_id):
    cache_key = (subreddit, post_id)
    data = get_cached(post_comments_cache, "post_comments", cache_key, config.COMMENTS_CACHE_TTL)
    if data is None:
        data = reader.fetch_post_comments(subreddit, post_id)
        if data:
            set_cache(post_comments_cache, "post_comments", cache_key, data)

    if not data or len(data) < 2:
        return render_template("error.html", message="Could not load comments"), 404

    post_data = data[0]["data"]["children"][0]["data"]
    media = reader.extract_media(post_data)
    post = {
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

    comments_list = reader.parse_comments(data)

    return render_template(
        "comments.html",
        post=post,
        comments=comments_list,
        reader=reader,
    )


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if query:
        return redirect(url_for("subreddit", name=query))
    return redirect(url_for("index"))


# ===================================================================
# JSON API endpoints
# ===================================================================


@app.route("/api/comments")
def api_comments():
    sub = request.args.get("subreddit", "").strip()
    post_id = request.args.get("post_id", "").strip()
    limit = int(request.args.get("limit", 200))

    if not sub or not post_id:
        return jsonify({"error": "Missing subreddit or post_id"}), 400

    fetch_limit = max(limit, config.TOP_COMMENTS_FETCH_LIMIT)
    cache_key = (sub, post_id, fetch_limit)
    comments_data = get_cached(comment_cache, "top_comments", cache_key, config.COMMENTS_CACHE_TTL)
    if comments_data is None:
        data = reader.fetch_post_comments(sub, post_id, limit=fetch_limit)
        comments_data = reader.parse_comments(data) if data else []
        set_cache(comment_cache, "top_comments", cache_key, comments_data)
        time.sleep(config.RATE_LIMIT_DELAY)

    # Add formatted body to each comment and reply
    def add_formatted_body(comment):
        from filters import format_content
        comment['formatted_body'] = format_content(comment.get('body', ''))
        if 'replies' in comment and comment['replies']:
            for reply in comment['replies']:
                add_formatted_body(reply)
        return comment
    
    formatted_comments = [add_formatted_body(c.copy()) for c in comments_data[:limit]]
    return jsonify({"comments": formatted_comments})


@app.route("/api/posts")
def api_posts():
    sub = request.args.get("subreddit", "all").strip()
    sort = request.args.get("sort", config.DEFAULT_SORT)
    t = request.args.get("t", "day")
    after = request.args.get("after", "").strip() or None
    limit = int(request.args.get("limit", config.DEFAULT_POST_LIMIT))

    data = reader.fetch_subreddit(sub, sort=sort, limit=limit, after=after, t=t if sort == "top" else None)
    posts = reader.parse_posts(data) if data else []

    if current_user.is_authenticated:
        banned = get_user_banned_subs(current_user.id)
        if banned:
            posts = [p for p in posts if p["subreddit"].lower() not in banned]

    next_after = None
    if data and "data" in data:
        next_after = data["data"].get("after")

    return jsonify({"posts": posts, "after": next_after, "comments_limit": config.TOP_COMMENTS_PER_POST})


# ===================================================================
# Error handlers
# ===================================================================


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", message="Page not found"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", message="Server error occurred"), 500


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
