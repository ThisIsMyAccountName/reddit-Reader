"""
Reddit Reader - A custom program to fetch and display Reddit posts
"""

import requests
import json
import html
from datetime import datetime
from typing import List, Dict, Optional
import time


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
        gallery_urls: List[str] = []
        is_video = bool(post_data.get('is_video', False))

        # Reddit-hosted video
        media = post_data.get('secure_media') or post_data.get('media') or {}
        if isinstance(media, dict):
            reddit_video = media.get('reddit_video') or {}
            if isinstance(reddit_video, dict):
                video_url = reddit_video.get('fallback_url', '')

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
            'gallery_urls': gallery_urls,
        }
    
    def fetch_subreddit(self, subreddit: str = "all", sort: str = "hot", limit: int = 25) -> Optional[Dict]:
        """
        Fetch posts from a subreddit
        
        Args:
            subreddit: Name of the subreddit (default: "all")
            sort: Sort method - "hot", "new", "top", "rising" (default: "hot")
            limit: Number of posts to fetch (default: 25, max: 100)
            
        Returns:
            JSON response from Reddit or None if failed
        """
        url = f"https://reddit.com/r/{subreddit}/{sort}.json"
        params = {'limit': min(limit, 100)}
        
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
                'thumbnail': post_data.get('thumbnail', ''),
                'image_url': media['image_url'],
                'is_video': media['is_video'],
                'video_url': media['video_url'],
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


def main():
    """Main function to demonstrate the Reddit reader"""
    reader = RedditReader()
    
    print("Reddit Reader - Custom JSON API Reader")
    print("="*50)
    
    # Example: Fetch posts from r/all
    subreddit = input("\nEnter subreddit name (default: all): ").strip() or "all"
    sort_method = input("Sort by (hot/new/top/rising, default: hot): ").strip() or "hot"
    
    print(f"\nFetching posts from r/{subreddit}...")
    data = reader.fetch_subreddit(subreddit, sort=sort_method, limit=25)
    
    if data:
        posts = reader.parse_posts(data)
        reader.display_posts(posts)
        
        # Ask if user wants to see comments for a specific post
        view_comments = input("\nView comments for a post? (y/n): ").strip().lower()
        if view_comments == 'y':
            try:
                post_num = int(input(f"Enter post number (1-{len(posts)}): "))
                if 1 <= post_num <= len(posts):
                    selected_post = posts[post_num - 1]
                    print(f"\nFetching comments for: {selected_post['title']}")
                    
                    comment_data = reader.fetch_post_comments(
                        selected_post['subreddit'], 
                        selected_post['id']
                    )
                    
                    if comment_data:
                        comments = reader.parse_comments(comment_data)
                        reader.display_comments(comments)
                else:
                    print("Invalid post number.")
            except ValueError:
                print("Invalid input.")
    else:
        print("Failed to fetch posts.")


if __name__ == "__main__":
    main()
