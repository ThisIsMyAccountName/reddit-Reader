"""
Reddit Reader Web App
A minimal dark mode web interface for browsing Reddit
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import sqlite3
import time
import os
import shelve
import requests
import json
import html
from datetime import datetime
from typing import List, Dict, Optional
import config

# ============================================================================
# RedditReader Class (moved from reddit_reader.py)
# ============================================================================

class RedditReader:
    """Fetches and displays Reddit posts from JSON API"""
    
    def __init__(self, user_agent: str = "RedditReader/1.0"):
        """
        Initialize the Reddit reader
        
        Args:
            user_agent: User agent string for Reddit API requests
        """
        self.user_agent = user_agent
        self.headers = {'User-Agent': user_agent}
        self.session = requests.Session()

    def _get_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Internal helper with basic 429 backoff."""
        try:
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 429:
                time.sleep(2.0)
                response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def extract_media(self, post_data: Dict) -> Dict:
        """Extract media (images, video, gallery) from a post."""
        image_url = ''
        video_url = ''
        audio_url = ''
        hls_url = ''
        gallery_urls: List[str] = []
        is_video = bool(post_data.get('is_video', False))

        # Reddit-hosted video
        media = post_data.get('secure_media') or post_data.get('media') or {}
        if isinstance(media, dict):
            reddit_video = media.get('reddit_video') or {}
            if isinstance(reddit_video, dict):
                # Get HLS URL - has audio included
                hls_url = reddit_video.get('hls_url', '')
                
                # Get fallback URL for video
                fallback_url = reddit_video.get('fallback_url', '')
                if fallback_url:
                    # Clean video URL (remove query params)
                    video_url = fallback_url.split('?')[0]
                    
                    # Extract base URL: https://v.redd.it/{video_id}
                    # From: https://v.redd.it/{video_id}/DASH_720.mp4 or /CMAF_480.mp4
                    base = fallback_url.split('?')[0].rsplit('/', 1)[0]
                    
                    # Audio is at DASH_AUDIO_128.mp4 (128kbps) or DASH_AUDIO_64.mp4 (64kbps)
                    # Try 128 first for better quality
                    audio_url = f"{base}/DASH_AUDIO_128.mp4"

        # Gallery/album support
        if post_data.get('is_gallery'):
            gallery = post_data.get('gallery_data') or {}
            items = gallery.get('items') or []
            media_metadata = post_data.get('media_metadata') or {}
            for item in items:
                media_id = item.get('media_id')
                meta = media_metadata.get(media_id) or {}
                source = meta.get('s') or {}
                url = source.get('u') or ''
                if url:
                    gallery_urls.append(html.unescape(url))

        # Image from preview (best quality)
        preview = post_data.get('preview') or {}
        images = preview.get('images') or []
        if images and not gallery_urls:
            source = images[0].get('source') or {}
            image_url = source.get('url', '')
            if image_url:
                image_url = html.unescape(image_url)

        # Fallback: direct image link
        if not image_url and not gallery_urls:
            url = post_data.get('url', '')
            if isinstance(url, str) and url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                image_url = url

        # Prefer gallery over single image when present
        if gallery_urls and not image_url:
            image_url = gallery_urls[0]

        return {
            'image_url': image_url,
            'is_video': is_video,
            'video_url': video_url,
            'audio_url': audio_url,
            'hls_url': hls_url,
            'gallery_urls': gallery_urls,
        }
    
    def _get_thumbnail(self, post_data: Dict) -> str:
        """Get the best available thumbnail for a post."""
        # First try the thumbnail field
        thumbnail = post_data.get('thumbnail', '')
        if thumbnail and thumbnail.startswith('http'):
            return html.unescape(thumbnail)
        
        # Try preview images (better quality, works for videos too)
        preview = post_data.get('preview') or {}
        images = preview.get('images') or []
        if images:
            # Get a smaller resolution for thumbnail
            resolutions = images[0].get('resolutions') or []
            if resolutions:
                # Pick a medium resolution (around 320px wide)
                for res in resolutions:
                    if res.get('width', 0) >= 320:
                        return html.unescape(res.get('url', ''))
                # Fallback to last (largest) resolution
                return html.unescape(resolutions[-1].get('url', ''))
            # Fallback to source
            source = images[0].get('source') or {}
            if source.get('url'):
                return html.unescape(source.get('url', ''))
        
        return ''
    
    def fetch_subreddit(self, subreddit: str = "all", sort: str = "hot", limit: int = 25, after: str = None) -> Optional[Dict]:
        """
        Fetch posts from a subreddit
        
        Args:
            subreddit: Name of the subreddit (default: "all")
            sort: Sort method - "hot", "new", "top", "rising" (default: "hot")
            limit: Number of posts to fetch (default: 25, max: 100)
            after: Pagination token for next page (default: None)
            
        Returns:
            JSON response from Reddit or None if failed
        """
        url = f"https://reddit.com/r/{subreddit}/{sort}.json"
        params = {'limit': min(limit, 100)}
        if after:
            params['after'] = after
        
        return self._get_json(url, params=params)
    
    def fetch_post_comments(self, subreddit: str, post_id: str, limit: int = 200) -> Optional[Dict]:
        """
        Fetch comments for a specific post
        
        Args:
            subreddit: Name of the subreddit
            post_id: Reddit post ID
            limit: Number of comments to fetch (default: 200)
            
        Returns:
            JSON response containing post and comments
        """
        url = f"https://reddit.com/r/{subreddit}/comments/{post_id}.json"
        params = {'limit': limit, 'depth': 10, 'showmore': False}
        
        return self._get_json(url, params=params)
    
    def parse_posts(self, data: Dict) -> List[Dict]:
        """
        Parse Reddit JSON data into a list of post dictionaries
        
        Args:
            data: Raw JSON data from Reddit
            
        Returns:
            List of parsed post dictionaries
        """
        if not data or 'data' not in data:
            return []
        
        posts = []
        for child in data['data']['children']:
            post_data = child['data']
            media = self.extract_media(post_data)
            
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
                'thumbnail': self._get_thumbnail(post_data),
                'image_url': media['image_url'],
                'is_video': media['is_video'],
                'video_url': media['video_url'],
                'audio_url': media['audio_url'],
                'hls_url': media['hls_url'],
                'gallery_urls': media['gallery_urls'],
            }
            posts.append(post)
        
        return posts
    
    def is_bot_comment(self, author: str, body: str) -> bool:
        """Check if comment is from a bot."""
        bot_authors = [
            'AutoModerator', 'sneakpeekbot', 'TweetPoster', 'autowikibot',
            'transcribot', 'HelperBot', 'RemindMeBot', 'VideoLinkBot',
            'RepostSleuthBot', 'Mentioned_Videos', 'ImagesOfNetwork'
        ]
        
        if author in bot_authors:
            return True
        
        # Author heuristics
        author_lower = author.lower()
        if 'bot' in author_lower or author_lower.endswith('bot'):
            return True

        # Check for bot indicators in body
        bot_phrases = [
            'i am a bot', 'i\'m a bot', 'this action was performed automatically',
            'beep boop', '^(this action', 'this is a bot', 'automoderator'
        ]
        
        body_lower = body.lower()
        for phrase in bot_phrases:
            if phrase in body_lower:
                return True
        
        return False
    
    def parse_comment_tree(self, comment_obj: Dict, depth: int = 0, max_score_siblings: int = 0) -> Optional[Dict]:
        """Recursively parse a comment and its replies."""
        if comment_obj.get('kind') != 't1':
            return None
        
        data = comment_obj.get('data', {})
        author = data.get('author', '[deleted]')
        body = data.get('body', '')
        score = data.get('score', 0)

        # Remove pinned/distinguished comments
        if data.get('stickied') or data.get('distinguished') in ('moderator', 'admin'):
            return None
        
        # Filter out bot comments
        if self.is_bot_comment(author, body):
            # Keep bot only if it's the top score among siblings
            if max_score_siblings and score < max_score_siblings:
                return None
            return None
        
        # Optional: remove very low-score auto-like comments
        if score <= 0 and self.is_bot_comment(author, body):
            return None
        
        comment = {
            'author': author,
            'body': body,
            'score': score,
            'created_utc': data.get('created_utc', 0),
            'id': data.get('id', ''),
            'depth': depth,
            'replies': [],
        }
        
        # Parse replies
        replies_obj = data.get('replies')
        if isinstance(replies_obj, dict):
            replies_data = replies_obj.get('data', {}).get('children', [])
            replies_scores = [
                child.get('data', {}).get('score', 0)
                for child in replies_data
                if child.get('kind') == 't1'
            ]
            max_reply_score = max(replies_scores, default=0)
            for reply_obj in replies_data:
                parsed_reply = self.parse_comment_tree(reply_obj, depth + 1, max_reply_score)
                if parsed_reply:
                    comment['replies'].append(parsed_reply)
        
        return comment
    
    def parse_comments(self, data: List) -> List[Dict]:
        """Parse Reddit comments from JSON data with nested replies."""
        if not data or len(data) < 2:
            return []
        
        comments = []
        comment_data = data[1]['data']['children']
        
        scores = [
            child.get('data', {}).get('score', 0)
            for child in comment_data
            if child.get('kind') == 't1'
        ]
        max_score = max(scores, default=0)

        for child in comment_data:
            parsed = self.parse_comment_tree(child, 0, max_score)
            if parsed:
                comments.append(parsed)
        
        return comments
    
    def format_timestamp(self, timestamp: float) -> str:
        """Convert Unix timestamp to readable format"""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    def display_posts(self, posts: List[Dict], show_details: bool = True):
        """
        Display posts in a formatted way
        
        Args:
            posts: List of post dictionaries
            show_details: Whether to show full details or just titles
        """
        if not posts:
            print("No posts found.")
            return
        
        print(f"\n{'='*80}")
        print(f"Found {len(posts)} posts")
        print(f"{'='*80}\n")
        
        for i, post in enumerate(posts, 1):
            print(f"[{i}] {post['title']}")
            
            if show_details:
                print(f"    Author: u/{post['author']} | Subreddit: r/{post['subreddit']}")
                print(f"    Score: {post['score']:,} | Comments: {post['num_comments']:,}")
                print(f"    Posted: {self.format_timestamp(post['created_utc'])}")
                print(f"    URL: {post['permalink']}")
                
                if post['is_self'] and post['selftext']:
                    # Show first 150 characters of selftext
                    text = post['selftext'][:150]
                    if len(post['selftext']) > 150:
                        text += "..."
                    print(f"    Text: {text}")
                
                print()
    
    def display_comments(self, comments: List[Dict], limit: int = 10):
        """
        Display comments in a formatted way
        
        Args:
            comments: List of comment dictionaries
            limit: Maximum number of comments to display
        """
        if not comments:
            print("No comments found.")
            return
        
        print(f"\n{'='*80}")
        print(f"Top {min(len(comments), limit)} Comments")
        print(f"{'='*80}\n")
        
        for i, comment in enumerate(comments[:limit], 1):
            print(f"[{i}] u/{comment['author']} (Score: {comment['score']:,})")
            print(f"    {comment['body'][:200]}")
            if len(comment['body']) > 200:
                print("    ...")
            print()


# ============================================================================
# Flask App
# ============================================================================

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(seconds=config.REMEMBER_COOKIE_DURATION)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

reader = RedditReader(user_agent=config.USER_AGENT)


# ============================================================================
# User Authentication
# ============================================================================

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.context_processor
def inject_pinned_subs():
    """Inject pinned subreddits into all templates."""
    if current_user.is_authenticated:
        conn = get_db()
        row = conn.execute('SELECT pinned_subs FROM user_settings WHERE user_id = ?', (current_user.id,)).fetchone()
        conn.close()
        if row and row['pinned_subs']:
            return {'pinned_subs': [s.strip() for s in row['pinned_subs'].split(',') if s.strip()]}
    return {'pinned_subs': []}


def init_db():
    """Initialize the database with users and settings tables."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            pinned_subs TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

class User(UserMixin):
    """User class for Flask-Login."""
    def __init__(self, id, username):
        self.id = id
        self.username = username
    
    @staticmethod
    def get(user_id):
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if user:
            return User(user['id'], user['username'])
        return None
    
    @staticmethod
    def get_by_username(username):
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user:
            return {'id': user['id'], 'username': user['username'], 'password_hash': user['password_hash']}
        return None
    
    @staticmethod
    def create(username, password):
        conn = get_db()
        try:
            conn.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))

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


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html')
        
        user_data = User.get_by_username(username)
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'])
            login_user(user, remember=bool(remember))
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        
        if not username or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('register.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')
        
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if User.create(username, password):
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists.', 'error')
    
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    return redirect(url_for('index'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page."""
    conn = get_db()
    
    if request.method == 'POST':
        pinned_subs = request.form.get('pinned_subs', '').strip()
        # Normalize: remove r/ prefix, clean up whitespace
        subs = [s.strip().lstrip('r/').lower() for s in pinned_subs.split(',') if s.strip()]
        pinned_subs = ','.join(subs)
        
        conn.execute('''
            INSERT INTO user_settings (user_id, pinned_subs) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET pinned_subs = excluded.pinned_subs
        ''', (current_user.id, pinned_subs))
        conn.commit()
        conn.close()
        flash('Settings saved!', 'success')
        return redirect(url_for('settings'))
    
    # Get current settings
    row = conn.execute('SELECT pinned_subs FROM user_settings WHERE user_id = ?', (current_user.id,)).fetchone()
    conn.close()
    pinned_subs = row['pinned_subs'] if row else ''
    
    return render_template('settings.html', pinned_subs=pinned_subs)


def get_user_pinned_subs(user_id):
    """Get user's pinned subreddits as a list."""
    conn = get_db()
    row = conn.execute('SELECT pinned_subs FROM user_settings WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    if row and row['pinned_subs']:
        return [s.strip() for s in row['pinned_subs'].split(',') if s.strip()]
    return []


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
    
    # Get the 'after' token for pagination
    after = None
    if data and 'data' in data:
        after = data['data'].get('after')

    return render_template('posts.html', 
                         posts=posts, 
                         subreddit=name, 
                         sort=sort,
                         after=after,
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
        'audio_url': media['audio_url'],
        'hls_url': media['hls_url'],
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


@app.route('/api/posts')
def api_posts():
    """Return posts for infinite scroll."""
    subreddit = request.args.get('subreddit', 'all').strip()
    sort = request.args.get('sort', config.DEFAULT_SORT)
    after = request.args.get('after', '').strip() or None
    limit = int(request.args.get('limit', config.DEFAULT_POST_LIMIT))
    
    data = reader.fetch_subreddit(subreddit, sort=sort, limit=limit, after=after)
    posts = reader.parse_posts(data) if data else []
    
    # Get the 'after' token for next page
    next_after = None
    if data and 'data' in data:
        next_after = data['data'].get('after')
    
    return jsonify({
        "posts": posts,
        "after": next_after,
        "comments_limit": config.TOP_COMMENTS_PER_POST
    })


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
    import os
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
