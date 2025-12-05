# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Copyright 2025 John Brosnihan

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import re
from datetime import datetime
from typing import Any

from .models import NormalizedComment, NormalizedIssue

# Common spam patterns for noise detection
SPAM_PATTERNS = [
    r"^test\s*$",
    r"^testing\s*$",
    r"^hello\s*$",
    r"^hi\s*$",
    r"^hey\s*$",
]


def clean_markdown(text: str) -> str:
    """
    Clean markdown formatting from text while preserving readability.

    Args:
        text: Raw markdown text

    Returns:
        Cleaned text with markdown noise removed
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Remove code blocks (keep content but remove markers)
    text = re.sub(r"```[a-zA-Z]*\n", "", text)
    text = re.sub(r"```", "", text)

    # Remove inline code markers (keep content)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove image markdown
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", text)

    # Convert links to text (keep link text, discard URL)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Remove markdown headers (keep text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove list markers (keep content)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Remove blockquote markers (keep content)
    text = re.sub(r"^\s*>\s+", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Trim whitespace
    text = text.strip()

    return text


def deduplicate_comments(comments: list[NormalizedComment]) -> list[NormalizedComment]:
    """
    Remove duplicate comments based on content similarity.

    Args:
        comments: List of normalized comments

    Returns:
        Deduplicated list of comments
    """
    if not comments:
        return []

    seen_bodies: set[str] = set()
    unique_comments: list[NormalizedComment] = []

    for comment in comments:
        # Normalize body for comparison
        normalized_body = comment.body.lower().strip()

        if normalized_body and normalized_body not in seen_bodies:
            seen_bodies.add(normalized_body)
            unique_comments.append(comment)

    return unique_comments


def truncate_text(
    issue_body: str,
    comments: list[NormalizedComment],
    max_length: int,
) -> tuple[str, list[NormalizedComment], int]:
    """
    Truncate combined issue and comment text to fit within max_length.
    Priority is given to the issue body.

    Args:
        issue_body: Issue body text
        comments: List of comments
        max_length: Maximum combined length in characters

    Returns:
        Tuple of (truncated_issue_body, truncated_comments, original_length)
    """
    # Validate minimum max_length
    truncation_marker = "... [truncated]"
    min_required_length = len(truncation_marker) * 2 + 10  # Marker + some content
    if max_length < min_required_length:
        raise ValueError(
            f"max_length ({max_length}) must be at least {min_required_length} "
            f"to accommodate truncation markers and minimal content"
        )

    # Calculate original length
    original_length = len(issue_body) + sum(len(c.body) for c in comments)

    # If already under limit, return as-is
    if original_length <= max_length:
        return issue_body, comments, original_length

    # Reserve space for issue body (at least 50% or the full body if it's smaller)
    issue_body_target = min(len(issue_body), max_length // 2)
    comments_space = max_length - issue_body_target

    # Truncate issue body if needed
    truncation_marker = "... [truncated]"
    if len(issue_body) > issue_body_target:
        # Ensure we don't create a negative slice
        truncate_at = max(0, issue_body_target - len(truncation_marker))
        truncated_issue = issue_body[:truncate_at] + truncation_marker
    else:
        truncated_issue = issue_body

    # Adjust comments space to account for actual issue body length
    comments_space = max_length - len(truncated_issue)

    # Truncate comments to fit remaining space
    truncated_comments: list[NormalizedComment] = []
    current_length = 0

    for comment in comments:
        comment_length = len(comment.body)

        if current_length + comment_length <= comments_space:
            truncated_comments.append(comment)
            current_length += comment_length
        else:
            # Try to fit a truncated version of this comment
            remaining_space = comments_space - current_length
            if remaining_space > 100:  # Only truncate if there's meaningful space
                # Ensure we don't create a negative slice
                truncate_at = max(0, remaining_space - len(truncation_marker))
                truncated_body = comment.body[:truncate_at] + truncation_marker
                truncated_comment = comment.model_copy(update={"body": truncated_body})
                truncated_comments.append(truncated_comment)
            break

    return truncated_issue, truncated_comments, original_length


def is_noise_issue(
    title: str,
    body: str,
    labels: list[str],
    author: str | None,
    comment_count: int,
) -> tuple[bool, str | None]:
    """
    Determine if an issue is likely noise/spam.

    Args:
        title: Issue title
        body: Issue body
        labels: Issue labels
        author: Issue author username
        comment_count: Number of comments

    Returns:
        Tuple of (is_noise, reason)
    """
    # Check for spam labels
    spam_labels = {"spam", "invalid", "wontfix", "duplicate"}
    if any(label.lower() in spam_labels for label in labels):
        spam_label_list = [label for label in labels if label.lower() in spam_labels]
        return True, f"Spam label detected: {spam_label_list}"

    # Check for bot authors (common bot patterns)
    if author:
        bot_patterns = ["[bot]", "-bot", "bot-", "dependabot", "renovate"]
        if any(pattern in author.lower() for pattern in bot_patterns):
            return True, f"Bot author: {author}"

    # Check for very short title (single word)
    if len(title.split()) <= 1:
        return True, "Single-word title"

    # Check for empty or very short body
    if len(body.strip()) < 10:
        return True, "Empty or very short body"

    # Check for common spam patterns in title
    for pattern in SPAM_PATTERNS:
        if re.match(pattern, title.lower().strip()):
            return True, f"Spam pattern in title: {title}"

    return False, None


def normalize_github_issue(
    issue_data: dict[str, Any],
    comments_data: list[dict[str, Any]],
    max_text_length: int,
    noise_filter_enabled: bool = True,
) -> NormalizedIssue:
    """
    Normalize a GitHub issue and its comments into a clean, structured format.

    Args:
        issue_data: Raw GitHub issue data
        comments_data: Raw GitHub comments data
        max_text_length: Maximum combined text length
        noise_filter_enabled: Whether to apply noise filtering

    Returns:
        Normalized issue with cleaned and truncated content
    """
    # Extract basic issue fields
    issue_id = issue_data["id"]
    issue_number = issue_data["number"]
    title = issue_data.get("title", "")
    raw_body = issue_data.get("body") or ""
    state = issue_data["state"]
    url = issue_data["html_url"]
    created_at = datetime.fromisoformat(issue_data["created_at"].replace("Z", "+00:00"))
    updated_at = datetime.fromisoformat(issue_data["updated_at"].replace("Z", "+00:00"))

    # Extract labels
    labels = [label["name"] for label in issue_data.get("labels", [])]

    # Extract reactions
    reactions_data = issue_data.get("reactions", {})
    reactions = {
        "+1": reactions_data.get("+1", 0),
        "-1": reactions_data.get("-1", 0),
        "laugh": reactions_data.get("laugh", 0),
        "hooray": reactions_data.get("hooray", 0),
        "confused": reactions_data.get("confused", 0),
        "heart": reactions_data.get("heart", 0),
        "rocket": reactions_data.get("rocket", 0),
        "eyes": reactions_data.get("eyes", 0),
    }
    # Remove zero reactions
    reactions = {k: v for k, v in reactions.items() if v > 0}

    # Clean body text
    cleaned_body = clean_markdown(raw_body)

    # Normalize comments
    normalized_comments: list[NormalizedComment] = []
    for comment_data in comments_data:
        comment_id = comment_data["id"]
        author_data = comment_data.get("user")
        author = author_data["login"] if author_data else None
        raw_comment_body = comment_data.get("body") or ""
        cleaned_comment_body = clean_markdown(raw_comment_body)
        comment_created_at = datetime.fromisoformat(
            comment_data["created_at"].replace("Z", "+00:00")
        )

        comment_reactions_data = comment_data.get("reactions", {})
        comment_reactions = {
            "+1": comment_reactions_data.get("+1", 0),
            "-1": comment_reactions_data.get("-1", 0),
            "laugh": comment_reactions_data.get("laugh", 0),
            "hooray": comment_reactions_data.get("hooray", 0),
            "confused": comment_reactions_data.get("confused", 0),
            "heart": comment_reactions_data.get("heart", 0),
            "rocket": comment_reactions_data.get("rocket", 0),
            "eyes": comment_reactions_data.get("eyes", 0),
        }
        comment_reactions = {k: v for k, v in comment_reactions.items() if v > 0}

        normalized_comments.append(
            NormalizedComment(
                id=comment_id,
                author=author,
                body=cleaned_comment_body,
                created_at=comment_created_at,
                reactions=comment_reactions,
            )
        )

    # Deduplicate comments
    normalized_comments = deduplicate_comments(normalized_comments)

    # Sort comments by creation time (deterministic ordering)
    normalized_comments.sort(key=lambda c: c.created_at)

    # Truncate text if needed
    truncated_body, truncated_comments, original_length = truncate_text(
        cleaned_body, normalized_comments, max_text_length
    )

    # Check if truncation occurred
    was_truncated = original_length > max_text_length

    # Apply noise filter
    is_noise = False
    noise_reason = None
    if noise_filter_enabled:
        author_data = issue_data.get("user")
        author = author_data["login"] if author_data else None
        is_noise, noise_reason = is_noise_issue(
            title, cleaned_body, labels, author, len(normalized_comments)
        )

    return NormalizedIssue(
        id=issue_id,
        number=issue_number,
        title=title,
        body=truncated_body,
        labels=labels,
        state=state,
        reactions=reactions,
        comments=truncated_comments,
        url=url,
        created_at=created_at,
        updated_at=updated_at,
        is_noise=is_noise,
        noise_reason=noise_reason,
        truncated=was_truncated,
        original_length=original_length,
    )
