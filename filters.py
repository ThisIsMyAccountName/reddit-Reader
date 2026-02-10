"""
Jinja2 template filters.
"""

import html
import re


def format_content(text: str) -> str:
    """Render GIFs, blockquotes, and Reddit markdown for display."""
    if not text:
        return ""

    # Escape HTML for safety
    text = html.escape(text)

    # Giphy embeds: ![gif](giphy|ID) or ![gif](giphy|ID|downsized)
    def _replace_giphy(match: re.Match) -> str:
        giphy_id = match.group(1).split("|")[0]
        return (
            '<div class="giphy-container" style="margin:10px 0;">'
            f'<img src="https://media.giphy.com/media/{giphy_id}/giphy.gif" '
            'alt="GIF" class="comment-media" '
            'style="max-width:100%;border-radius:4px;" loading="lazy">'
            "</div>"
        )

    text = re.sub(r"!\[gif\]\(giphy\|([^)]+)\)", _replace_giphy, text)

    # Reddit images: ![img](url) - unescape the URL to handle &amp; properly
    def _replace_image(match: re.Match) -> str:
        url = html.unescape(match.group(1))
        return (
            f'<img src="{url}" alt="Image" class="comment-media" '
            'style="max-width:100%;border-radius:4px;margin:10px 0;" loading="lazy">'
        )
    
    text = re.sub(r"!\[img\]\(([^)]+)\)", _replace_image, text)

    # Render bare image URLs (not inside markdown link parentheses) as inline images.
    # Use a negative lookbehind to avoid matching URLs that are immediately
    # preceded by '(' which indicates they are inside a markdown link [text](url).
    def _replace_bare_image(match: re.Match) -> str:
        url = html.unescape(match.group(1))
        if re.search(r"\.(?:mp4|webm|ogv|mov|m4v)(?:[\?#].*)?$", url, re.IGNORECASE):
            return (
                '<video class="comment-media" controls playsinline preload="metadata" '
                f'src="{url}"></video>'
            )
        # Treat preview.redd.it and common image extensions as images
        if (
            'preview.redd.it' in url
            or re.search(r"\.(?:png|jpe?g|gif|webp|bmp)(?:[\?#].*)?$", url, re.IGNORECASE)
        ):
            return (
                f'<img src="{url}" alt="Image" class="comment-media" '
                'style="max-width:100%;border-radius:4px;margin:10px 0;" loading="lazy">'
            )
        # If it doesn't look like an image, leave the raw URL text (it will be
        # linkified later by inline formatting) — return the original match.
        return match.group(0)

    text = re.sub(r"(?<!\()\b(https?://[^\s)]+)", _replace_bare_image, text)

    # Process lines for blockquotes and other formatting
    lines = text.split("\n")
    formatted: list[str] = []
    in_code_block = False
    code_block_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Code blocks (4 spaces or tab)
        if line.startswith("    ") or line.startswith("\t"):
            if not in_code_block:
                in_code_block = True
                code_block_lines = []
            code_block_lines.append(html.escape(line[4:] if line.startswith("    ") else line[1:]))
            continue
        elif in_code_block:
            formatted.append(
                '<pre style="background:#1a1a1a;padding:10px;border-radius:4px;'
                'overflow-x:auto;margin:10px 0;"><code>'
                + "\n".join(code_block_lines)
                + "</code></pre>"
            )
            in_code_block = False
            code_block_lines = []
        
        # Blockquotes
        if stripped.startswith("&gt;"):
            content = stripped[4:].strip()
            # Apply inline formatting to blockquote content
            content = _apply_inline_formatting(content)
            formatted.append(
                '<blockquote style="border-left:4px solid #555;'
                "margin:5px 0 5px 10px;padding-left:10px;"
                f'color:#aaa;">{content}</blockquote>'
            )
        elif stripped == "":
            formatted.append("<br>")
        else:
            # Apply inline formatting
            line = _apply_inline_formatting(line)
            formatted.append(line + "<br>")
    
    # Close any remaining code block
    if in_code_block:
        formatted.append(
            '<pre style="background:#1a1a1a;padding:10px;border-radius:4px;'
            'overflow-x:auto;margin:10px 0;"><code>'
            + "\n".join(code_block_lines)
            + "</code></pre>"
        )

    return "".join(formatted)


def _apply_inline_formatting(text: str) -> str:
    """Apply inline Reddit markdown formatting."""
    # Inline code: `code`
    text = re.sub(
        r"`([^`]+)`",
        r'<code style="background:#1a1a1a;padding:2px 4px;border-radius:3px;">\1</code>',
        text
    )
    
    # Links: [text](url) - unescape the URL to handle &amp; properly
    def _replace_link(match: re.Match) -> str:
        link_text = match.group(1)
        url = html.unescape(match.group(2))
        return f'<a href="{url}" target="_blank" style="color:#4a9eff;">{link_text}</a>'
    
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        _replace_link,
        text
    )
    
    # Bold: **text** or __text__
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    
    # Italic: *text* or _text_ (but not in the middle of words)
    text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", text)
    
    # Strikethrough: ~~text~~
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    
    # Superscript: ^text
    text = re.sub(r"\^(\w+)", r"<sup>\1</sup>", text)
    
    # Spoilers: >!text!<
    text = re.sub(
        r"&gt;!([^!]+)!&lt;",
        r'<span style="background:#555;color:#555;" title="Spoiler (hover to reveal)">\1</span>',
        text
    )

    text = _linkify_mentions(text)

    return text


def _linkify_mentions(text: str) -> str:
    parts = re.split(r"(<[^>]+>)", text)
    out: list[str] = []
    in_code = 0
    in_anchor = 0

    mention_re = re.compile(r"(?<![\w/])([ru])/([A-Za-z0-9_]{2,21})")

    for part in parts:
        if part.startswith("<"):
            tag = part.lower()
            if re.match(r"<code\b|<pre\b", tag):
                in_code += 1
            elif re.match(r"</code\b|</pre\b", tag):
                in_code = max(0, in_code - 1)
            if re.match(r"<a\b", tag):
                in_anchor += 1
            elif re.match(r"</a\b", tag):
                in_anchor = max(0, in_anchor - 1)
            out.append(part)
            continue

        if in_code or in_anchor:
            out.append(part)
            continue

        def _replace_mention(match: re.Match) -> str:
            kind = match.group(1)
            name = match.group(2)
            href = f"/r/{name}" if kind == "r" else f"/u/{name}"
            return f'<a href="{href}" class="mention-link">{kind}/{name}</a>'

        out.append(mention_re.sub(_replace_mention, part))

    return "".join(out)


def register_filters(app):
    """Register all custom Jinja filters on *app*."""
    app.template_filter("format_content")(format_content)
