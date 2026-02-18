"""Comment formatting helpers for API responses."""

from __future__ import annotations

import copy
from typing import Any

from filters import format_content


def _add_formatted_body(comment: Any) -> Any:
    if not isinstance(comment, dict):
        return comment

    formatted_comment = dict(comment)
    formatted_comment["formatted_body"] = format_content(formatted_comment.get("body", ""))

    replies = formatted_comment.get("replies")
    if isinstance(replies, list):
        formatted_comment["replies"] = [_add_formatted_body(reply) for reply in replies]

    return formatted_comment


def format_comment_tree(comments: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    comments_subset = copy.deepcopy(comments[:limit]) if comments else []
    return [_add_formatted_body(comment) for comment in comments_subset]
