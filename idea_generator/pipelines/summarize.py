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
Summarization pipeline for processing normalized issues through the LLM summarizer persona.

This pipeline:
1. Loads cleaned issues one at a time (no batching to avoid context ballooning)
2. Truncates text to fit within configured token limits
3. Calls the LLM with retry logic
4. Validates and parses JSON responses
5. Caches successful summaries by issue ID
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..llm.client import OllamaClient, OllamaError
from ..models import NormalizedIssue, SummarizedIssue

logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    """Base exception for summarization pipeline errors."""

    pass


class SummarizationPipeline:
    """
    Pipeline for summarizing normalized issues using the LLM summarizer persona.

    This pipeline processes issues sequentially (one at a time) to avoid context
    ballooning. Each issue is independently summarized and cached.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        model: str,
        prompt_template_path: Path,
        max_tokens: int = 4000,
        cache_dir: Path | None = None,
    ) -> None:
        """
        Initialize the summarization pipeline.

        Args:
            llm_client: Configured Ollama client instance
            model: Name of the model to use for summarization
            prompt_template_path: Path to the system prompt template file
            max_tokens: Maximum tokens for issue text (rough estimate: ~4 chars/token)
            cache_dir: Directory for caching successful summaries (optional)
        """
        self.llm_client = llm_client
        self.model = model
        self.max_tokens = max_tokens
        self.cache_dir = cache_dir

        # Load system prompt
        if not prompt_template_path.exists():
            raise SummarizationError(
                f"Prompt template not found: {prompt_template_path}"
            )

        with open(prompt_template_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

        # Ensure cache directory exists
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, issue_id: int) -> Path | None:
        """Get cache file path for an issue."""
        if not self.cache_dir:
            return None
        return self.cache_dir / f"summary_{issue_id}.json"

    def _load_from_cache(self, issue_id: int) -> SummarizedIssue | None:
        """
        Load a cached summary if available.

        Args:
            issue_id: GitHub issue ID

        Returns:
            Cached SummarizedIssue or None if not cached
        """
        cache_path = self._get_cache_path(issue_id)
        if not cache_path or not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SummarizedIssue(**data)
        except Exception as e:
            logger.warning(f"Failed to load cache for issue {issue_id}: {e}")
            return None

    def _save_to_cache(self, summary: SummarizedIssue) -> None:
        """
        Save a summary to cache.

        Args:
            summary: SummarizedIssue to cache
        """
        cache_path = self._get_cache_path(summary.issue_id)
        if not cache_path:
            return

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(summary.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save cache for issue {summary.issue_id}: {e}")

    def _truncate_text(self, text: str, max_chars: int) -> tuple[str, bool]:
        """
        Truncate text to fit within character limit.

        Args:
            text: Text to truncate
            max_chars: Maximum number of characters

        Returns:
            Tuple of (truncated_text, was_truncated)
        """
        if len(text) <= max_chars:
            return text, False

        # Truncate at word boundary
        truncated = text[:max_chars].rsplit(" ", 1)[0]
        return truncated + "...", True

    def _format_issue_prompt(self, issue: NormalizedIssue) -> str:
        """
        Format a normalized issue into a prompt for the LLM.

        Args:
            issue: NormalizedIssue to format

        Returns:
            Formatted prompt string
        """
        # Calculate character budget (rough estimate: 4 chars per token)
        max_chars = self.max_tokens * 4

        # Reserve space for metadata and structure (~500 chars)
        available_chars = max_chars - 500

        # Allocate 40% to body, 60% to comments
        body_budget = int(available_chars * 0.4)
        comments_budget = int(available_chars * 0.6)

        # Truncate body
        body_text, body_truncated = self._truncate_text(issue.body, body_budget)

        # Format comments
        comments_text = ""
        comments_truncated = False
        if issue.comments:
            comments_parts = []
            remaining = comments_budget

            for comment in issue.comments:
                # Format: "- [Author]: Comment body"
                author = comment.author or "deleted-user"
                comment_line = f"- [{author}]: {comment.body}"

                if len(comment_line) <= remaining:
                    comments_parts.append(comment_line)
                    remaining -= len(comment_line) + 1  # +1 for newline
                else:
                    comments_truncated = True
                    break

            comments_text = "\n".join(comments_parts)

        # Format reactions
        total_reactions = sum(issue.reactions.values())
        reaction_str = f"{total_reactions} reactions" if total_reactions > 0 else "0 reactions"

        # Build prompt
        prompt_parts = [
            f"Title: {issue.title}",
            f"Body: {body_text}",
        ]

        if body_truncated:
            prompt_parts.append("(Body truncated due to length)")

        if comments_text:
            prompt_parts.append(f"Comments:\n{comments_text}")
            if comments_truncated:
                prompt_parts.append("(Additional comments truncated)")

        prompt_parts.append(f"Reactions: {reaction_str}")

        if issue.labels:
            prompt_parts.append(f"Labels: {', '.join(issue.labels)}")

        prompt_parts.append(
            "\nAnalyze this issue and respond with ONLY valid JSON following the specified schema."
        )

        return "\n\n".join(prompt_parts)

    def _parse_llm_response(
        self, issue: NormalizedIssue, llm_response: dict[str, Any]
    ) -> SummarizedIssue:
        """
        Parse and validate LLM response into a SummarizedIssue.

        Args:
            issue: Original NormalizedIssue
            llm_response: Raw response from LLM client

        Returns:
            Validated SummarizedIssue

        Raises:
            SummarizationError: If response is invalid or missing required fields
        """
        try:
            # Extract JSON from response
            parsed_json = self.llm_client.parse_json_response(llm_response)

            # Validate required fields
            required_fields = [
                "title",
                "summary",
                "topic_area",
                "novelty",
                "feasibility",
                "desirability",
                "attention",
                "noise_flag",
            ]
            missing = [f for f in required_fields if f not in parsed_json]
            if missing:
                raise SummarizationError(
                    f"LLM response missing required fields: {missing}"
                )

            # Create SummarizedIssue with data from both sources
            summary_data = {
                "issue_id": issue.id,
                "source_number": issue.number,
                "raw_issue_url": issue.url,
                **parsed_json,
            }

            return SummarizedIssue(**summary_data)

        except ValidationError as e:
            raise SummarizationError(f"Invalid summary data: {e}") from e
        except OllamaError as e:
            raise SummarizationError(f"Failed to parse LLM response: {e}") from e

    def summarize_issue(
        self, issue: NormalizedIssue, skip_cache: bool = False
    ) -> SummarizedIssue:
        """
        Summarize a single normalized issue using the LLM.

        Args:
            issue: NormalizedIssue to summarize
            skip_cache: If True, bypass cache and regenerate summary

        Returns:
            SummarizedIssue with metrics and summary

        Raises:
            SummarizationError: If summarization fails after retries
        """
        # Check cache first
        if not skip_cache:
            cached = self._load_from_cache(issue.id)
            if cached:
                logger.info(f"Using cached summary for issue #{issue.number}")
                return cached

        # Format prompt
        prompt = self._format_issue_prompt(issue)

        # Call LLM
        try:
            logger.info(f"Summarizing issue #{issue.number} (ID: {issue.id})")
            llm_response = self.llm_client.generate(
                model=self.model,
                prompt=prompt,
                system=self.system_prompt,
                temperature=0.3,  # Lower temperature for more consistent output
                format="json",
            )

            # Parse and validate response
            summary = self._parse_llm_response(issue, llm_response)

            # Cache successful summary
            self._save_to_cache(summary)

            logger.info(
                f"Successfully summarized issue #{issue.number} "
                f"(novelty: {summary.novelty:.2f}, feasibility: {summary.feasibility:.2f})"
            )

            return summary

        except OllamaError as e:
            raise SummarizationError(
                f"Failed to generate summary for issue #{issue.number}: {e}"
            ) from e

    def summarize_issues(
        self,
        issues: list[NormalizedIssue],
        skip_cache: bool = False,
        skip_noise: bool = False,
    ) -> list[SummarizedIssue]:
        """
        Summarize multiple issues sequentially.

        Args:
            issues: List of NormalizedIssues to summarize
            skip_cache: If True, bypass cache and regenerate all summaries
            skip_noise: If True, skip issues already flagged as noise

        Returns:
            List of SummarizedIssues (may be shorter if some fail)
        """
        summaries = []
        failed_count = 0

        for i, issue in enumerate(issues, 1):
            # Skip noise if requested
            if skip_noise and issue.is_noise:
                logger.info(
                    f"[{i}/{len(issues)}] Skipping noise issue #{issue.number}"
                )
                continue

            logger.info(f"[{i}/{len(issues)}] Processing issue #{issue.number}...")

            try:
                summary = self.summarize_issue(issue, skip_cache=skip_cache)
                summaries.append(summary)
            except SummarizationError as e:
                logger.error(f"Failed to summarize issue #{issue.number}: {e}")
                failed_count += 1
                continue

        logger.info(
            f"Summarization complete: {len(summaries)} succeeded, {failed_count} failed"
        )

        return summaries
