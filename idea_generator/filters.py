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
Filtering and ranking utilities for idea clusters.

This module provides:
- Composite score calculation with configurable weights
- Deterministic tie-breaking for consistent ordering
- Ranking functions for idea clusters
"""

from typing import Any, TypeVar

from .models import IdeaCluster

T = TypeVar("T", bound=IdeaCluster)

# Type alias for cluster dictionaries with composite scores
ClusterDict = dict[str, Any]


def compute_composite_score(
    cluster: IdeaCluster,
    weight_novelty: float = 0.25,
    weight_feasibility: float = 0.25,
    weight_desirability: float = 0.30,
    weight_attention: float = 0.20,
) -> float:
    """
    Compute a weighted composite score for an idea cluster.

    Args:
        cluster: The IdeaCluster to score
        weight_novelty: Weight for novelty metric (default: 0.25)
        weight_feasibility: Weight for feasibility metric (default: 0.25)
        weight_desirability: Weight for desirability metric (default: 0.30)
        weight_attention: Weight for attention metric (default: 0.20)

    Returns:
        Composite score in range [0.0, 1.0]

    Note:
        Weights should sum to 1.0 for normalized scores. If they don't,
        the result will be scaled accordingly.
    """
    score = (
        cluster.novelty * weight_novelty
        + cluster.feasibility * weight_feasibility
        + cluster.desirability * weight_desirability
        + cluster.attention * weight_attention
    )
    return score


def rank_clusters(
    clusters: list[T],
    weight_novelty: float = 0.25,
    weight_feasibility: float = 0.25,
    weight_desirability: float = 0.30,
    weight_attention: float = 0.20,
) -> list[T]:
    """
    Rank idea clusters by composite score with deterministic tie-breaking.

    Clusters are sorted by:
    1. Composite score (descending)
    2. Desirability (descending) - tie-breaker
    3. Feasibility (descending) - tie-breaker
    4. Representative title (ascending) - final tie-breaker for consistency

    Args:
        clusters: List of IdeaClusters to rank
        weight_novelty: Weight for novelty in composite score
        weight_feasibility: Weight for feasibility in composite score
        weight_desirability: Weight for desirability in composite score
        weight_attention: Weight for attention in composite score

    Returns:
        Sorted list of clusters in descending order of priority
    """
    if not clusters:
        return []

    # Compute scores for all clusters
    scored_clusters = [
        (
            cluster,
            compute_composite_score(
                cluster,
                weight_novelty=weight_novelty,
                weight_feasibility=weight_feasibility,
                weight_desirability=weight_desirability,
                weight_attention=weight_attention,
            ),
        )
        for cluster in clusters
    ]

    # Sort with deterministic tie-breaking
    # Primary: composite score (descending)
    # Secondary: desirability (descending)
    # Tertiary: feasibility (descending)
    # Quaternary: title (ascending)
    sorted_clusters = sorted(
        scored_clusters,
        key=lambda x: (
            -x[1],  # Negative for descending composite score
            -x[0].desirability,  # Negative for descending desirability
            -x[0].feasibility,  # Negative for descending feasibility
            x[0].representative_title,  # Ascending for consistent ordering
        ),
    )

    return [cluster for cluster, _ in sorted_clusters]


def add_composite_scores(
    clusters: list[IdeaCluster],
    weight_novelty: float = 0.25,
    weight_feasibility: float = 0.25,
    weight_desirability: float = 0.30,
    weight_attention: float = 0.20,
) -> list[ClusterDict]:
    """
    Add composite scores to clusters for serialization.

    Args:
        clusters: List of IdeaClusters
        weight_novelty: Weight for novelty in composite score
        weight_feasibility: Weight for feasibility in composite score
        weight_desirability: Weight for desirability in composite score
        weight_attention: Weight for attention in composite score

    Returns:
        List of cluster dictionaries with added 'composite_score' field
    """
    results = []
    for cluster in clusters:
        cluster_dict = cluster.model_dump(mode="json")
        cluster_dict["composite_score"] = compute_composite_score(
            cluster,
            weight_novelty=weight_novelty,
            weight_feasibility=weight_feasibility,
            weight_desirability=weight_desirability,
            weight_attention=weight_attention,
        )
        results.append(cluster_dict)
    return results
