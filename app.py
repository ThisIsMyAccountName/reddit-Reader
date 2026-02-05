"""
Reddit Reader Web App
A minimal dark mode web interface for browsing Reddit
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
import time
import os
import shelve
from reddit_reader import RedditReader
import config

app = Flask(__name__)
reader = RedditReader(user_agent=config.USER_AGENT)

# Simple in-memory caches
subreddit_cache = {}
comment_cache = {}
post_comments_cache = {}


def _disk_key(cache_name: str, key) -> str:
    return f"{cache_name}:{repr(key)}"


def _disk_get(cache_name: str, key, ttl):
    if not config.CACHE_PERSISTENCE:
        return None
    os.makedirs(os.path.dirname(config.CACHE_PATH), exist_ok=True)
    disk_key = _disk_key(cache_name, key)
    with shelve.open(config.CACHE_PATH) as db:
        item = db.get(disk_key)
        if not item:
            return None
        timestamp, value = item
        if time.time() - timestamp > ttl:
            db.pop(disk_key, None)
            return None
        return value


def _disk_set(cache_name: str, key, value):
    if not config.CACHE_PERSISTENCE:
        return
    os.makedirs(os.path.dirname(config.CACHE_PATH), exist_ok=True)
    disk_key = _disk_key(cache_name, key)
    with shelve.open(config.CACHE_PATH) as db:
        db[disk_key] = (time.time(), value)


def _get_cached(cache, cache_name, key, ttl):
    item = cache.get(key)
    if item:
        timestamp, value = item
        if time.time() - timestamp <= ttl:
            return value
        cache.pop(key, None)

    value = _disk_get(cache_name, key, ttl)
    if value is not None:
        cache[key] = (time.time(), value)
    return value


def _set_cache(cache, cache_name, key, value):
    cache[key] = (time.time(), value)
    _disk_set(cache_name, key, value)


@app.route('/')
def index():
    """Home page - redirect to r/all"""
    return redirect(url_for('subreddit', name='all'))


@app.route('/r/<name>')
def subreddit(name):
    """Display posts from a subreddit"""
    sort = request.args.get('sort', config.DEFAULT_SORT)
    limit = int(request.args.get('limit', config.DEFAULT_POST_LIMIT))
    
    # Fetch data
    cache_key = (name, sort, limit)
    data = _get_cached(subreddit_cache, "subreddit", cache_key, config.SUBREDDIT_CACHE_TTL)
    if data is None:
        data = reader.fetch_subreddit(name, sort=sort, limit=limit)
        if data:
            _set_cache(subreddit_cache, "subreddit", cache_key, data)
    posts = reader.parse_posts(data) if data else []

    return render_template('posts.html', 
                         posts=posts, 
                         subreddit=name, 
                         sort=sort,
                         comments_limit=config.TOP_COMMENTS_PER_POST,
                         reader=reader)


@app.route('/r/<subreddit>/comments/<post_id>')
def comments(subreddit, post_id):
    """Display comments for a post"""
    # Fetch post and comments
    data = _get_cached(post_comments_cache, "post_comments", (subreddit, post_id), config.COMMENTS_CACHE_TTL)
    if data is None:
        data = reader.fetch_post_comments(subreddit, post_id)
        if data:
            _set_cache(post_comments_cache, "post_comments", (subreddit, post_id), data)
    
    if not data or len(data) < 2:
        return render_template('error.html', 
                             message="Could not load comments"), 404
    
    # Parse post info
    post_data = data[0]['data']['children'][0]['data']
    media = reader.extract_media(post_data)
    post = {
        'title': post_data.get('title', ''),
        'author': post_data.get('author', '[deleted]'),
        'subreddit': post_data.get('subreddit', ''),
        'score': post_data.get('score', 0),
        'num_comments': post_data.get('num_comments', 0),
        'url': post_data.get('url', ''),
        'permalink': f"https://reddit.com{post_data.get('permalink', '')}",
        'created_utc': post_data.get('created_utc', 0),
        'selftext': post_data.get('selftext', ''),
        'is_self': post_data.get('is_self', False),
        'id': post_data.get('id', ''),
        'image_url': media['image_url'],
        'is_video': media['is_video'],
        'video_url': media['video_url'],
        'gallery_urls': media['gallery_urls'],
    }
    
    # Parse comments
    comments_list = reader.parse_comments(data)
    
    return render_template('comments.html', 
                         post=post, 
                         comments=comments_list,
                         reader=reader)


@app.route('/search')
def search():
    """Search for a subreddit"""
    query = request.args.get('q', '').strip()
    if query:
        return redirect(url_for('subreddit', name=query))
    return redirect(url_for('index'))


@app.route('/api/comments')
def api_comments():
    """Return top comments for a post (lazy-load)."""
    subreddit = request.args.get('subreddit', '').strip()
    post_id = request.args.get('post_id', '').strip()
    limit = int(request.args.get('limit', 200))

    if not subreddit or not post_id:
        return jsonify({"error": "Missing subreddit or post_id"}), 400

    fetch_limit = max(limit, config.TOP_COMMENTS_FETCH_LIMIT)
    cache_key = (subreddit, post_id, fetch_limit)
    comments = _get_cached(comment_cache, "top_comments", cache_key, config.COMMENTS_CACHE_TTL)
    if comments is None:
        data = reader.fetch_post_comments(subreddit, post_id, limit=fetch_limit)
        comments = reader.parse_comments(data) if data else []
        _set_cache(comment_cache, "top_comments", cache_key, comments)
        time.sleep(config.RATE_LIMIT_DELAY)

    # Return full nested structure
    top_limit = int(request.args.get('limit', config.TOP_COMMENTS_PER_POST))
    return jsonify({"comments": comments[:top_limit]})



@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('error.html', 
                         message="Page not found"), 404


@app.errorhandler(500)
def server_error(error):
    """500 error handler"""
    return render_template('error.html', 
                         message="Server error occurred"), 500


if __name__ == '__main__':
    print("="*60)
    print("Reddit Reader Web App")
    print("="*60)
    print("Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
