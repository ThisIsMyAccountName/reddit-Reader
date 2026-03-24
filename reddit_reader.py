"""
Reddit API client — fetches and parses posts, comments, and media.
"""

import html
import logging
import time
import requests
from datetime import datetime, timezone

import config
from services.post_builder import build_post_view_model

logger = logging.getLogger(__name__)


class RedditReader:
    """Fetches and displays Reddit posts from JSON API."""

    def __init__(self, user_agent: str = "RedditReader/1.0"):
        self.user_agent = user_agent
        self.headers = {"User-Agent": user_agent}
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_json(self, url: str, params: dict | None = None) -> dict | None:
        """GET *url* and return parsed JSON, with basic 429 back-off."""
        try:
            response = self.session.get(
                url, headers=self.headers, params=params, timeout=config.REQUEST_TIMEOUT
            )
            if response.status_code == 429:
                time.sleep(config.RATE_LIMIT_RETRY_DELAY)
                response = self.session.get(
                    url, headers=self.headers, params=params, timeout=config.REQUEST_TIMEOUT
                )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning("Error fetching data from %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # Fetch endpoints
    # ------------------------------------------------------------------

    def fetch_subreddit(
        self,
        subreddit: str = "all",
        sort: str = "hot",
        limit: int = 25,
        after: str | None = None,
        t: str | None = None,
    ) -> dict | None:
        """Fetch posts from *r/<subreddit>/<sort>.json*."""
        url = f"https://reddit.com/r/{subreddit}/{sort}.json"
        params: dict = {"limit": min(limit, config.MAX_POSTS_PER_REQUEST)}
        if after:
            params["after"] = after
        if t and sort == "top":
            params["t"] = t
        return self._get_json(url, params=params)

    def fetch_post_comments(
        self, subreddit: str, post_id: str, limit: int = 200
    ) -> dict | None:
        """Fetch comments for a specific post."""
        url = f"https://reddit.com/r/{subreddit}/comments/{post_id}.json"
        params = {"limit": limit, "depth": 10, "showmore": False}
        return self._get_json(url, params=params)

    def fetch_subreddit_autocomplete(self, query: str, limit: int = 10) -> list[dict]:
        """Call Reddit's subreddit autocomplete endpoint and return a
        normalized list of small dicts: {name, title, subscribers}.
        Uses the public reddit.com API with the configured User-Agent.
        """
        if not query:
            return []

        params = {"query": query, "limit": min(max(1, int(limit)), 100), "include_over_18": "true"}

        # Try known variants of the endpoint. Some Reddit endpoints require a
        # .json suffix; certain queries can return 404 on some endpoints.
        candidate_urls = [
            "https://www.reddit.com/api/subreddit_autocomplete_v2.json",
            "https://www.reddit.com/api/subreddit_autocomplete.json",
            "https://www.reddit.com/api/subreddit_autocomplete_v2",
        ]

        data = None
        for url in candidate_urls:
            try:
                resp = self.session.get(url, headers=self.headers, params=params, timeout=config.REQUEST_TIMEOUT)
                if resp.status_code == 429:
                    time.sleep(config.RATE_LIMIT_RETRY_DELAY)
                    resp = self.session.get(url, headers=self.headers, params=params, timeout=config.REQUEST_TIMEOUT)

                # If 404, try next candidate silently
                if resp.status_code == 404:
                    continue

                resp.raise_for_status()
                data = resp.json()
                break
            except requests.exceptions.HTTPError as he:
                logger.warning("Error fetching autocomplete (%s): %s", url, he)
                break
            except requests.exceptions.RequestException as e:
                logger.warning("Error fetching autocomplete (%s): %s", url, e)
                break

        results: list[dict] = []
        if not data:
            return results

        children = data.get("data", {}).get("children", []) if isinstance(data, dict) else []

        for child in children:
            d = child.get("data", {}) if isinstance(child, dict) else {}
            display_name = d.get("display_name") or d.get("display_name_prefixed") or d.get("name") or ""
            if display_name.startswith("r/"):
                name = display_name.split("/", 1)[1]
            else:
                name = display_name

            title = d.get("title") or d.get("public_description") or ""
            subscribers = d.get("subscribers") or 0

            if name:
                results.append({"name": name, "title": title, "subscribers": subscribers})

        return results

    # ------------------------------------------------------------------
    # Media extraction
    # ------------------------------------------------------------------

    def extract_media(self, post_data: dict) -> dict:
        """Extract media URLs (images, video, gallery) from a post."""
        image_url = ""
        video_url = ""
        audio_url = ""
        hls_url = ""
        gallery_urls: list[str] = []
        is_video = bool(post_data.get("is_video", False))

        # Reddit-hosted video
        media = post_data.get("secure_media") or post_data.get("media") or {}
        if isinstance(media, dict):
            reddit_video = media.get("reddit_video") or {}
            if isinstance(reddit_video, dict):
                hls_url = reddit_video.get("hls_url", "")
                fallback_url = reddit_video.get("fallback_url", "")
                if fallback_url:
                    # Keep signed query params on Reddit CDN URLs; stripping them causes 403.
                    clean_fallback_url = html.unescape(fallback_url)
                    video_url = clean_fallback_url

                    fallback_path, _, fallback_query = clean_fallback_url.partition("?")
                    base = fallback_path.rsplit("/", 1)[0]
                    audio_url = f"{base}/DASH_AUDIO_128.mp4"
                    if fallback_query:
                        audio_url = f"{audio_url}?{fallback_query}"

        # Gallery / album
        if post_data.get("is_gallery"):
            gallery = post_data.get("gallery_data") or {}
            items = gallery.get("items") or []
            media_metadata = post_data.get("media_metadata") or {}
            for item in items:
                media_id = item.get("media_id")
                meta = media_metadata.get(media_id) or {}
                source = meta.get("s") or {}
                url = source.get("u") or ""
                if url:
                    gallery_urls.append(html.unescape(url))

        # Image from preview (best quality)
        preview = post_data.get("preview") or {}
        images = preview.get("images") or []
        preview_image_url = ""
        if images and not gallery_urls:
            source = images[0].get("source") or {}
            preview_image_url = source.get("url", "")
            if preview_image_url:
                preview_image_url = html.unescape(preview_image_url)

        # Check direct URL for GIFs (prefer actual GIF over static preview)
        direct_url = post_data.get("url", "")
        if isinstance(direct_url, str) and direct_url.lower().endswith(".gif"):
            image_url = direct_url
        elif preview_image_url:
            image_url = preview_image_url

        # Fallback: direct image or video link
        if not image_url and not gallery_urls:
            url = post_data.get("url", "")
            if isinstance(url, str):
                url_lower = url.lower()
                # Check for video formats
                if url_lower.endswith((
                    ".mp4", ".webm", ".avi", ".mov", ".mkv", ".flv", ".wmv", 
                    ".m4v", ".3gp", ".ogv", ".mpg", ".mpeg", ".gifv"
                )):
                    video_url = url
                    is_video = True
                # Check for image formats
                elif url_lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                    image_url = url

        # Use first gallery image as hero when no standalone image
        if gallery_urls and not image_url:
            image_url = gallery_urls[0]

        return {
            "image_url": image_url,
            "is_video": is_video,
            "video_url": video_url,
            "audio_url": audio_url,
            "hls_url": hls_url,
            "gallery_urls": gallery_urls,
        }

    def _get_thumbnail(self, post_data: dict) -> str:
        """Return the best available thumbnail URL for a post."""
        thumbnail = post_data.get("thumbnail", "")
        if thumbnail and thumbnail.startswith("http"):
            return html.unescape(thumbnail)

        preview = post_data.get("preview") or {}
        images = preview.get("images") or []
        if images:
            resolutions = images[0].get("resolutions") or []
            if resolutions:
                for res in resolutions:
                    if res.get("width", 0) >= 320:
                        return html.unescape(res.get("url", ""))
                return html.unescape(resolutions[-1].get("url", ""))
            source = images[0].get("source") or {}
            if source.get("url"):
                return html.unescape(source.get("url", ""))

        return ""

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def parse_posts(self, data: dict | None) -> list[dict]:
        """Parse Reddit listing JSON into a flat list of post dicts."""
        if not data or "data" not in data:
            return []

        posts = []
        for child in data["data"]["children"]:
            post_data = child["data"]
            media = self.extract_media(post_data)
            thumbnail = self._get_thumbnail(post_data)

            posts.append(build_post_view_model(post_data, media, thumbnail=thumbnail))
        return posts

    @staticmethod
    def _is_bot_comment(author: str, body: str) -> bool:
        """Return True if the comment looks like it was posted by a bot."""
        bot_authors = {
            "AutoModerator", "sneakpeekbot", "TweetPoster", "autowikibot",
            "transcribot", "HelperBot", "RemindMeBot", "VideoLinkBot",
            "RepostSleuthBot", "Mentioned_Videos", "ImagesOfNetwork",
        }
        if author in bot_authors:
            return True

        author_lower = author.lower()
        if "bot" in author_lower or author_lower.endswith("bot"):
            return True

        bot_phrases = [
            "i am a bot", "i'm a bot", "this action was performed automatically",
            "beep boop", "^(this action", "this is a bot", "automoderator",
        ]
        body_lower = body.lower()
        return any(phrase in body_lower for phrase in bot_phrases)

    def parse_comment_tree(
        self, comment_obj: dict, depth: int = 0
    ) -> dict | None:
        """Recursively parse a comment and its replies."""
        if comment_obj.get("kind") != "t1":
            return None

        data = comment_obj.get("data", {})
        author = data.get("author", "[deleted]")
        body = data.get("body", "")
        score = data.get("score", 0)

        # Skip pinned / distinguished / bot comments
        if data.get("stickied") or data.get("distinguished") in ("moderator", "admin"):
            return None
        if self._is_bot_comment(author, body):
            return None

        comment: dict = {
            "author": author,
            "body": body,
            "score": score,
            "created_utc": data.get("created_utc", 0),
            "id": data.get("id", ""),
            "depth": depth,
            "replies": [],
        }

        replies_obj = data.get("replies")
        if isinstance(replies_obj, dict):
            for reply_obj in replies_obj.get("data", {}).get("children", []):
                parsed_reply = self.parse_comment_tree(reply_obj, depth + 1)
                if parsed_reply:
                    comment["replies"].append(parsed_reply)

        return comment

    def parse_comments(self, data: list | None) -> list[dict]:
        """Parse top-level Reddit comments with nested replies."""
        if not data or len(data) < 2:
            return []

        comments: list[dict] = []
        for child in data[1]["data"]["children"]:
            parsed = self.parse_comment_tree(child, 0)
            if parsed:
                comments.append(parsed)
        return comments

    def fetch_user(self, username: str, content: str = "submitted", sort: str = "new", limit: int = 25, after: str | None = None, t: str | None = None) -> dict | None:
        """Fetch user submitted posts or comments: /user/<username>/<content>.json"""
        if content not in ("submitted", "comments"):
            content = "submitted"
        url = f"https://reddit.com/user/{username}/{content}.json"
        params: dict = {"limit": min(limit, config.MAX_POSTS_PER_REQUEST)}
        if after:
            params["after"] = after
        if t and sort == "top":
            params["t"] = t
        return self._get_json(url, params=params)

    def parse_user_comments(self, data: dict | None) -> list[dict]:
        """Parse the listing returned by /user/<name>/comments.json into a list of comment dicts."""
        if not data or "data" not in data:
            return []

        comments: list[dict] = []
        for child in data["data"].get("children", []):
            d = child.get("data", {})
            # Basic fields
            author = d.get("author", "[deleted]")
            body = d.get("body", "")
            score = d.get("score", 0)
            subreddit = d.get("subreddit", "")
            created = d.get("created_utc", 0)
            cid = d.get("id", "")

            # Derive post id from link_id (e.g., t3_<id>) when possible
            link_id = d.get("link_id", "") or d.get("link_parent_id", "")
            post_id = ""
            if isinstance(link_id, str) and link_id.startswith("t3_"):
                parts = link_id.split("_", 1)
                if len(parts) > 1:
                    post_id = parts[1]

            permalink = d.get("permalink", "")
            # Full urls
            full_permalink = f"https://reddit.com{permalink}" if permalink else ""

            comments.append(
                {
                    "author": author,
                    "body": body,
                    "score": score,
                    "subreddit": subreddit,
                    "created_utc": created,
                    "id": cid,
                    "permalink": full_permalink,
                    "post_id": post_id,
                    "link_title": d.get("link_title", ""),
                }
            )

        return comments

    @staticmethod
    def format_timestamp(timestamp: float) -> str:
        """Convert a Unix timestamp to a human-readable string."""
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
