# Reddit Reader

A custom Python program to fetch and display Reddit posts using the Reddit JSON API.

## Project Structure

- `app.py`: Application bootstrap and app factory
- `routes/`: Route registration modules separated by domain
	- `auth_routes.py`: login/register/logout
	- `settings_routes.py`: user settings, pin/ban management
	- `content_routes.py`: subreddit, post, share, and user profile pages
	- `api_routes.py`: JSON endpoints
	- `context.py`: global template context injection
	- `error_routes.py`: error handlers
- `services/`: Reusable business logic helpers
	- `user_settings_service.py`: settings load/save and normalization
	- `post_builder.py`: post payload mapping for templates
	- `comment_formatter.py`: recursive API comment body formatting


## Installation

1. Install Python 3.7 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

*Forms*: many pages now use Flask-WTF/WTForms for form handling and CSRF protection.  The settings page has been redesigned into a cohesive interface with immediate AJAX updates for display preferences (sidebar position, volume, speed and link behavior) and built-in rate limiting to prevent spamming toggles.  The dependency is listed in `requirements.txt`.

### Basic Usage

Run the program:
```bash
python app.py
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
