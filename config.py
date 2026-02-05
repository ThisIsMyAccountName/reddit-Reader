"""
Configuration file for Reddit Reader
"""

# Default settings
DEFAULT_SUBREDDIT = "all"
DEFAULT_SORT = "hot"
DEFAULT_POST_LIMIT = 25
DEFAULT_COMMENT_LIMIT = 50

# Top comments loaded on demand
TOP_COMMENTS_PER_POST = 3
TOP_COMMENTS_FETCH_LIMIT = 50

# Cache settings (seconds)
COMMENTS_CACHE_TTL = 1800
SUBREDDIT_CACHE_TTL = 300

# Persistent cache
CACHE_PERSISTENCE = True
CACHE_PATH = ".cache/reddit_reader_cache"

# Simple rate limiting/backoff (seconds)
RATE_LIMIT_DELAY = 0.35
RATE_LIMIT_RETRY_DELAY = 2.0

# User agent for Reddit API requests
USER_AGENT = "RedditReader/1.0 (Custom Reddit JSON Reader)"

# Display settings
SHOW_POST_DETAILS = True
MAX_SELFTEXT_LENGTH = 150
MAX_COMMENT_LENGTH = 200
MAX_COMMENTS_DISPLAY = 10

# API settings
REQUEST_TIMEOUT = 10  # seconds
MAX_POSTS_PER_REQUEST = 100  # Reddit's max

# Future: AI Summary settings (for when you add AI features)
# AI_PROVIDER = "openai"  # or "anthropic"
# AI_MODEL = "gpt-4"
# AI_API_KEY = "your-api-key-here"
# SUMMARY_MAX_LENGTH = 200
