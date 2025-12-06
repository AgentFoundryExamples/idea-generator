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
Orchestration pipeline for end-to-end idea generation.

This module chains:
1. Ingest (fetch issues from GitHub)
2. Summarize (process with LLM)
3. Group (cluster similar issues)
4. Rank (compute scores and sort)
5. Output (generate JSON and Markdown reports)

Artifacts are cached to enable resumption after failures.
"""

import json
import logging
from pathlib import Path

from ..cleaning import normalize_github_issue
from ..config import Config
from ..filters import rank_clusters
from ..github_client import GitHubAPIError, GitHubClient
from ..llm.client import OllamaClient, OllamaError
from ..models import IdeaCluster, NormalizedIssue, SummarizedIssue
from ..output import generate_json_report, generate_markdown_report
from .grouping import GroupingPipeline
from .summarize import SummarizationPipeline

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Base exception for orchestrator pipeline errors."""

    pass


class Orchestrator:
    """
    End-to-end pipeline orchestrator for idea generation.

    Chains all stages: ingest → summarize → group → rank → output.
    Caches intermediate artifacts to enable resumption.
    """

    def __init__(self, config: Config) -> None:
        """
        Initialize the orchestrator.

        Args:
            config: Configuration object with all settings
        """
        self.config = config
        config.ensure_directories()

    def run(
        self,
        force: bool = False,
        skip_json: bool = False,
        skip_markdown: bool = False,
    ) -> dict[str, Path | int]:
        """
        Run the complete pipeline end-to-end.

        Args:
            force: If True, regenerate all artifacts even if cached
            skip_json: If True, skip JSON report generation
            skip_markdown: If True, skip Markdown report generation

        Returns:
            Dictionary with artifact paths and statistics

        Raises:
            OrchestratorError: If any stage fails
        """
        logger.info("Starting orchestration pipeline...")
        results: dict[str, Path | int] = {}

        # Validate config
        if not self.config.github_repo:
            raise OrchestratorError("GitHub repository not configured")

        try:
            owner, repo = self.config.github_repo.split("/")
        except ValueError:
            raise OrchestratorError(
                f"Invalid repository format: {self.config.github_repo}"
            ) from None

        # Stage 1: Ingest issues
        logger.info("Stage 1: Ingesting issues from GitHub...")
        issues_file = self.config.data_dir / f"{owner}_{repo}_issues.json"
        if force or not issues_file.exists():
            issues = self._ingest_issues(owner, repo)
            results["issues_count"] = len(issues)
        else:
            logger.info(f"Using cached issues from {issues_file}")
            with open(issues_file, encoding="utf-8") as f:
                issues_data = json.load(f)
            issues = [NormalizedIssue(**data) for data in issues_data]
            results["issues_count"] = len(issues)

        if not issues:
            logger.warning("No issues found. Generating empty reports.")
            self._generate_empty_reports(skip_json, skip_markdown)
            return results

        # Stage 2: Summarize issues
        logger.info("Stage 2: Summarizing issues with LLM...")
        summaries_file = self.config.output_dir / f"{owner}_{repo}_summaries.json"
        if force or not summaries_file.exists():
            summaries = self._summarize_issues(issues)
            results["summaries_count"] = len(summaries)
        else:
            logger.info(f"Using cached summaries from {summaries_file}")
            with open(summaries_file, encoding="utf-8") as f:
                summaries_data = json.load(f)
            summaries = [SummarizedIssue(**data) for data in summaries_data]
            results["summaries_count"] = len(summaries)

        if not summaries:
            logger.warning("No summaries generated. Generating empty reports.")
            self._generate_empty_reports(skip_json, skip_markdown)
            return results

        # Stage 3: Group summaries into clusters
        logger.info("Stage 3: Grouping summaries into clusters...")
        clusters_file = self.config.output_dir / f"{owner}_{repo}_clusters.json"
        if force or not clusters_file.exists():
            clusters = self._group_summaries(summaries)
            results["clusters_count"] = len(clusters)
        else:
            logger.info(f"Using cached clusters from {clusters_file}")
            with open(clusters_file, encoding="utf-8") as f:
                clusters_data = json.load(f)
            clusters = [IdeaCluster(**data) for data in clusters_data]
            results["clusters_count"] = len(clusters)

        if not clusters:
            logger.warning("No clusters generated. Generating empty reports.")
            self._generate_empty_reports(skip_json, skip_markdown)
            return results

        # Stage 4: Rank clusters
        logger.info("Stage 4: Ranking clusters by composite score...")
        # Note: weights are automatically validated during config initialization
        ranked_clusters = rank_clusters(
            clusters,
            weight_novelty=self.config.ranking_weight_novelty,
            weight_feasibility=self.config.ranking_weight_feasibility,
            weight_desirability=self.config.ranking_weight_desirability,
            weight_attention=self.config.ranking_weight_attention,
        )

        # Stage 5: Generate reports
        logger.info("Stage 5: Generating reports...")
        reports_dir = self.config.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True)

        # Generate JSON report
        if not skip_json:
            json_path = reports_dir / "ideas.json"
            logger.info(f"Generating JSON report: {json_path}")
            generate_json_report(
                ranked_clusters,
                issues,
                json_path,
                weight_novelty=self.config.ranking_weight_novelty,
                weight_feasibility=self.config.ranking_weight_feasibility,
                weight_desirability=self.config.ranking_weight_desirability,
                weight_attention=self.config.ranking_weight_attention,
            )
            results["json_report"] = json_path

        # Generate Markdown report
        if not skip_markdown:
            md_path = reports_dir / "top-ideas.md"
            logger.info(f"Generating Markdown report: {md_path}")
            generate_markdown_report(
                ranked_clusters,
                issues,
                md_path,
                top_n=self.config.top_ideas_count,
                weight_novelty=self.config.ranking_weight_novelty,
                weight_feasibility=self.config.ranking_weight_feasibility,
                weight_desirability=self.config.ranking_weight_desirability,
                weight_attention=self.config.ranking_weight_attention,
            )
            results["markdown_report"] = md_path

        logger.info("Pipeline completed successfully!")
        return results

    def _ingest_issues(self, owner: str, repo: str) -> list[NormalizedIssue]:
        """
        Ingest issues from GitHub and save to cache.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of normalized issues

        Raises:
            OrchestratorError: If ingestion fails
        """
        cache_dir = self.config.data_dir / "cache"
        cache_dir.mkdir(exist_ok=True)

        try:
            with GitHubClient(
                token=self.config.github_token,
                per_page=self.config.github_per_page,
                max_retries=self.config.github_max_retries,
                cache_dir=cache_dir,
            ) as client:
                # Check repository access
                if not client.check_repository_access(owner, repo):
                    raise OrchestratorError(f"Repository {owner}/{repo} not accessible")

                # Fetch issues
                issues_data = client.fetch_issues(owner, repo, state="open", limit=self.config.github_issue_limit)
                if not issues_data:
                    logger.warning("No open issues found")
                    return []

                # Normalize issues
                normalized_issues: list[NormalizedIssue] = []
                for issue_data in issues_data:
                    comments = client.fetch_issue_comments(owner, repo, issue_data["number"])
                    normalized = normalize_github_issue(
                        issue_data,
                        comments,
                        max_text_length=self.config.max_text_length,
                        noise_filter_enabled=self.config.noise_filter_enabled,
                    )
                    normalized_issues.append(normalized)

                # Save to cache
                issues_file = self.config.data_dir / f"{owner}_{repo}_issues.json"
                with open(issues_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [issue.model_dump(mode="json") for issue in normalized_issues],
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                return normalized_issues

        except GitHubAPIError as e:
            raise OrchestratorError(f"Failed to ingest issues from GitHub: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error during issue ingestion")
            raise OrchestratorError(
                f"Failed to ingest issues: {e.__class__.__name__}: {e}"
            ) from e

    def _summarize_issues(self, issues: list[NormalizedIssue]) -> list[SummarizedIssue]:
        """
        Summarize issues using LLM and save to cache.

        Args:
            issues: List of normalized issues

        Returns:
            List of summarized issues

        Raises:
            OrchestratorError: If summarization fails
        """
        prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / "summarizer.txt"
        cache_dir = self.config.output_dir / "summarization_cache"

        try:
            llm_client = OllamaClient(
                base_url=self.config.ollama_base_url,
                timeout=self.config.llm_timeout,
                max_retries=self.config.llm_max_retries,
            )

            try:
                if not llm_client.check_health():
                    raise OrchestratorError(
                        f"Ollama server not reachable at {self.config.ollama_base_url}"
                    )

                # Validate that the summarization model exists
                model_name = self.config.model_summarizing
                if not llm_client.model_exists(model_name):
                    raise OrchestratorError(
                        f"Summarization model '{model_name}' not found on Ollama server. "
                        f"Available models: {', '.join(llm_client.list_models()) or 'none'}. "
                        f"Build the model with: "
                        f"ollama create {model_name} -f idea_generator/llm/modelfiles/summarizer.Modelfile"
                    )

                pipeline = SummarizationPipeline(
                    llm_client=llm_client,
                    model=model_name,
                    prompt_template_path=prompt_path,
                    max_tokens=self.config.summarization_max_tokens,
                    cache_dir=cache_dir,
                    cache_max_file_size=self.config.cache_max_file_size,
                )

                summaries = pipeline.summarize_issues(issues, skip_cache=False, skip_noise=False)

                # Save to cache
                owner, repo = self.config.github_repo.split("/")
                summaries_file = self.config.output_dir / f"{owner}_{repo}_summaries.json"
                with open(summaries_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [s.model_dump(mode="json") for s in summaries],
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                return summaries
            finally:
                llm_client.close()

        except OllamaError as e:
            logger.exception("Ollama error during summarization")
            raise OrchestratorError(
                f"Failed to summarize issues due to LLM error: {e.__class__.__name__}: {e}"
            ) from e
        except Exception as e:
            logger.exception("Unexpected error during summarization")
            raise OrchestratorError(
                f"Failed to summarize issues: {e.__class__.__name__}: {e}"
            ) from e

    def _group_summaries(self, summaries: list[SummarizedIssue]) -> list[IdeaCluster]:
        """
        Group summaries into clusters and save to cache.

        Args:
            summaries: List of summarized issues

        Returns:
            List of idea clusters

        Raises:
            OrchestratorError: If grouping fails
        """
        prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / "grouper.txt"

        try:
            llm_client = OllamaClient(
                base_url=self.config.ollama_base_url,
                timeout=self.config.llm_timeout,
                max_retries=self.config.llm_max_retries,
            )

            try:
                if not llm_client.check_health():
                    raise OrchestratorError(
                        f"Ollama server not reachable at {self.config.ollama_base_url}"
                    )

                # Validate that the grouping model exists
                model_name = self.config.model_grouping
                if not llm_client.model_exists(model_name):
                    raise OrchestratorError(
                        f"Grouping model '{model_name}' not found on Ollama server. "
                        f"Available models: {', '.join(llm_client.list_models()) or 'none'}. "
                        f"Build the model with: "
                        f"ollama create {model_name} -f idea_generator/llm/modelfiles/grouping.Modelfile"
                    )

                pipeline = GroupingPipeline(
                    llm_client=llm_client,
                    model=model_name,
                    prompt_template_path=prompt_path,
                    max_batch_size=self.config.grouping_max_batch_size,
                    max_batch_chars=self.config.grouping_max_batch_chars,
                )

                clusters = pipeline.group_summaries(summaries, skip_noise=False)

                # Save to cache
                owner, repo = self.config.github_repo.split("/")
                clusters_file = self.config.output_dir / f"{owner}_{repo}_clusters.json"
                with open(clusters_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [c.model_dump(mode="json") for c in clusters],
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                return clusters
            finally:
                llm_client.close()

        except OllamaError as e:
            logger.exception("Ollama error during grouping")
            raise OrchestratorError(
                f"Failed to group summaries due to LLM error: {e.__class__.__name__}: {e}"
            ) from e
        except Exception as e:
            logger.exception("Unexpected error during grouping")
            raise OrchestratorError(
                f"Failed to group summaries: {e.__class__.__name__}: {e}"
            ) from e

    def _generate_empty_reports(self, skip_json: bool, skip_markdown: bool) -> None:
        """
        Generate empty reports when no data is available.

        Args:
            skip_json: If True, skip JSON report
            skip_markdown: If True, skip Markdown report
        """
        reports_dir = self.config.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True)

        if not skip_json:
            json_path = reports_dir / "ideas.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            logger.info(f"Generated empty JSON report: {json_path}")

        if not skip_markdown:
            md_path = reports_dir / "top-ideas.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Top Ideas Report\n\n")
                f.write("No open issues found in the repository.\n")
            logger.info(f"Generated empty Markdown report: {md_path}")
