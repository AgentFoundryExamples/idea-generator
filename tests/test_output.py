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
Tests for output generation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from idea_generator.models import IdeaCluster, NormalizedComment, NormalizedIssue
from idea_generator.output import (
    _get_priority_tag,
    generate_json_report,
    generate_markdown_report,
)


@pytest.fixture
def sample_issues() -> list[NormalizedIssue]:
    """Create sample normalized issues for testing."""
    return [
        NormalizedIssue(
            id=100,
            number=1,
            title="Add dark mode",
            body="Users want dark mode support.",
            labels=["enhancement"],
            state="open",
            reactions={"+1": 10},
            comments=[],
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            is_noise=False,
        ),
        NormalizedIssue(
            id=101,
            number=2,
            title="Security vulnerability",
            body="Critical security issue.",
            labels=["security", "bug"],
            state="open",
            reactions={"+1": 20, "heart": 5},
            comments=[],
            url="https://github.com/owner/repo/issues/2",
            created_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 4, tzinfo=timezone.utc),
            is_noise=False,
        ),
        NormalizedIssue(
            id=102,
            number=3,
            title="Spam issue",
            body="Test test test",
            labels=[],
            state="open",
            reactions={},
            comments=[],
            url="https://github.com/owner/repo/issues/3",
            created_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
            is_noise=True,
            noise_reason="Spam pattern detected",
        ),
    ]


@pytest.fixture
def sample_clusters() -> list[IdeaCluster]:
    """Create sample idea clusters for testing."""
    return [
        IdeaCluster(
            cluster_id="cluster-1",
            representative_title="Dark mode support",
            summary="Users request dark mode and theme customization.",
            topic_area="UI/UX",
            member_issue_ids=[100],
            novelty=0.4,
            feasibility=0.8,
            desirability=0.9,
            attention=0.7,
        ),
        IdeaCluster(
            cluster_id="cluster-2",
            representative_title="Security fixes",
            summary="Critical security vulnerabilities need immediate attention.",
            topic_area="security",
            member_issue_ids=[101],
            novelty=0.2,
            feasibility=0.9,
            desirability=1.0,
            attention=0.95,
        ),
        IdeaCluster(
            cluster_id="cluster-3",
            representative_title="Noise cluster",
            summary="Low quality issues.",
            topic_area="other",
            member_issue_ids=[102],
            novelty=0.1,
            feasibility=0.5,
            desirability=0.2,
            attention=0.1,
        ),
    ]


class TestGenerateJsonReport:
    """Tests for generate_json_report function."""

    def test_creates_valid_json(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that valid JSON is generated."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "ideas.json"
            generate_json_report(sample_clusters, sample_issues, output_path)

            assert output_path.exists()

            # Verify it's valid JSON
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)

            assert isinstance(data, list)
            assert len(data) == 3

    def test_includes_composite_scores(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that composite scores are included."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "ideas.json"
            generate_json_report(sample_clusters, sample_issues, output_path)

            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)

            for cluster in data:
                assert "composite_score" in cluster
                assert isinstance(cluster["composite_score"], float)
                assert 0.0 <= cluster["composite_score"] <= 1.0

    def test_includes_noise_flags(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that noise flags are included."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "ideas.json"
            generate_json_report(sample_clusters, sample_issues, output_path)

            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)

            # cluster-3 has issue 102 which is noise
            noise_cluster = next(c for c in data if c["cluster_id"] == "cluster-3")
            assert noise_cluster["has_noise_members"] is True

            # cluster-1 has issue 100 which is not noise
            clean_cluster = next(c for c in data if c["cluster_id"] == "cluster-1")
            assert clean_cluster["has_noise_members"] is False

    def test_includes_source_urls(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that source issue URLs are included."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "ideas.json"
            generate_json_report(sample_clusters, sample_issues, output_path)

            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)

            for cluster in data:
                assert "source_issue_urls" in cluster
                assert isinstance(cluster["source_issue_urls"], list)

                # Verify URLs match member issues
                for url in cluster["source_issue_urls"]:
                    assert url.startswith("https://github.com/")

    def test_custom_weights(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that custom weights affect composite scores."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "ideas.json"
            generate_json_report(
                sample_clusters,
                sample_issues,
                output_path,
                weight_novelty=0.5,
                weight_feasibility=0.2,
                weight_desirability=0.2,
                weight_attention=0.1,
            )

            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)

            # Manually calculate expected score for first cluster
            cluster = sample_clusters[0]
            expected = (
                cluster.novelty * 0.5
                + cluster.feasibility * 0.2
                + cluster.desirability * 0.2
                + cluster.attention * 0.1
            )

            actual = next(c for c in data if c["cluster_id"] == "cluster-1")[
                "composite_score"
            ]
            assert pytest.approx(actual, 0.001) == expected

    def test_creates_parent_directory(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that parent directories are created if needed."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "reports" / "nested" / "ideas.json"
            generate_json_report(sample_clusters, sample_issues, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_permission_error_handling(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that permission errors are handled gracefully."""
        # Try to write to a non-writable location (root)
        output_path = Path("/root/ideas.json")

        with pytest.raises(IOError, match="Failed to write JSON report"):
            generate_json_report(sample_clusters, sample_issues, output_path)


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report function."""

    def test_creates_valid_markdown(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that valid Markdown is generated."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "top-ideas.md"
            generate_markdown_report(sample_clusters, sample_issues, output_path)

            assert output_path.exists()

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            assert "# Top Ideas Report" in content
            assert "## 1." in content  # First ranked idea

    def test_limits_to_top_n(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that report limits to top N clusters."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "top-ideas.md"
            generate_markdown_report(
                sample_clusters, sample_issues, output_path, top_n=2
            )

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            # Should have ideas 1 and 2, but not 3
            assert "## 1." in content
            assert "## 2." in content
            assert "## 3." not in content

    def test_includes_metrics(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that metrics are included in report."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "top-ideas.md"
            generate_markdown_report(sample_clusters, sample_issues, output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            # Check for metric labels
            assert "Composite Score" in content
            assert "Novelty" in content
            assert "Feasibility" in content
            assert "Desirability" in content
            assert "Attention" in content

    def test_includes_priority_tags(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that priority tags are included."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "top-ideas.md"
            generate_markdown_report(sample_clusters, sample_issues, output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            assert "**Priority**:" in content

    def test_includes_source_links(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that source issue links are included."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "top-ideas.md"
            generate_markdown_report(sample_clusters, sample_issues, output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            # Should have links to GitHub issues
            assert "https://github.com/owner/repo/issues/1" in content
            assert "[#1]" in content

    def test_includes_scoring_config(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that scoring configuration is documented."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "top-ideas.md"
            generate_markdown_report(
                sample_clusters,
                sample_issues,
                output_path,
                weight_novelty=0.3,
                weight_feasibility=0.2,
                weight_desirability=0.4,
                weight_attention=0.1,
            )

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            assert "Novelty Weight" in content
            assert "0.30" in content
            assert "Desirability Weight" in content
            assert "0.40" in content

    def test_creates_parent_directory(
        self,
        sample_clusters: list[IdeaCluster],
        sample_issues: list[NormalizedIssue],
    ) -> None:
        """Test that parent directories are created if needed."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "reports" / "top-ideas.md"
            generate_markdown_report(sample_clusters, sample_issues, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()


class TestGetPriorityTag:
    """Tests for _get_priority_tag helper function."""

    def test_critical_priority_high_score(self) -> None:
        """Test critical priority for high composite score."""
        cluster = IdeaCluster(
            cluster_id="test",
            representative_title="Test",
            summary="Test",
            topic_area="test",
            member_issue_ids=[1],
            novelty=0.8,
            feasibility=0.8,
            desirability=0.8,
            attention=0.8,
        )
        tag = _get_priority_tag(0.8, cluster)
        assert "🔥 Critical" == tag

    def test_critical_priority_high_desirability(self) -> None:
        """Test critical priority for high desirability + feasibility."""
        cluster = IdeaCluster(
            cluster_id="test",
            representative_title="Test",
            summary="Test",
            topic_area="test",
            member_issue_ids=[1],
            novelty=0.3,
            feasibility=0.9,
            desirability=0.95,
            attention=0.5,
        )
        tag = _get_priority_tag(0.6, cluster)
        assert "🔥 Critical" == tag

    def test_high_priority(self) -> None:
        """Test high priority tag."""
        cluster = IdeaCluster(
            cluster_id="test",
            representative_title="Test",
            summary="Test",
            topic_area="test",
            member_issue_ids=[1],
            novelty=0.7,
            feasibility=0.7,
            desirability=0.7,
            attention=0.7,
        )
        tag = _get_priority_tag(0.7, cluster)
        assert "⭐ High Priority" == tag

    def test_medium_priority(self) -> None:
        """Test medium priority tag."""
        cluster = IdeaCluster(
            cluster_id="test",
            representative_title="Test",
            summary="Test",
            topic_area="test",
            member_issue_ids=[1],
            novelty=0.5,
            feasibility=0.5,
            desirability=0.5,
            attention=0.5,
        )
        tag = _get_priority_tag(0.5, cluster)
        assert "✅ Medium Priority" == tag

    def test_low_priority(self) -> None:
        """Test low priority tag."""
        cluster = IdeaCluster(
            cluster_id="test",
            representative_title="Test",
            summary="Test",
            topic_area="test",
            member_issue_ids=[1],
            novelty=0.2,
            feasibility=0.2,
            desirability=0.2,
            attention=0.2,
        )
        tag = _get_priority_tag(0.2, cluster)
        assert "💡 Low Priority" == tag
