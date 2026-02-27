"""Thread-safe wrapper around cachetools TTLCache for simple in-process caching."""
from __future__ import annotations

import threading
from typing import Any, Optional

from cachetools import TTLCache


class ThreadSafeTTLCache:
    """A thin thread-safe wrapper around cachetools.TTLCache.

    Usage:
        cache = ThreadSafeTTLCache(maxsize=1024, ttl=60)
        cache.get(key)
        cache.set(key, value)
    """

    def __init__(self, maxsize: int = 1024, ttl: int = 60):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = threading.RLock()

    def get(self, key: Any, default: Optional[Any] = None) -> Optional[Any]:
        with self._lock:
            return self._cache.get(key, default)

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._cache[key] = value

    def pop(self, key: Any, default: Optional[Any] = None) -> Optional[Any]:
        with self._lock:
            return self._cache.pop(key, default)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict:
        with self._lock:
            return {"currsize": self._cache.currsize, "maxsize": self._cache.maxsize}
