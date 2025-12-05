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
Tests for orchestration pipeline.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from idea_generator.config import Config
from idea_generator.models import IdeaCluster, NormalizedIssue, SummarizedIssue
from idea_generator.pipelines.orchestrator import Orchestrator, OrchestratorError


@pytest.fixture
def temp_config() -> Config:
    """Create a temporary configuration for testing."""
    with TemporaryDirectory() as tmpdir:
        config = Config(
            github_repo="owner/repo",
            github_token="test_token",
            output_dir=Path(tmpdir) / "output",
            data_dir=Path(tmpdir) / "data",
            persona_dir=Path(tmpdir) / "personas",
        )
        yield config


@pytest.fixture
def sample_issue() -> NormalizedIssue:
    """Create a sample normalized issue."""
    return NormalizedIssue(
        id=100,
        number=1,
        title="Test issue",
        body="Test body",
        labels=["bug"],
        state="open",
        reactions={"+1": 5},
        comments=[],
        url="https://github.com/owner/repo/issues/1",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        is_noise=False,
    )


@pytest.fixture
def sample_summary() -> SummarizedIssue:
    """Create a sample summarized issue."""
    return SummarizedIssue(
        issue_id=100,
        source_number=1,
        title="Test issue",
        summary="Test summary",
        topic_area="bug",
        novelty=0.5,
        feasibility=0.7,
        desirability=0.8,
        attention=0.6,
        noise_flag=False,
        raw_issue_url="https://github.com/owner/repo/issues/1",
    )


@pytest.fixture
def sample_cluster() -> IdeaCluster:
    """Create a sample idea cluster."""
    return IdeaCluster(
        cluster_id="cluster-1",
        representative_title="Test cluster",
        summary="Test cluster summary",
        topic_area="bug",
        member_issue_ids=[100],
        novelty=0.5,
        feasibility=0.7,
        desirability=0.8,
        attention=0.6,
    )


class TestOrchestratorInit:
    """Tests for Orchestrator initialization."""

    def test_initialization(self, temp_config: Config) -> None:
        """Test that orchestrator initializes correctly."""
        orchestrator = Orchestrator(temp_config)
        assert orchestrator.config == temp_config

    def test_creates_directories(self, temp_config: Config) -> None:
        """Test that required directories are created."""
        Orchestrator(temp_config)
        assert temp_config.output_dir.exists()
        assert temp_config.data_dir.exists()


class TestOrchestratorRun:
    """Tests for Orchestrator.run method."""

    def test_requires_github_repo(self) -> None:
        """Test that github_repo is required."""
        with TemporaryDirectory() as tmpdir:
            config = Config(
                github_repo="",  # Empty repo
                output_dir=Path(tmpdir) / "output",
                data_dir=Path(tmpdir) / "data",
            )
            orchestrator = Orchestrator(config)

            with pytest.raises(OrchestratorError, match="not configured"):
                orchestrator.run()

    def test_invalid_repo_format(self) -> None:
        """Test that invalid repo format raises error during config creation."""
        with TemporaryDirectory() as tmpdir:
            # Config validation should fail for invalid format
            with pytest.raises(ValueError, match="owner/repo"):
                Config(
                    github_repo="invalid-format",  # Missing slash
                    output_dir=Path(tmpdir) / "output",
                    data_dir=Path(tmpdir) / "data",
                )

    @patch("idea_generator.pipelines.orchestrator.GitHubClient")
    def test_handles_no_issues(
        self,
        mock_github_client: Mock,
        temp_config: Config,
    ) -> None:
        """Test that empty repository generates empty reports."""
        # Mock GitHub client to return no issues
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.check_repository_access = Mock(return_value=True)
        mock_client.fetch_issues = Mock(return_value=[])
        mock_github_client.return_value = mock_client

        orchestrator = Orchestrator(temp_config)
        results = orchestrator.run()

        # Should have empty reports
        reports_dir = temp_config.output_dir / "reports"
        assert reports_dir.exists()

        json_path = reports_dir / "ideas.json"
        assert json_path.exists()
        with open(json_path) as f:
            data = json.load(f)
        assert data == []

        md_path = reports_dir / "top-ideas.md"
        assert md_path.exists()
        with open(md_path) as f:
            content = f.read()
        assert "No open issues" in content

    @patch("idea_generator.pipelines.orchestrator.GitHubClient")
    @patch("idea_generator.pipelines.orchestrator.OllamaClient")
    @patch("idea_generator.pipelines.orchestrator.SummarizationPipeline")
    @patch("idea_generator.pipelines.orchestrator.GroupingPipeline")
    def test_full_pipeline_execution(
        self,
        mock_grouping_pipeline: Mock,
        mock_summarization_pipeline: Mock,
        mock_ollama_client: Mock,
        mock_github_client: Mock,
        temp_config: Config,
        sample_issue: NormalizedIssue,
        sample_summary: SummarizedIssue,
        sample_cluster: IdeaCluster,
    ) -> None:
        """Test full pipeline execution with mocked stages."""
        # Mock GitHub client
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.check_repository_access = Mock(return_value=True)
        mock_client.fetch_issues = Mock(
            return_value=[
                {
                    "id": 100,
                    "number": 1,
                    "title": "Test issue",
                    "body": "Test body",
                    "labels": [{"name": "bug"}],
                    "state": "open",
                    "reactions": {"+1": 5},
                    "html_url": "https://github.com/owner/repo/issues/1",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-02T00:00:00Z",
                }
            ]
        )
        mock_client.fetch_issue_comments = Mock(return_value=[])
        mock_github_client.return_value = mock_client

        # Mock Ollama client
        mock_llm = Mock()
        mock_llm.check_health = Mock(return_value=True)
        mock_llm.close = Mock()
        mock_ollama_client.return_value = mock_llm

        # Mock summarization pipeline
        mock_sum_pipeline = Mock()
        mock_sum_pipeline.summarize_issues = Mock(return_value=[sample_summary])
        mock_summarization_pipeline.return_value = mock_sum_pipeline

        # Mock grouping pipeline
        mock_group_pipeline = Mock()
        mock_group_pipeline.group_summaries = Mock(return_value=[sample_cluster])
        mock_grouping_pipeline.return_value = mock_group_pipeline

        orchestrator = Orchestrator(temp_config)
        results = orchestrator.run()

        # Verify results
        assert "issues_count" in results
        assert "summaries_count" in results
        assert "clusters_count" in results
        assert "json_report" in results
        assert "markdown_report" in results

        # Verify reports were created
        json_path = results["json_report"]
        assert json_path.exists()

        md_path = results["markdown_report"]
        assert md_path.exists()

    @patch("idea_generator.pipelines.orchestrator.GitHubClient")
    @patch("idea_generator.pipelines.orchestrator.OllamaClient")
    @patch("idea_generator.pipelines.orchestrator.SummarizationPipeline")
    @patch("idea_generator.pipelines.orchestrator.GroupingPipeline")
    def test_skip_json_flag(
        self,
        mock_grouping_pipeline: Mock,
        mock_summarization_pipeline: Mock,
        mock_ollama_client: Mock,
        mock_github_client: Mock,
        temp_config: Config,
        sample_issue: NormalizedIssue,
        sample_summary: SummarizedIssue,
        sample_cluster: IdeaCluster,
    ) -> None:
        """Test that skip_json flag prevents JSON generation."""
        # Setup mocks (same as full pipeline test)
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.check_repository_access = Mock(return_value=True)
        mock_client.fetch_issues = Mock(
            return_value=[
                {
                    "id": 100,
                    "number": 1,
                    "title": "Test",
                    "body": "Test",
                    "labels": [],
                    "state": "open",
                    "reactions": {},
                    "html_url": "https://github.com/owner/repo/issues/1",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-02T00:00:00Z",
                }
            ]
        )
        mock_client.fetch_issue_comments = Mock(return_value=[])
        mock_github_client.return_value = mock_client

        mock_llm = Mock()
        mock_llm.check_health = Mock(return_value=True)
        mock_llm.close = Mock()
        mock_ollama_client.return_value = mock_llm

        mock_sum_pipeline = Mock()
        mock_sum_pipeline.summarize_issues = Mock(return_value=[sample_summary])
        mock_summarization_pipeline.return_value = mock_sum_pipeline

        mock_group_pipeline = Mock()
        mock_group_pipeline.group_summaries = Mock(return_value=[sample_cluster])
        mock_grouping_pipeline.return_value = mock_group_pipeline

        orchestrator = Orchestrator(temp_config)
        results = orchestrator.run(skip_json=True)

        # JSON should not be generated
        assert "json_report" not in results

        # But Markdown should still be generated
        assert "markdown_report" in results

    @patch("idea_generator.pipelines.orchestrator.GitHubClient")
    @patch("idea_generator.pipelines.orchestrator.OllamaClient")
    @patch("idea_generator.pipelines.orchestrator.SummarizationPipeline")
    @patch("idea_generator.pipelines.orchestrator.GroupingPipeline")
    def test_skip_markdown_flag(
        self,
        mock_grouping_pipeline: Mock,
        mock_summarization_pipeline: Mock,
        mock_ollama_client: Mock,
        mock_github_client: Mock,
        temp_config: Config,
        sample_issue: NormalizedIssue,
        sample_summary: SummarizedIssue,
        sample_cluster: IdeaCluster,
    ) -> None:
        """Test that skip_markdown flag prevents Markdown generation."""
        # Setup mocks (same as full pipeline test)
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.check_repository_access = Mock(return_value=True)
        mock_client.fetch_issues = Mock(
            return_value=[
                {
                    "id": 100,
                    "number": 1,
                    "title": "Test",
                    "body": "Test",
                    "labels": [],
                    "state": "open",
                    "reactions": {},
                    "html_url": "https://github.com/owner/repo/issues/1",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-02T00:00:00Z",
                }
            ]
        )
        mock_client.fetch_issue_comments = Mock(return_value=[])
        mock_github_client.return_value = mock_client

        mock_llm = Mock()
        mock_llm.check_health = Mock(return_value=True)
        mock_llm.close = Mock()
        mock_ollama_client.return_value = mock_llm

        mock_sum_pipeline = Mock()
        mock_sum_pipeline.summarize_issues = Mock(return_value=[sample_summary])
        mock_summarization_pipeline.return_value = mock_sum_pipeline

        mock_group_pipeline = Mock()
        mock_group_pipeline.group_summaries = Mock(return_value=[sample_cluster])
        mock_grouping_pipeline.return_value = mock_group_pipeline

        orchestrator = Orchestrator(temp_config)
        results = orchestrator.run(skip_markdown=True)

        # Markdown should not be generated
        assert "markdown_report" not in results

        # But JSON should still be generated
        assert "json_report" in results


class TestOrchestratorCaching:
    """Tests for orchestrator caching behavior."""

    @patch("idea_generator.pipelines.orchestrator.GitHubClient")
    def test_uses_cached_issues(
        self,
        mock_github_client: Mock,
        temp_config: Config,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test that cached issues are reused."""
        # Create cached issues file
        issues_file = temp_config.data_dir / "owner_repo_issues.json"
        issues_file.parent.mkdir(parents=True, exist_ok=True)
        with open(issues_file, "w") as f:
            json.dump([sample_issue.model_dump(mode="json")], f)

        orchestrator = Orchestrator(temp_config)

        # Mock should not be called since we have cached data
        # But we need to mock the downstream stages
        with patch(
            "idea_generator.pipelines.orchestrator.OllamaClient"
        ) as mock_ollama:
            mock_llm = Mock()
            mock_llm.check_health = Mock(return_value=True)
            mock_llm.close = Mock()
            mock_ollama.return_value = mock_llm

            with patch(
                "idea_generator.pipelines.orchestrator.SummarizationPipeline"
            ) as mock_sum:
                mock_sum_pipeline = Mock()
                mock_sum_pipeline.summarize_issues = Mock(return_value=[])
                mock_sum.return_value = mock_sum_pipeline

                # This should use cached issues without calling GitHub API
                orchestrator._ingest_issues = Mock(return_value=[sample_issue])
                results = orchestrator.run()

                # Verify GitHub client was not instantiated
                mock_github_client.assert_not_called()
