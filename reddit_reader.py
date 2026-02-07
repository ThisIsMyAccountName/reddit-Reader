"""
Reddit API client — fetches and parses posts, comments, and media.
"""

import html
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional


class RedditReader:
    """Fetches and displays Reddit posts from JSON API."""

    def __init__(self, user_agent: str = "RedditReader/1.0"):
        self.user_agent = user_agent
        self.headers = {"User-Agent": user_agent}
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """GET *url* and return parsed JSON, with basic 429 back-off."""
        try:
            response = self.session.get(
                url, headers=self.headers, params=params, timeout=10
            )
            if response.status_code == 429:
                time.sleep(2.0)
                response = self.session.get(
                    url, headers=self.headers, params=params, timeout=10
                )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    # ------------------------------------------------------------------
    # Fetch endpoints
    # ------------------------------------------------------------------

    def fetch_subreddit(
        self,
        subreddit: str = "all",
        sort: str = "hot",
        limit: int = 25,
        after: Optional[str] = None,
        t: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch posts from *r/<subreddit>/<sort>.json*."""
        url = f"https://reddit.com/r/{subreddit}/{sort}.json"
        params: Dict = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        if t and sort == "top":
            params["t"] = t
        return self._get_json(url, params=params)

    def fetch_post_comments(
        self, subreddit: str, post_id: str, limit: int = 200
    ) -> Optional[Dict]:
        """Fetch comments for a specific post."""
        url = f"https://reddit.com/r/{subreddit}/comments/{post_id}.json"
        params = {"limit": limit, "depth": 10, "showmore": False}
        return self._get_json(url, params=params)

    # ------------------------------------------------------------------
    # Media extraction
    # ------------------------------------------------------------------

    def extract_media(self, post_data: Dict) -> Dict:
        """Extract media URLs (images, video, gallery) from a post."""
        image_url = ""
        video_url = ""
        audio_url = ""
        hls_url = ""
        gallery_urls: List[str] = []
        is_video = bool(post_data.get("is_video", False))

        # Reddit-hosted video
        media = post_data.get("secure_media") or post_data.get("media") or {}
        if isinstance(media, dict):
            reddit_video = media.get("reddit_video") or {}
            if isinstance(reddit_video, dict):
                hls_url = reddit_video.get("hls_url", "")
                fallback_url = reddit_video.get("fallback_url", "")
                if fallback_url:
                    video_url = fallback_url.split("?")[0]
                    base = fallback_url.split("?")[0].rsplit("/", 1)[0]
                    audio_url = f"{base}/DASH_AUDIO_128.mp4"

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

    def _get_thumbnail(self, post_data: Dict) -> str:
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

    def parse_posts(self, data: Optional[Dict]) -> List[Dict]:
        """Parse Reddit listing JSON into a flat list of post dicts."""
        if not data or "data" not in data:
            return []

        posts = []
        for child in data["data"]["children"]:
            post_data = child["data"]
            media = self.extract_media(post_data)

            posts.append(
                {
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
                    "thumbnail": self._get_thumbnail(post_data),
                    "image_url": media["image_url"],
                    "is_video": media["is_video"],
                    "video_url": media["video_url"],
                    "audio_url": media["audio_url"],
                    "hls_url": media["hls_url"],
                    "gallery_urls": media["gallery_urls"],
                }
            )
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
        self, comment_obj: Dict, depth: int = 0
    ) -> Optional[Dict]:
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

        comment: Dict = {
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

    def parse_comments(self, data: Optional[List]) -> List[Dict]:
        """Parse top-level Reddit comments with nested replies."""
        if not data or len(data) < 2:
            return []

        comments: List[Dict] = []
        for child in data[1]["data"]["children"]:
            parsed = self.parse_comment_tree(child, 0)
            if parsed:
                comments.append(parsed)
        return comments

    @staticmethod
    def format_timestamp(timestamp: float) -> str:
        """Convert a Unix timestamp to a human-readable string."""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
