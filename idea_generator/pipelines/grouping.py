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
Grouping pipeline for clustering summarized issues using the LLM grouper persona.

This pipeline:
1. Batches summarized issues by count and character budget
2. Sends batches to the LLM with grouping instructions
3. Validates cluster outputs (member IDs, uniqueness, coverage)
4. Aggregates metrics deterministically
5. Handles singleton clusters and edge cases
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..llm.client import OllamaClient, OllamaError
from ..models import IdeaCluster, SummarizedIssue

logger = logging.getLogger(__name__)


class GroupingError(Exception):
    """Base exception for grouping pipeline errors."""

    pass


class GroupingPipeline:
    """
    Pipeline for grouping summarized issues using the LLM grouper persona.

    This pipeline processes summaries in batches to respect context limits,
    validates cluster membership, and ensures deterministic metric aggregation.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        model: str,
        prompt_template_path: Path,
        max_batch_size: int = 20,
        max_batch_chars: int = 50000,
    ) -> None:
        """
        Initialize the grouping pipeline.

        Args:
            llm_client: Configured Ollama client instance
            model: Name of the model to use for grouping
            prompt_template_path: Path to the system prompt template file
            max_batch_size: Maximum number of summaries per batch (default: 20)
            max_batch_chars: Maximum character count per batch (default: 50000)
        """
        self.llm_client = llm_client
        self.model = model
        self.max_batch_size = max_batch_size
        self.max_batch_chars = max_batch_chars

        # Load system prompt
        if not prompt_template_path.exists():
            raise GroupingError(f"Prompt template not found: {prompt_template_path}")

        with open(prompt_template_path, encoding="utf-8") as f:
            self.system_prompt = f.read()

    def _create_batches(self, summaries: list[SummarizedIssue]) -> list[list[SummarizedIssue]]:
        """
        Create batches of summaries respecting size and character limits.

        Args:
            summaries: List of SummarizedIssues to batch

        Returns:
            List of batches, where each batch is a list of SummarizedIssues
        """
        if not summaries:
            return []

        batches: list[list[SummarizedIssue]] = []
        current_batch: list[SummarizedIssue] = []
        current_chars = 0

        for summary in summaries:
            # Estimate character count (JSON representation)
            summary_json = json.dumps(summary.model_dump(mode="json"), ensure_ascii=False)
            summary_chars = len(summary_json)

            # Check if adding this summary would exceed limits
            would_exceed_size = len(current_batch) >= self.max_batch_size
            would_exceed_chars = current_chars + summary_chars > self.max_batch_chars

            if current_batch and (would_exceed_size or would_exceed_chars):
                # Start new batch
                batches.append(current_batch)
                current_batch = [summary]
                current_chars = summary_chars
            else:
                # Add to current batch
                current_batch.append(summary)
                current_chars += summary_chars

        # Add final batch
        if current_batch:
            batches.append(current_batch)

        return batches

    def _format_batch_prompt(self, summaries: list[SummarizedIssue]) -> str:
        """
        Format a batch of summaries into a prompt for the LLM.

        Args:
            summaries: Batch of SummarizedIssues

        Returns:
            Formatted prompt string
        """
        # Convert summaries to simplified format for LLM
        summaries_data = [summary.model_dump(mode="json") for summary in summaries]

        prompt = (
            "Analyze the following batch of summarized GitHub issues and group them "
            "into actionable idea clusters. Merge duplicates, split multi-topic issues "
            "as needed, and preserve unique issues as singletons.\n\n"
            f"Input batch ({len(summaries)} issues):\n"
            f"{json.dumps(summaries_data, indent=2, ensure_ascii=False)}\n\n"
            "Respond with ONLY valid JSON following the specified cluster schema."
        )

        return prompt

    def _validate_clusters(
        self,
        clusters: list[IdeaCluster],
        input_summaries: list[SummarizedIssue],
    ) -> tuple[bool, list[str]]:
        """
        Validate clusters against input summaries.

        Checks:
        1. All cluster member_issue_ids exist in input
        2. No issue appears in multiple clusters
        3. All input issues are covered by exactly one cluster

        Args:
            clusters: List of IdeaClusters to validate
            input_summaries: Original input summaries

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        # Build set of valid issue IDs
        valid_issue_ids = {s.issue_id for s in input_summaries}

        # Track which issues are claimed by clusters
        claimed_issues: set[int] = set()
        issue_to_cluster: dict[int, str] = {}

        for cluster in clusters:
            # Check for unknown issue IDs
            unknown_ids = [iid for iid in cluster.member_issue_ids if iid not in valid_issue_ids]
            if unknown_ids:
                errors.append(
                    f"Cluster '{cluster.cluster_id}' references unknown issue IDs: {unknown_ids}"
                )

            # Check for duplicate assignments
            for issue_id in cluster.member_issue_ids:
                if issue_id in claimed_issues:
                    other_cluster = issue_to_cluster.get(issue_id, "unknown")
                    errors.append(
                        f"Issue {issue_id} assigned to multiple clusters: "
                        f"'{cluster.cluster_id}' and '{other_cluster}'"
                    )
                else:
                    claimed_issues.add(issue_id)
                    issue_to_cluster[issue_id] = cluster.cluster_id

        # Check for unclaimed issues
        unclaimed = valid_issue_ids - claimed_issues
        if unclaimed:
            errors.append(f"Issues not assigned to any cluster: {sorted(unclaimed)}")

        return (len(errors) == 0, errors)

    def _parse_llm_response(
        self,
        llm_response: dict[str, Any],
        input_summaries: list[SummarizedIssue],
    ) -> list[IdeaCluster]:
        """
        Parse and validate LLM response into IdeaClusters.

        Args:
            llm_response: Raw response from LLM client
            input_summaries: Original input summaries for validation

        Returns:
            List of validated IdeaClusters

        Raises:
            GroupingError: If response is invalid or validation fails
        """
        try:
            # Extract JSON from response
            parsed_json = self.llm_client.parse_json_response(llm_response)

            # Check for clusters key
            if "clusters" not in parsed_json:
                raise GroupingError("LLM response missing 'clusters' field")

            clusters_data = parsed_json["clusters"]
            if not isinstance(clusters_data, list):
                raise GroupingError("'clusters' field must be a list")

            # Parse each cluster
            clusters: list[IdeaCluster] = []
            for cluster_data in clusters_data:
                try:
                    cluster = IdeaCluster(**cluster_data)
                    clusters.append(cluster)
                except ValidationError as e:
                    raise GroupingError(f"Invalid cluster data: {e}") from e

            # Validate clusters against input
            is_valid, errors = self._validate_clusters(clusters, input_summaries)
            if not is_valid:
                error_msg = "Cluster validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                raise GroupingError(error_msg)

            return clusters

        except OllamaError as e:
            raise GroupingError(f"Failed to parse LLM response: {e}") from e

    def _resolve_overlaps(
        self,
        clusters: list[IdeaCluster],
        summaries_map: dict[int, SummarizedIssue],
    ) -> list[IdeaCluster]:
        """
        Resolve any overlapping issue assignments deterministically.

        Uses tie-breaking: assign to cluster with smallest cluster_id lexicographically.

        Args:
            clusters: List of clusters potentially with overlaps
            summaries_map: Map of issue_id to SummarizedIssue

        Returns:
            List of clusters with overlaps resolved
        """
        # Track final assignments
        issue_assignments: dict[int, str] = {}

        # Sort clusters by cluster_id for deterministic ordering
        sorted_clusters = sorted(clusters, key=lambda c: c.cluster_id)

        # First pass: identify conflicts
        conflicts: set[int] = set()
        for cluster in sorted_clusters:
            for issue_id in cluster.member_issue_ids:
                if issue_id in issue_assignments:
                    conflicts.add(issue_id)
                else:
                    issue_assignments[issue_id] = cluster.cluster_id

        if not conflicts:
            return clusters  # No overlaps

        logger.warning(f"Resolving {len(conflicts)} overlapping issue assignments")

        # Second pass: rebuild clusters with conflicts resolved
        resolved_clusters: list[IdeaCluster] = []

        for cluster in sorted_clusters:
            # Keep only non-conflicted issues, plus conflicted ones assigned to this cluster
            retained_ids = [
                iid
                for iid in cluster.member_issue_ids
                if self._should_retain_issue_in_cluster(
                    iid, conflicts, issue_assignments, cluster.cluster_id
                )
            ]

            if not retained_ids:
                # Cluster lost all members
                logger.warning(f"Cluster '{cluster.cluster_id}' has no members after resolution")
                continue

            # Recalculate metrics if membership changed
            if len(retained_ids) != len(cluster.member_issue_ids):
                metrics = self._aggregate_metrics([summaries_map[iid] for iid in retained_ids])
                cluster = cluster.model_copy(
                    update={
                        "member_issue_ids": retained_ids,
                        **metrics,
                    }
                )

            resolved_clusters.append(cluster)

        return resolved_clusters

    def _should_retain_issue_in_cluster(
        self,
        issue_id: int,
        conflicts: set[int],
        issue_assignments: dict[int, str],
        cluster_id: str,
    ) -> bool:
        """
        Determine if an issue should be retained in a cluster during conflict resolution.

        Args:
            issue_id: The issue ID to check
            conflicts: Set of conflicted issue IDs
            issue_assignments: Map of issue ID to assigned cluster ID
            cluster_id: The cluster ID being processed

        Returns:
            True if issue should be retained in the cluster
        """
        if issue_id not in conflicts:
            return True  # Non-conflicted issues are always retained
        return issue_assignments.get(issue_id) == cluster_id

    def _aggregate_metrics(self, summaries: list[SummarizedIssue]) -> dict[str, float]:
        """
        Aggregate metrics from multiple summaries.

        Uses average for all metrics, rounded to 2 decimal places.

        Args:
            summaries: List of SummarizedIssues to aggregate

        Returns:
            Dictionary with aggregated metrics
        """
        if not summaries:
            return {
                "novelty": 0.0,
                "feasibility": 0.0,
                "desirability": 0.0,
                "attention": 0.0,
            }

        return {
            "novelty": round(sum(s.novelty for s in summaries) / len(summaries), 2),
            "feasibility": round(sum(s.feasibility for s in summaries) / len(summaries), 2),
            "desirability": round(sum(s.desirability for s in summaries) / len(summaries), 2),
            "attention": round(sum(s.attention for s in summaries) / len(summaries), 2),
        }

    def group_batch(
        self,
        summaries: list[SummarizedIssue],
        retry_on_validation_error: bool = True,
    ) -> list[IdeaCluster]:
        """
        Group a single batch of summaries into clusters.

        Args:
            summaries: Batch of SummarizedIssues to group
            retry_on_validation_error: If True, retry once on validation failure

        Returns:
            List of IdeaClusters

        Raises:
            GroupingError: If grouping fails after retries
        """
        if not summaries:
            return []

        # Format prompt
        prompt = self._format_batch_prompt(summaries)

        # Call LLM
        max_attempts = 2 if retry_on_validation_error else 1

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Grouping batch of {len(summaries)} summaries (attempt {attempt + 1}/{max_attempts})"
                )

                llm_response = self.llm_client.generate(
                    model=self.model,
                    prompt=prompt,
                    system=self.system_prompt,
                    temperature=0.3,  # Lower temperature for consistent clustering
                    format="json",
                )

                # Parse and validate
                clusters = self._parse_llm_response(llm_response, summaries)

                logger.info(f"Successfully created {len(clusters)} clusters from batch")
                return clusters

            except GroupingError as e:
                if "validation failed" in str(e).lower() and attempt < max_attempts - 1:
                    logger.warning(f"Validation error on attempt {attempt + 1}, retrying: {e}")
                    continue
                raise

            except OllamaError as e:
                raise GroupingError(f"LLM request failed: {e}") from e

        # Should not reach here
        raise GroupingError("Failed to group batch after all attempts")

    def _normalize_topic_for_cluster_id(self, topic_area: str) -> str:
        """
        Normalize a topic area string for use in cluster IDs.

        Args:
            topic_area: The raw topic area string

        Returns:
            Normalized topic string (lowercase, spaces and slashes become hyphens)
        """
        return topic_area.lower().replace(" ", "-").replace("/", "-")

    def group_summaries(
        self,
        summaries: list[SummarizedIssue],
        skip_noise: bool = False,
    ) -> list[IdeaCluster]:
        """
        Group multiple summaries into clusters across batches.

        Args:
            summaries: List of SummarizedIssues to group
            skip_noise: If True, skip summaries flagged as noise

        Returns:
            List of IdeaClusters covering all input summaries
        """
        if not summaries:
            logger.info("No summaries to group")
            return []

        # Filter noise if requested
        if skip_noise:
            original_count = len(summaries)
            summaries_to_process = [s for s in summaries if not s.noise_flag]
            skipped = original_count - len(summaries_to_process)
            if skipped > 0:
                logger.info(f"Skipped {skipped} noise-flagged summaries")
        else:
            summaries_to_process = summaries

        if not summaries_to_process:
            logger.info("No non-noise summaries to group")
            return []

        summaries_map = {s.issue_id: s for s in summaries_to_process}

        # Create batches
        batches = self._create_batches(summaries_to_process)
        logger.info(
            f"Created {len(batches)} batches from {len(summaries_to_process)} summaries "
            f"(max_batch_size={self.max_batch_size}, max_batch_chars={self.max_batch_chars})"
        )

        # Process each batch
        all_clusters: list[IdeaCluster] = []
        cluster_sequence: dict[str, int] = {}  # topic -> next sequence number

        for i, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} summaries)...")

            try:
                batch_clusters = self.group_batch(batch)

                # Ensure unique cluster IDs across batches
                for cluster in batch_clusters:
                    topic = self._normalize_topic_for_cluster_id(cluster.topic_area)
                    seq = cluster_sequence.get(topic, 1)

                    # Regenerate cluster_id if needed to avoid conflicts
                    new_id = f"{topic}-{seq:03d}"
                    while any(c.cluster_id == new_id for c in all_clusters):
                        seq += 1
                        new_id = f"{topic}-{seq:03d}"

                    if cluster.cluster_id != new_id:
                        cluster = cluster.model_copy(update={"cluster_id": new_id})

                    cluster_sequence[topic] = seq + 1
                    all_clusters.append(cluster)

                logger.info(f"Batch {i}/{len(batches)}: Created {len(batch_clusters)} clusters")

            except GroupingError as e:
                logger.error(f"Failed to process batch {i}/{len(batches)}: {e}")
                # Continue with remaining batches
                continue

        # Resolve overlaps across all batches
        resolved_clusters = self._resolve_overlaps(all_clusters, summaries_map)

        logger.info(
            f"Grouping complete: {len(resolved_clusters)} total clusters from {len(summaries_to_process)} summaries"
        )

        return resolved_clusters
