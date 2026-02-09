# Reddit Reader

A custom Python program to fetch and display Reddit posts using the Reddit JSON API.


## Installation

1. Install Python 3.7 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run the program:
```bash
python app.py
```

The program will prompt you for:
- Subreddit name (default: all)
- Sort method (hot/new/top/rising)

### Using as a Module

```python
from reddit_reader import RedditReader

# Create reader instance
reader = RedditReader()

# Fetch posts
data = reader.fetch_subreddit("python", sort="hot", limit=10)
posts = reader.parse_posts(data)
reader.display_posts(posts)

# Fetch comments for a specific post
comment_data = reader.fetch_post_comments("python", post_id="abc123")
comments = reader.parse_comments(comment_data)
reader.display_comments(comments)
```

## Reddit JSON API

The program uses Reddit's public JSON API. Simply append `.json` to any Reddit URL:

- `https://reddit.com/r/all.json` - All posts
- `https://reddit.com/r/python.json` - Posts from r/python
- `https://reddit.com/r/python/hot.json` - Hot posts from r/python
- `https://reddit.com/r/python/new.json` - New posts from r/python
- `https://reddit.com/r/python/comments/{post_id}.json` - Comments for a specific post

### Parameters

- `limit`: Number of posts to fetch (max 100)
- `after`: Pagination token for next page
- `before`: Pagination token for previous page

## License

MIT License? - Feel free to use and modify as needed.