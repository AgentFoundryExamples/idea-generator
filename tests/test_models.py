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

from idea_generator.models import NormalizedComment, NormalizedIssue


class TestNormalizedComment:
    """Test suite for NormalizedComment model."""

    def test_normalized_comment_creation(self) -> None:
        """Test creating a NormalizedComment."""
        comment = NormalizedComment(
            id=123,
            author="testuser",
            body="Test comment body",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            reactions={"+1": 5, "heart": 2},
        )
        assert comment.id == 123
        assert comment.author == "testuser"
        assert comment.body == "Test comment body"
        assert comment.reactions == {"+1": 5, "heart": 2}

    def test_normalized_comment_none_author(self) -> None:
        """Test NormalizedComment with None author."""
        comment = NormalizedComment(
            id=123,
            author=None,
            body="Comment from deleted user",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )
        assert comment.author is None

    def test_normalized_comment_default_reactions(self) -> None:
        """Test NormalizedComment with default reactions."""
        comment = NormalizedComment(
            id=123,
            author="testuser",
            body="Test comment",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )
        assert comment.reactions == {}


class TestNormalizedIssue:
    """Test suite for NormalizedIssue model."""

    def test_normalized_issue_creation(self) -> None:
        """Test creating a NormalizedIssue."""
        issue = NormalizedIssue(
            id=456,
            number=1,
            title="Test Issue",
            body="Test body",
            labels=["bug", "enhancement"],
            state="open",
            reactions={"+1": 10},
            comments=[],
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 2, 12, 0, 0),
        )
        assert issue.id == 456
        assert issue.number == 1
        assert issue.title == "Test Issue"
        assert issue.state == "open"
        assert issue.labels == ["bug", "enhancement"]
        assert len(issue.comments) == 0

    def test_normalized_issue_with_comments(self) -> None:
        """Test NormalizedIssue with comments."""
        comment = NormalizedComment(
            id=789,
            author="commenter",
            body="A comment",
            created_at=datetime(2025, 1, 1, 13, 0, 0),
        )
        issue = NormalizedIssue(
            id=456,
            number=1,
            title="Test Issue",
            body="Test body",
            state="open",
            comments=[comment],
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 2, 12, 0, 0),
        )
        assert len(issue.comments) == 1
        assert issue.comments[0].id == 789

    def test_normalized_issue_defaults(self) -> None:
        """Test NormalizedIssue with default values."""
        issue = NormalizedIssue(
            id=456,
            number=1,
            title="Test Issue",
            body="Test body",
            state="open",
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 2, 12, 0, 0),
        )
        assert issue.labels == []
        assert issue.reactions == {}
        assert issue.comments == []
        assert issue.is_noise is False
        assert issue.noise_reason is None
        assert issue.truncated is False
        assert issue.original_length == 0

    def test_normalized_issue_noise_flagging(self) -> None:
        """Test NormalizedIssue with noise flags."""
        issue = NormalizedIssue(
            id=456,
            number=1,
            title="spam",
            body="spam",
            state="open",
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 2, 12, 0, 0),
            is_noise=True,
            noise_reason="Spam label detected",
        )
        assert issue.is_noise is True
        assert issue.noise_reason == "Spam label detected"

    def test_normalized_issue_truncation_metadata(self) -> None:
        """Test NormalizedIssue with truncation metadata."""
        issue = NormalizedIssue(
            id=456,
            number=1,
            title="Long Issue",
            body="Very long text... [truncated]",
            state="open",
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 2, 12, 0, 0),
            truncated=True,
            original_length=15000,
        )
        assert issue.truncated is True
        assert issue.original_length == 15000
