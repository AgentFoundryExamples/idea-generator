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
Output generation for idea reports.

This module provides:
- JSON report generation with complete cluster data
- Markdown report generation for top-ranked ideas
- Functions to generate human-readable summaries
"""

import json
from pathlib import Path

from .filters import add_composite_scores
from .models import IdeaCluster, NormalizedIssue


def generate_json_report(
    clusters: list[IdeaCluster],
    issues: list[NormalizedIssue],
    output_path: Path,
    weight_novelty: float = 0.25,
    weight_feasibility: float = 0.25,
    weight_desirability: float = 0.30,
    weight_attention: float = 0.20,
) -> None:
    """
    Generate a comprehensive JSON report of all idea clusters.

    The JSON includes:
    - All clusters with normalized metrics
    - Composite scores
    - Noise flags (inherited from member issues)
    - Source issue URLs for reference

    Args:
        clusters: List of ranked IdeaClusters
        issues: List of NormalizedIssues (for noise flag lookup)
        output_path: Path to write the JSON file
        weight_novelty: Weight for novelty in composite score
        weight_feasibility: Weight for feasibility in composite score
        weight_desirability: Weight for desirability in composite score
        weight_attention: Weight for attention in composite score

    Raises:
        IOError: If unable to write to output_path
        PermissionError: If output_path is not writable
    """
    # Create issue lookup for noise flags
    issue_map = {issue.id: issue for issue in issues}

    # Add composite scores to clusters
    clusters_with_scores = add_composite_scores(
        clusters,
        weight_novelty=weight_novelty,
        weight_feasibility=weight_feasibility,
        weight_desirability=weight_desirability,
        weight_attention=weight_attention,
    )

    # Enrich with noise flags and issue URLs
    for cluster_dict in clusters_with_scores:
        member_ids = cluster_dict["member_issue_ids"]
        # Check if any member issue is flagged as noise
        has_noise = any(
            issue_map[issue_id].is_noise for issue_id in member_ids if issue_id in issue_map
        )
        cluster_dict["has_noise_members"] = has_noise

        # Add source URLs for all member issues
        cluster_dict["source_issue_urls"] = [
            issue_map[issue_id].url for issue_id in member_ids if issue_id in issue_map
        ]

    # Write to file with proper error handling
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(clusters_with_scores, f, indent=2, ensure_ascii=False)
    except (OSError, PermissionError) as e:
        raise OSError(f"Failed to write JSON report to {output_path}: {e}") from e


def generate_markdown_report(
    clusters: list[IdeaCluster],
    issues: list[NormalizedIssue],
    output_path: Path,
    top_n: int = 10,
    weight_novelty: float = 0.25,
    weight_feasibility: float = 0.25,
    weight_desirability: float = 0.30,
    weight_attention: float = 0.20,
) -> None:
    """
    Generate a Markdown report summarizing the top-ranked ideas.

    The report includes:
    - Title and description of each top cluster
    - Metric breakdowns (novelty, feasibility, desirability, attention)
    - Composite score
    - Recommended priority tags
    - Source issue links

    Args:
        clusters: List of ranked IdeaClusters (should be pre-sorted)
        issues: List of NormalizedIssues (for lookup)
        output_path: Path to write the Markdown file
        top_n: Number of top ideas to include (default: 10)
        weight_novelty: Weight for novelty in composite score
        weight_feasibility: Weight for feasibility in composite score
        weight_desirability: Weight for desirability in composite score
        weight_attention: Weight for attention in composite score

    Raises:
        IOError: If unable to write to output_path
        PermissionError: If output_path is not writable
    """
    # Create issue lookup
    issue_map = {issue.id: issue for issue in issues}

    # Limit to top N clusters
    top_clusters = clusters[:top_n]

    # Build markdown content
    lines = [
        "# Top Ideas Report",
        "",
        "This report summarizes the highest-priority ideas derived from GitHub issues.",
        f"Generated from {len(issues)} issues, grouped into {len(clusters)} clusters.",
        "",
        "## Scoring Configuration",
        "",
        f"- **Novelty Weight**: {weight_novelty:.2f}",
        f"- **Feasibility Weight**: {weight_feasibility:.2f}",
        f"- **Desirability Weight**: {weight_desirability:.2f}",
        f"- **Attention Weight**: {weight_attention:.2f}",
        "",
        "---",
        "",
    ]

    # Add each cluster
    for rank, cluster in enumerate(top_clusters, 1):
        # Compute composite score
        composite = (
            cluster.novelty * weight_novelty
            + cluster.feasibility * weight_feasibility
            + cluster.desirability * weight_desirability
            + cluster.attention * weight_attention
        )

        # Determine priority tag
        priority = _get_priority_tag(composite, cluster)

        lines.append(f"## {rank}. {cluster.representative_title}")
        lines.append("")
        lines.append(f"**Priority**: {priority}")
        lines.append("")
        lines.append(f"**Topic Area**: {cluster.topic_area}")
        lines.append("")
        lines.append("### Summary")
        lines.append("")
        lines.append(cluster.summary)
        lines.append("")
        lines.append("### Metrics")
        lines.append("")
        lines.append(f"- **Composite Score**: {composite:.2f} / 1.00")
        lines.append(f"- **Novelty**: {cluster.novelty:.2f} / 1.00")
        lines.append(f"- **Feasibility**: {cluster.feasibility:.2f} / 1.00")
        lines.append(f"- **Desirability**: {cluster.desirability:.2f} / 1.00")
        lines.append(f"- **Attention**: {cluster.attention:.2f} / 1.00")
        lines.append("")
        lines.append("### Source Issues")
        lines.append("")

        # Add issue links
        for issue_id in cluster.member_issue_ids:
            issue = issue_map.get(issue_id)
            if issue:
                lines.append(f"- [#{issue.number}]({issue.url}) - {issue.title}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Write to file
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except (OSError, PermissionError) as e:
        raise OSError(f"Failed to write Markdown report to {output_path}: {e}") from e


def _get_priority_tag(composite_score: float, cluster: IdeaCluster) -> str:
    """
    Determine a priority tag based on composite score and metrics.

    Args:
        composite_score: The computed composite score (0.0-1.0)
        cluster: The IdeaCluster being evaluated

    Returns:
        Priority tag string (e.g., "🔥 Critical", "⭐ High Priority")
    """
    # High priority: composite > 0.75 or (desirability > 0.9 and feasibility > 0.7)
    if composite_score > 0.75 or (cluster.desirability > 0.9 and cluster.feasibility > 0.7):
        return "🔥 Critical"

    # Medium-high priority: composite > 0.6
    if composite_score > 0.6:
        return "⭐ High Priority"

    # Medium priority: composite > 0.45
    if composite_score > 0.45:
        return "✅ Medium Priority"

    # Low priority: everything else
    return "💡 Low Priority"
