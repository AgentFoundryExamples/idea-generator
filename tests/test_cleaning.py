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

from datetime import datetime

import pytest

from idea_generator.cleaning import (
    clean_markdown,
    deduplicate_comments,
    is_noise_issue,
    normalize_github_issue,
    truncate_text,
)
from idea_generator.models import NormalizedComment


class TestCleanMarkdown:
    """Test suite for clean_markdown function."""

    def test_clean_empty_text(self) -> None:
        """Test cleaning empty text."""
        assert clean_markdown("") == ""
        assert clean_markdown(None) == ""  # type: ignore

    def test_clean_code_blocks(self) -> None:
        """Test removing code blocks."""
        text = "Some text\n```python\ncode here\n```\nMore text"
        result = clean_markdown(text)
        assert "```" not in result
        assert "code here" in result

    def test_clean_inline_code(self) -> None:
        """Test removing inline code markers."""
        text = "This is `inline code` in text"
        result = clean_markdown(text)
        assert result == "This is inline code in text"

    def test_clean_images(self) -> None:
        """Test removing image markdown."""
        text = "Text ![alt text](image.png) more text"
        result = clean_markdown(text)
        assert result == "Text alt text more text"

    def test_clean_links(self) -> None:
        """Test converting links to text."""
        text = "Visit [GitHub](https://github.com) for more"
        result = clean_markdown(text)
        assert result == "Visit GitHub for more"

    def test_clean_headers(self) -> None:
        """Test removing header markers."""
        text = "## Header\nSome text\n### Another Header"
        result = clean_markdown(text)
        assert "##" not in result
        assert "Header" in result

    def test_clean_bold_italic(self) -> None:
        """Test removing bold/italic markers."""
        text = "This is **bold** and *italic* and __bold2__ and _italic2_"
        result = clean_markdown(text)
        assert "**" not in result
        assert "*" not in result
        assert result == "This is bold and italic and bold2 and italic2"

    def test_clean_lists(self) -> None:
        """Test removing list markers."""
        text = "- Item 1\n* Item 2\n1. Item 3"
        result = clean_markdown(text)
        assert "-" not in result
        assert "Item 1" in result
        assert "Item 2" in result

    def test_clean_blockquotes(self) -> None:
        """Test removing blockquote markers."""
        text = "> This is a quote\n> Another line"
        result = clean_markdown(text)
        assert ">" not in result
        assert "This is a quote" in result

    def test_clean_html_comments(self) -> None:
        """Test removing HTML comments."""
        text = "Text <!-- comment --> more text"
        result = clean_markdown(text)
        assert "<!--" not in result
        assert "comment" not in result
        assert result == "Text  more text"

    def test_clean_multiple_blank_lines(self) -> None:
        """Test collapsing multiple blank lines."""
        text = "Line 1\n\n\n\nLine 2"
        result = clean_markdown(text)
        assert "\n\n\n" not in result
        assert "Line 1\n\nLine 2" == result


class TestDeduplicateComments:
    """Test suite for deduplicate_comments function."""

    def test_deduplicate_empty_list(self) -> None:
        """Test deduplicating empty list."""
        assert deduplicate_comments([]) == []

    def test_deduplicate_unique_comments(self) -> None:
        """Test deduplicating unique comments."""
        comments = [
            NormalizedComment(id=1, author="user1", body="Comment 1", created_at=datetime.now()),
            NormalizedComment(id=2, author="user2", body="Comment 2", created_at=datetime.now()),
        ]
        result = deduplicate_comments(comments)
        assert len(result) == 2

    def test_deduplicate_duplicate_comments(self) -> None:
        """Test deduplicating duplicate comments."""
        comments = [
            NormalizedComment(id=1, author="user1", body="Same comment", created_at=datetime.now()),
            NormalizedComment(id=2, author="user2", body="Same comment", created_at=datetime.now()),
            NormalizedComment(
                id=3, author="user3", body="Different comment", created_at=datetime.now()
            ),
        ]
        result = deduplicate_comments(comments)
        assert len(result) == 2
        assert result[0].id == 1  # First occurrence kept
        assert result[1].id == 3

    def test_deduplicate_case_insensitive(self) -> None:
        """Test deduplication is case-insensitive."""
        comments = [
            NormalizedComment(id=1, author="user1", body="Comment", created_at=datetime.now()),
            NormalizedComment(id=2, author="user2", body="COMMENT", created_at=datetime.now()),
        ]
        result = deduplicate_comments(comments)
        assert len(result) == 1


class TestTruncateText:
    """Test suite for truncate_text function."""

    def test_truncate_no_truncation_needed(self) -> None:
        """Test when no truncation is needed."""
        issue_body = "Short body"
        comments = [
            NormalizedComment(id=1, author="user", body="Short comment", created_at=datetime.now())
        ]
        body, truncated_comments, original_length = truncate_text(issue_body, comments, 1000)
        assert body == "Short body"
        assert len(truncated_comments) == 1
        assert original_length == len("Short body") + len("Short comment")

    def test_truncate_issue_body_priority(self) -> None:
        """Test that issue body gets priority."""
        issue_body = "A" * 6000
        comments = [
            NormalizedComment(id=1, author="user", body="B" * 5000, created_at=datetime.now())
        ]
        body, truncated_comments, _ = truncate_text(issue_body, comments, 8000)
        # Issue body should get at least half (4000 chars)
        assert len(body) >= 4000
        assert "[truncated]" in body or len(body) == 6000

    def test_truncate_comments(self) -> None:
        """Test truncating comments."""
        issue_body = "Short body"
        comments = [
            NormalizedComment(id=1, author="user1", body="A" * 5000, created_at=datetime.now()),
            NormalizedComment(id=2, author="user2", body="B" * 5000, created_at=datetime.now()),
        ]
        body, truncated_comments, _ = truncate_text(issue_body, comments, 6000)
        # The function should either truncate comments or include fewer comments
        total_length = len(body) + sum(len(c.body) for c in truncated_comments)
        assert total_length <= 6000

    def test_truncate_returns_original_length(self) -> None:
        """Test that original length is returned."""
        issue_body = "A" * 5000
        comments = [
            NormalizedComment(id=1, author="user", body="B" * 5000, created_at=datetime.now())
        ]
        _, _, original_length = truncate_text(issue_body, comments, 8000)
        assert original_length == 10000

    def test_truncate_validates_minimum_length(self) -> None:
        """Test that truncate_text validates minimum max_length."""
        issue_body = "Some body"
        comments = []

        # max_length too small should raise ValueError
        with pytest.raises(ValueError, match="max_length.*must be at least"):
            truncate_text(issue_body, comments, 10)

        # Acceptable minimum should work
        body, _, _ = truncate_text(issue_body, comments, 50)
        assert body == "Some body"


class TestIsNoiseIssue:
    """Test suite for is_noise_issue function."""

    def test_not_noise(self) -> None:
        """Test valid issue."""
        is_noise, reason = is_noise_issue(
            title="Valid issue title",
            body="Detailed description of the problem",
            labels=["bug"],
            author="user",
            comment_count=5,
        )
        assert is_noise is False
        assert reason is None

    def test_spam_label(self) -> None:
        """Test issue with spam label."""
        is_noise, reason = is_noise_issue(
            title="Issue", body="Body", labels=["spam"], author="user", comment_count=0
        )
        assert is_noise is True
        assert "spam" in reason.lower()

    def test_invalid_label(self) -> None:
        """Test issue with invalid label."""
        is_noise, reason = is_noise_issue(
            title="Issue", body="Body", labels=["invalid"], author="user", comment_count=0
        )
        assert is_noise is True
        assert "invalid" in reason.lower()

    def test_bot_author(self) -> None:
        """Test issue from bot."""
        is_noise, reason = is_noise_issue(
            title="Update dependencies",
            body="Auto-generated PR",
            labels=[],
            author="dependabot[bot]",
            comment_count=0,
        )
        assert is_noise is True
        assert "bot" in reason.lower()

    def test_single_word_title(self) -> None:
        """Test issue with single-word title."""
        is_noise, reason = is_noise_issue(
            title="test", body="Some body", labels=[], author="user", comment_count=0
        )
        assert is_noise is True
        assert "single-word" in reason.lower()

    def test_empty_body(self) -> None:
        """Test issue with empty body."""
        is_noise, reason = is_noise_issue(
            title="Valid title", body="", labels=[], author="user", comment_count=0
        )
        assert is_noise is True
        assert "empty" in reason.lower() or "short" in reason.lower()

    def test_spam_pattern_title(self) -> None:
        """Test issue with spam pattern in title."""
        is_noise, reason = is_noise_issue(
            title="test", body="Some body", labels=[], author="user", comment_count=0
        )
        assert is_noise is True


class TestNormalizeGitHubIssue:
    """Test suite for normalize_github_issue function."""

    def test_normalize_basic_issue(self) -> None:
        """Test normalizing a basic issue."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": "Test body",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [{"name": "bug"}],
            "reactions": {"+1": 5, "-1": 0},
            "user": {"login": "testuser"},
        }
        comments_data = []

        result = normalize_github_issue(issue_data, comments_data, 10000, False)
        assert result.id == 123
        assert result.number == 1
        assert result.title == "Test Issue"
        assert result.state == "open"
        assert result.labels == ["bug"]
        assert result.reactions == {"+1": 5}
        assert len(result.comments) == 0

    def test_normalize_issue_with_comments(self) -> None:
        """Test normalizing issue with comments."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": "Test body",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [],
            "reactions": {},
            "user": {"login": "testuser"},
        }
        comments_data = [
            {
                "id": 456,
                "user": {"login": "commenter"},
                "body": "Test comment",
                "created_at": "2025-01-01T13:00:00Z",
                "reactions": {},
            }
        ]

        result = normalize_github_issue(issue_data, comments_data, 10000, False)
        assert len(result.comments) == 1
        assert result.comments[0].id == 456
        assert result.comments[0].author == "commenter"

    def test_normalize_issue_markdown_cleaning(self) -> None:
        """Test markdown cleaning in normalization."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": "**Bold** text with `code`",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [],
            "reactions": {},
            "user": {"login": "testuser"},
        }
        comments_data = []

        result = normalize_github_issue(issue_data, comments_data, 10000, False)
        assert "**" not in result.body
        assert "`" not in result.body
        assert "Bold" in result.body
        assert "code" in result.body

    def test_normalize_issue_noise_filtering(self) -> None:
        """Test noise filtering during normalization."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "spam",
            "body": "spam content",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [{"name": "spam"}],
            "reactions": {},
            "user": {"login": "testuser"},
        }
        comments_data = []

        result = normalize_github_issue(issue_data, comments_data, 10000, True)
        assert result.is_noise is True
        assert result.noise_reason is not None

    def test_normalize_issue_truncation(self) -> None:
        """Test text truncation during normalization."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": "A" * 10000,
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [],
            "reactions": {},
            "user": {"login": "testuser"},
        }
        comments_data = []

        result = normalize_github_issue(issue_data, comments_data, 5000, False)
        assert result.truncated is True
        assert result.original_length == 10000
        assert len(result.body) < 10000

    def test_normalize_issue_null_body(self) -> None:
        """Test normalizing issue with null body."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": None,
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [],
            "reactions": {},
            "user": {"login": "testuser"},
        }
        comments_data = []

        result = normalize_github_issue(issue_data, comments_data, 10000, False)
        assert result.body == ""

    def test_normalize_issue_deleted_user(self) -> None:
        """Test normalizing issue with deleted user."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": "Test body",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [],
            "reactions": {},
            "user": None,
        }
        comments_data = [
            {
                "id": 456,
                "user": None,
                "body": "Comment from deleted user",
                "created_at": "2025-01-01T13:00:00Z",
                "reactions": {},
            }
        ]

        result = normalize_github_issue(issue_data, comments_data, 10000, False)
        assert len(result.comments) == 1
        assert result.comments[0].author is None

    def test_normalize_issue_comment_sorting(self) -> None:
        """Test that comments are sorted by creation time."""
        issue_data = {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "body": "Test body",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
            "created_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
            "labels": [],
            "reactions": {},
            "user": {"login": "testuser"},
        }
        comments_data = [
            {
                "id": 2,
                "user": {"login": "user2"},
                "body": "Second comment",
                "created_at": "2025-01-01T14:00:00Z",
                "reactions": {},
            },
            {
                "id": 1,
                "user": {"login": "user1"},
                "body": "First comment",
                "created_at": "2025-01-01T13:00:00Z",
                "reactions": {},
            },
        ]

        result = normalize_github_issue(issue_data, comments_data, 10000, False)
        assert result.comments[0].id == 1
        assert result.comments[1].id == 2
