"""
Configuration file for Reddit Reader
Supports environment variable overrides for Docker/production deployment
"""

import os

# Default settings
DEFAULT_SUBREDDIT = os.getenv("DEFAULT_SUBREDDIT", "all")
DEFAULT_SORT = os.getenv("DEFAULT_SORT", "hot")
DEFAULT_POST_LIMIT = int(os.getenv("DEFAULT_POST_LIMIT", "25"))
DEFAULT_COMMENT_LIMIT = int(os.getenv("DEFAULT_COMMENT_LIMIT", "50"))

# Top comments loaded on demand
TOP_COMMENTS_PER_POST = int(os.getenv("TOP_COMMENTS_PER_POST", "3"))
TOP_COMMENTS_FETCH_LIMIT = int(os.getenv("TOP_COMMENTS_FETCH_LIMIT", "50"))

# Simple rate limiting/backoff (seconds)
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "0.35"))
RATE_LIMIT_RETRY_DELAY = float(os.getenv("RATE_LIMIT_RETRY_DELAY", "2.0"))

# User agent for Reddit API requests
USER_AGENT = os.getenv("USER_AGENT", "RedditReader/1.0 (Custom Reddit JSON Reader)")

# Authentication settings
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-random-secret-key-in-production")
DATABASE_PATH = os.getenv("DATABASE_PATH", "users.db")
REMEMBER_COOKIE_DURATION = int(os.getenv("REMEMBER_COOKIE_DURATION", "2592000"))  # 30 days in seconds

# Display settings
SHOW_POST_DETAILS = os.getenv("SHOW_POST_DETAILS", "True").lower() == "true"
MAX_SELFTEXT_LENGTH = int(os.getenv("MAX_SELFTEXT_LENGTH", "150"))
MAX_COMMENT_LENGTH = int(os.getenv("MAX_COMMENT_LENGTH", "200"))
MAX_COMMENTS_DISPLAY = int(os.getenv("MAX_COMMENTS_DISPLAY", "10"))

# API settings
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))  # seconds
MAX_POSTS_PER_REQUEST = int(os.getenv("MAX_POSTS_PER_REQUEST", "100"))  # Reddit's max

# Autocomplete cache settings
AUTOCOMPLETE_CACHE_TTL = int(os.getenv("AUTOCOMPLETE_CACHE_TTL", "60"))  # seconds
AUTOCOMPLETE_CACHE_MAXSIZE = int(os.getenv("AUTOCOMPLETE_CACHE_MAXSIZE", "1024"))

# Future: AI Summary settings (for when you add AI features)
# AI_PROVIDER = "openai"  # or "anthropic"
# AI_MODEL = "gpt-4"
# AI_API_KEY = "your-api-key-here"
# SUMMARY_MAX_LENGTH = 200
