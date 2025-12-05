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

from idea_generator.models import NormalizedComment, NormalizedIssue, SummarizedIssue


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


class TestSummarizedIssue:
    """Test suite for SummarizedIssue model."""

    def test_summarized_issue_creation(self) -> None:
        """Test creating a SummarizedIssue."""
        summary = SummarizedIssue(
            issue_id=123456,
            source_number=42,
            title="Add dark mode",
            summary="Users request dark mode for better night-time viewing.",
            topic_area="UI/UX",
            novelty=0.3,
            feasibility=0.8,
            desirability=0.9,
            attention=0.7,
            noise_flag=False,
            raw_issue_url="https://github.com/owner/repo/issues/42",
        )
        assert summary.issue_id == 123456
        assert summary.source_number == 42
        assert summary.title == "Add dark mode"
        assert summary.topic_area == "UI/UX"
        assert summary.novelty == 0.3
        assert summary.noise_flag is False

    def test_summarized_issue_metric_bounds(self) -> None:
        """Test that metrics are validated within 0.0-1.0 range."""
        # Valid metrics
        summary = SummarizedIssue(
            issue_id=123,
            source_number=1,
            title="Test",
            summary="Test summary",
            topic_area="test",
            novelty=0.0,
            feasibility=1.0,
            desirability=0.5,
            attention=0.3,
            noise_flag=False,
            raw_issue_url="https://github.com/test/test/issues/1",
        )
        assert summary.novelty == 0.0
        assert summary.feasibility == 1.0

        # Invalid: below 0.0
        with pytest.raises(ValueError):
            SummarizedIssue(
                issue_id=123,
                source_number=1,
                title="Test",
                summary="Test",
                topic_area="test",
                novelty=-0.1,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url="https://github.com/test/test/issues/1",
            )

        # Invalid: above 1.0
        with pytest.raises(ValueError):
            SummarizedIssue(
                issue_id=123,
                source_number=1,
                title="Test",
                summary="Test",
                topic_area="test",
                novelty=0.5,
                feasibility=1.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url="https://github.com/test/test/issues/1",
            )

    def test_summarized_issue_title_truncation(self) -> None:
        """Test that title is automatically truncated to 100 chars."""
        long_title = "A" * 150
        summary = SummarizedIssue(
            issue_id=123,
            source_number=1,
            title=long_title,
            summary="Test summary",
            topic_area="test",
            novelty=0.5,
            feasibility=0.5,
            desirability=0.5,
            attention=0.5,
            noise_flag=False,
            raw_issue_url="https://github.com/test/test/issues/1",
        )
        assert len(summary.title) == 100

    def test_summarized_issue_empty_summary_validation(self) -> None:
        """Test that empty summary is rejected."""
        with pytest.raises(ValueError, match="Summary cannot be empty"):
            SummarizedIssue(
                issue_id=123,
                source_number=1,
                title="Test",
                summary="",
                topic_area="test",
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url="https://github.com/test/test/issues/1",
            )

        with pytest.raises(ValueError, match="Summary cannot be empty"):
            SummarizedIssue(
                issue_id=123,
                source_number=1,
                title="Test",
                summary="   ",
                topic_area="test",
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url="https://github.com/test/test/issues/1",
            )

    def test_summarized_issue_noise_flagging(self) -> None:
        """Test noise flag on summarized issue."""
        summary = SummarizedIssue(
            issue_id=999,
            source_number=1,
            title="spam",
            summary="Spam content detected",
            topic_area="spam",
            novelty=0.0,
            feasibility=0.0,
            desirability=0.0,
            attention=0.0,
            noise_flag=True,
            raw_issue_url="https://github.com/test/test/issues/1",
        )
        assert summary.noise_flag is True
