"""
Two-level cache: fast in-memory dict backed by persistent shelve on disk.
"""

import os
import time
import shelve
from typing import Any, Optional

import config

# In-memory caches (module-level singletons)
subreddit_cache: dict = {}
comment_cache: dict = {}
post_comments_cache: dict = {}


def _disk_key(cache_name: str, key: Any) -> str:
    return f"{cache_name}:{repr(key)}"


def _disk_get(cache_name: str, key: Any, ttl: int) -> Optional[Any]:
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


def _disk_set(cache_name: str, key: Any, value: Any) -> None:
    if not config.CACHE_PERSISTENCE:
        return
    os.makedirs(os.path.dirname(config.CACHE_PATH), exist_ok=True)
    disk_key = _disk_key(cache_name, key)
    with shelve.open(config.CACHE_PATH) as db:
        db[disk_key] = (time.time(), value)


def get_cached(cache: dict, cache_name: str, key: Any, ttl: int) -> Optional[Any]:
    """Look up *key* in the memory cache, falling back to disk."""
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


def set_cache(cache: dict, cache_name: str, key: Any, value: Any) -> None:
    """Store *value* in both the memory cache and on disk."""
    cache[key] = (time.time(), value)
    _disk_set(cache_name, key, value)
