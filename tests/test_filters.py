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
Tests for filtering and ranking utilities.
"""

import pytest

from idea_generator.filters import (
    add_composite_scores,
    compute_composite_score,
    rank_clusters,
)
from idea_generator.models import IdeaCluster


@pytest.fixture
def sample_clusters() -> list[IdeaCluster]:
    """Create sample idea clusters for testing."""
    return [
        IdeaCluster(
            cluster_id="cluster-1",
            representative_title="High priority feature",
            summary="Very desirable and feasible feature.",
            topic_area="feature",
            member_issue_ids=[100],
            novelty=0.5,
            feasibility=0.9,
            desirability=0.95,
            attention=0.8,
        ),
        IdeaCluster(
            cluster_id="cluster-2",
            representative_title="Experimental idea",
            summary="Novel but risky concept.",
            topic_area="research",
            member_issue_ids=[101],
            novelty=0.95,
            feasibility=0.3,
            desirability=0.5,
            attention=0.2,
        ),
        IdeaCluster(
            cluster_id="cluster-3",
            representative_title="Quick win",
            summary="Easy implementation, moderate value.",
            topic_area="enhancement",
            member_issue_ids=[102, 103],
            novelty=0.2,
            feasibility=0.95,
            desirability=0.7,
            attention=0.6,
        ),
    ]


class TestCompositeScore:
    """Tests for compute_composite_score function."""

    def test_default_weights(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test composite score calculation with default weights."""
        cluster = sample_clusters[0]
        score = compute_composite_score(cluster)

        # Expected: 0.5*0.25 + 0.9*0.25 + 0.95*0.30 + 0.8*0.20
        # = 0.125 + 0.225 + 0.285 + 0.16 = 0.795
        assert pytest.approx(score, 0.001) == 0.795

    def test_custom_weights(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test composite score with custom weights."""
        cluster = sample_clusters[1]
        score = compute_composite_score(
            cluster,
            weight_novelty=0.5,
            weight_feasibility=0.2,
            weight_desirability=0.2,
            weight_attention=0.1,
        )

        # Expected: 0.95*0.5 + 0.3*0.2 + 0.5*0.2 + 0.2*0.1
        # = 0.475 + 0.06 + 0.1 + 0.02 = 0.655
        assert pytest.approx(score, 0.001) == 0.655

    def test_equal_weights(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test composite score with equal weights."""
        cluster = sample_clusters[2]
        score = compute_composite_score(
            cluster,
            weight_novelty=0.25,
            weight_feasibility=0.25,
            weight_desirability=0.25,
            weight_attention=0.25,
        )

        # Expected: (0.2 + 0.95 + 0.7 + 0.6) / 4 = 0.6125
        assert pytest.approx(score, 0.001) == 0.6125

    def test_zero_weights(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test composite score with some zero weights."""
        cluster = sample_clusters[0]
        score = compute_composite_score(
            cluster,
            weight_novelty=0.0,
            weight_feasibility=0.0,
            weight_desirability=1.0,
            weight_attention=0.0,
        )

        # Expected: only desirability matters
        assert score == 0.95


class TestRankClusters:
    """Tests for rank_clusters function."""

    def test_basic_ranking(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test that clusters are ranked by composite score."""
        ranked = rank_clusters(sample_clusters)

        # cluster-1 should be first (highest composite score)
        assert ranked[0].cluster_id == "cluster-1"

        # All clusters should be present
        assert len(ranked) == 3
        assert {c.cluster_id for c in ranked} == {"cluster-1", "cluster-2", "cluster-3"}

    def test_deterministic_ordering(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test that ranking is deterministic across multiple calls."""
        ranked1 = rank_clusters(sample_clusters)
        ranked2 = rank_clusters(sample_clusters)

        # Order should be identical
        assert [c.cluster_id for c in ranked1] == [c.cluster_id for c in ranked2]

    def test_tie_breaking_by_desirability(self) -> None:
        """Test that ties are broken by desirability."""
        # Create clusters with same composite score but different desirability
        clusters = [
            IdeaCluster(
                cluster_id="a",
                representative_title="A",
                summary="Summary A",
                topic_area="feature",
                member_issue_ids=[1],
                novelty=0.5,
                feasibility=0.5,
                desirability=0.6,
                attention=0.5,
            ),
            IdeaCluster(
                cluster_id="b",
                representative_title="B",
                summary="Summary B",
                topic_area="feature",
                member_issue_ids=[2],
                novelty=0.5,
                feasibility=0.5,
                desirability=0.8,
                attention=0.5,
            ),
        ]

        ranked = rank_clusters(clusters)

        # B should come first (higher desirability)
        assert ranked[0].cluster_id == "b"
        assert ranked[1].cluster_id == "a"

    def test_tie_breaking_by_title(self) -> None:
        """Test that final ties are broken alphabetically by title."""
        clusters = [
            IdeaCluster(
                cluster_id="1",
                representative_title="Zebra feature",
                summary="Summary",
                topic_area="feature",
                member_issue_ids=[1],
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
            ),
            IdeaCluster(
                cluster_id="2",
                representative_title="Alpha feature",
                summary="Summary",
                topic_area="feature",
                member_issue_ids=[2],
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
            ),
        ]

        ranked = rank_clusters(clusters)

        # Alpha should come before Zebra alphabetically
        assert ranked[0].cluster_id == "2"
        assert ranked[1].cluster_id == "1"

    def test_empty_list(self) -> None:
        """Test ranking an empty list."""
        ranked = rank_clusters([])
        assert ranked == []

    def test_single_cluster(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test ranking a single cluster."""
        ranked = rank_clusters([sample_clusters[0]])
        assert len(ranked) == 1
        assert ranked[0].cluster_id == "cluster-1"

    def test_custom_weights_affect_ranking(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test that custom weights change ranking order."""
        # Default weights
        ranked_default = rank_clusters(sample_clusters)

        # Heavy novelty weight (should boost cluster-2)
        ranked_novelty = rank_clusters(
            sample_clusters,
            weight_novelty=0.7,
            weight_feasibility=0.1,
            weight_desirability=0.1,
            weight_attention=0.1,
        )

        # cluster-2 has highest novelty (0.95)
        assert ranked_novelty[0].cluster_id == "cluster-2"

        # Order should be different
        assert [c.cluster_id for c in ranked_default] != [c.cluster_id for c in ranked_novelty]


class TestAddCompositeScores:
    """Tests for add_composite_scores function."""

    def test_adds_score_field(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test that composite_score field is added to each cluster."""
        results = add_composite_scores(sample_clusters)

        assert len(results) == 3
        for result in results:
            assert "composite_score" in result
            assert isinstance(result["composite_score"], float)
            assert 0.0 <= result["composite_score"] <= 1.0

    def test_preserves_original_fields(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test that original cluster fields are preserved."""
        results = add_composite_scores(sample_clusters)

        for i, result in enumerate(results):
            original = sample_clusters[i]
            assert result["cluster_id"] == original.cluster_id
            assert result["representative_title"] == original.representative_title
            assert result["novelty"] == original.novelty
            assert result["feasibility"] == original.feasibility

    def test_correct_score_calculation(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test that scores match manual calculation."""
        results = add_composite_scores(sample_clusters)

        # Manually verify first cluster
        cluster = sample_clusters[0]
        expected = (
            cluster.novelty * 0.25
            + cluster.feasibility * 0.25
            + cluster.desirability * 0.30
            + cluster.attention * 0.20
        )

        assert pytest.approx(results[0]["composite_score"], 0.001) == expected

    def test_custom_weights(self, sample_clusters: list[IdeaCluster]) -> None:
        """Test composite scores with custom weights."""
        results = add_composite_scores(
            sample_clusters,
            weight_novelty=0.5,
            weight_feasibility=0.2,
            weight_desirability=0.2,
            weight_attention=0.1,
        )

        cluster = sample_clusters[0]
        expected = (
            cluster.novelty * 0.5
            + cluster.feasibility * 0.2
            + cluster.desirability * 0.2
            + cluster.attention * 0.1
        )

        assert pytest.approx(results[0]["composite_score"], 0.001) == expected
