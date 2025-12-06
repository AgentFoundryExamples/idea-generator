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
Tests for the grouping pipeline.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from idea_generator.llm.client import OllamaClient, OllamaError
from idea_generator.models import IdeaCluster, SummarizedIssue
from idea_generator.pipelines.grouping import GroupingError, GroupingPipeline


@pytest.fixture
def sample_summaries() -> list[SummarizedIssue]:
    """Create sample summarized issues for testing."""
    return [
        SummarizedIssue(
            issue_id=100,
            source_number=1,
            title="Add dark mode",
            summary="Users want dark mode.",
            topic_area="UI/UX",
            novelty=0.3,
            feasibility=0.8,
            desirability=0.9,
            attention=0.7,
            noise_flag=False,
            raw_issue_url="https://github.com/owner/repo/issues/1",
        ),
        SummarizedIssue(
            issue_id=101,
            source_number=2,
            title="Theme switching",
            summary="Support theme customization.",
            topic_area="UI/UX",
            novelty=0.4,
            feasibility=0.7,
            desirability=0.85,
            attention=0.6,
            noise_flag=False,
            raw_issue_url="https://github.com/owner/repo/issues/2",
        ),
        SummarizedIssue(
            issue_id=102,
            source_number=3,
            title="Fix security bug",
            summary="Critical auth vulnerability.",
            topic_area="security",
            novelty=0.2,
            feasibility=0.9,
            desirability=1.0,
            attention=0.9,
            noise_flag=False,
            raw_issue_url="https://github.com/owner/repo/issues/3",
        ),
    ]


@pytest.fixture
def noise_summary() -> SummarizedIssue:
    """Create a noise-flagged summary for testing."""
    return SummarizedIssue(
        issue_id=999,
        source_number=99,
        title="test",
        summary="test issue",
        topic_area="other",
        novelty=0.1,
        feasibility=0.5,
        desirability=0.1,
        attention=0.1,
        noise_flag=True,
        raw_issue_url="https://github.com/owner/repo/issues/99",
    )


@pytest.fixture
def mock_llm_client() -> Mock:
    """Create a mock LLM client."""
    client = Mock(spec=OllamaClient)
    return client


@pytest.fixture
def temp_prompt_file() -> Path:
    """Create a temporary prompt file."""
    with TemporaryDirectory() as tmpdir:
        prompt_path = Path(tmpdir) / "grouper.txt"
        prompt_path.write_text(
            "You are a test grouper. Respond with valid JSON containing a 'clusters' array."
        )
        yield prompt_path


class TestGroupingPipelineInit:
    """Tests for pipeline initialization."""

    def test_pipeline_initialization(self, mock_llm_client: Mock, temp_prompt_file: Path) -> None:
        """Test that pipeline initializes correctly."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_batch_size=20,
            max_batch_chars=50000,
        )

        assert pipeline.llm_client == mock_llm_client
        assert pipeline.model == "llama3.2:latest"
        assert pipeline.max_batch_size == 20
        assert pipeline.max_batch_chars == 50000
        assert len(pipeline.system_prompt) > 0

    def test_pipeline_missing_prompt_template(self, mock_llm_client: Mock) -> None:
        """Test error when prompt template doesn't exist."""
        with pytest.raises(GroupingError, match="Prompt template not found"):
            GroupingPipeline(
                llm_client=mock_llm_client,
                model="llama3.2:latest",
                prompt_template_path=Path("/nonexistent/grouper.txt"),
            )

    def test_prompt_contains_schema_reminders(self, mock_llm_client: Mock) -> None:
        """Test that prompt template contains explicit schema field requirements."""
        try:
            from importlib.resources import files
        except ImportError:
            pytest.skip("importlib.resources.files not available")
        
        try:
            prompt_path = files("idea_generator.llm.prompts").joinpath("grouper.txt")
            prompt_text = prompt_path.read_text()
        except (ModuleNotFoundError, FileNotFoundError):
            pytest.skip("Prompt template not found in expected location")
        
        # Verify schema reminders are present
        assert "Required JSON Schema" in prompt_text, "Prompt should contain explicit schema section"
        assert "clusters" in prompt_text, "Prompt should specify clusters field"
        assert "cluster_id" in prompt_text, "Prompt should specify cluster_id field"
        assert "representative_title" in prompt_text, "Prompt should specify representative_title field"
        assert "member_issue_ids" in prompt_text, "Prompt should specify member_issue_ids field"
        assert "novelty" in prompt_text, "Prompt should specify novelty field"
        assert "feasibility" in prompt_text, "Prompt should specify feasibility field"
        assert "desirability" in prompt_text, "Prompt should specify desirability field"
        assert "attention" in prompt_text, "Prompt should specify attention field"
        assert "0.0" in prompt_text and "1.0" in prompt_text, "Prompt should specify metric ranges"
        # Check for warning against extra fields using flexible assertion
        assert ("extra" in prompt_text.lower() and "field" in prompt_text.lower()), "Prompt should warn against extra fields"
        assert "newline" in prompt_text.lower(), "Prompt should mention newline handling"


class TestCreateBatches:
    """Tests for batch creation logic."""

    def test_create_batches_empty_list(self, mock_llm_client: Mock, temp_prompt_file: Path) -> None:
        """Test batching with empty input."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        batches = pipeline._create_batches([])
        assert batches == []

    def test_create_batches_single_batch(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test batching when all summaries fit in one batch."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_batch_size=10,
            max_batch_chars=100000,
        )

        batches = pipeline._create_batches(sample_summaries)
        assert len(batches) == 1
        assert batches[0] == sample_summaries

    def test_create_batches_by_size(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test batching splits by max_batch_size."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_batch_size=2,  # Small batch size
            max_batch_chars=1000000,
        )

        batches = pipeline._create_batches(sample_summaries)
        assert len(batches) == 2  # 3 summaries, batch size 2 -> 2 batches
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_create_batches_by_chars(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
    ) -> None:
        """Test batching splits by max_batch_chars."""
        # Create summaries with long bodies
        summaries = [
            SummarizedIssue(
                issue_id=i,
                source_number=i,
                title=f"Issue {i}",
                summary="A" * 1000,  # Long summary
                topic_area="test",
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url=f"https://github.com/owner/repo/issues/{i}",
            )
            for i in range(10)
        ]

        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_batch_size=100,  # Large batch size
            max_batch_chars=3000,  # Small character limit
        )

        batches = pipeline._create_batches(summaries)
        assert len(batches) > 1  # Should split due to character limit


class TestValidateClusters:
    """Tests for cluster validation logic."""

    def test_validate_valid_clusters(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test validation passes for valid clusters."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        clusters = [
            IdeaCluster(
                cluster_id="ui-ux-001",
                representative_title="Theme support",
                summary="Theme customization features",
                topic_area="UI/UX",
                member_issue_ids=[100, 101],
                novelty=0.35,
                feasibility=0.75,
                desirability=0.88,
                attention=0.65,
            ),
            IdeaCluster(
                cluster_id="security-001",
                representative_title="Security fix",
                summary="Auth vulnerability",
                topic_area="security",
                member_issue_ids=[102],
                novelty=0.2,
                feasibility=0.9,
                desirability=1.0,
                attention=0.9,
            ),
        ]

        is_valid, errors = pipeline._validate_clusters(clusters, sample_summaries)
        assert is_valid
        assert len(errors) == 0

    def test_validate_unknown_issue_ids(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test validation fails for unknown issue IDs."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        clusters = [
            IdeaCluster(
                cluster_id="test-001",
                representative_title="Test",
                summary="Test cluster",
                topic_area="test",
                member_issue_ids=[100, 999],  # 999 doesn't exist
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
            )
        ]

        is_valid, errors = pipeline._validate_clusters(clusters, sample_summaries)
        assert not is_valid
        assert any("unknown issue IDs" in e for e in errors)

    def test_validate_duplicate_assignments(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test validation fails when issue assigned to multiple clusters."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        clusters = [
            IdeaCluster(
                cluster_id="cluster-001",
                representative_title="Cluster 1",
                summary="First cluster",
                topic_area="test",
                member_issue_ids=[100, 101],
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
            ),
            IdeaCluster(
                cluster_id="cluster-002",
                representative_title="Cluster 2",
                summary="Second cluster",
                topic_area="test",
                member_issue_ids=[101, 102],  # 101 is duplicated
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
            ),
        ]

        is_valid, errors = pipeline._validate_clusters(clusters, sample_summaries)
        assert not is_valid
        assert any("multiple clusters" in e for e in errors)

    def test_validate_unclaimed_issues(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test validation fails when some issues are not in any cluster."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        clusters = [
            IdeaCluster(
                cluster_id="cluster-001",
                representative_title="Partial cluster",
                summary="Only some issues",
                topic_area="test",
                member_issue_ids=[100],  # Missing 101 and 102
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
            )
        ]

        is_valid, errors = pipeline._validate_clusters(clusters, sample_summaries)
        assert not is_valid
        assert any("not assigned to any cluster" in e for e in errors)


class TestAggregateMetrics:
    """Tests for metric aggregation."""

    def test_aggregate_single_summary(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test aggregation with single summary returns original metrics."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        metrics = pipeline._aggregate_metrics([sample_summaries[0]])

        assert metrics["novelty"] == 0.3
        assert metrics["feasibility"] == 0.8
        assert metrics["desirability"] == 0.9
        assert metrics["attention"] == 0.7

    def test_aggregate_multiple_summaries(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test aggregation averages metrics correctly."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        # Use first two summaries (dark mode and theme switching)
        metrics = pipeline._aggregate_metrics(sample_summaries[:2])

        # Should be averages rounded to 2 decimal places
        assert metrics["novelty"] == 0.35  # (0.3 + 0.4) / 2
        assert metrics["feasibility"] == 0.75  # (0.8 + 0.7) / 2
        assert metrics["desirability"] == 0.88  # (0.9 + 0.85) / 2 = 0.875 -> 0.88
        assert metrics["attention"] == 0.65  # (0.7 + 0.6) / 2

    def test_aggregate_empty_list(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
    ) -> None:
        """Test aggregation with empty list returns zeros."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        metrics = pipeline._aggregate_metrics([])

        assert metrics["novelty"] == 0.0
        assert metrics["feasibility"] == 0.0
        assert metrics["desirability"] == 0.0
        assert metrics["attention"] == 0.0


class TestGroupBatch:
    """Tests for single batch grouping."""

    def test_group_batch_success(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test successful batch grouping."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        # Mock LLM response
        mock_llm_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "ui-ux-001",
                            "representative_title": "Theme support",
                            "summary": "Theme customization",
                            "topic_area": "UI/UX",
                            "member_issue_ids": [100, 101],
                            "novelty": 0.35,
                            "feasibility": 0.75,
                            "desirability": 0.88,
                            "attention": 0.65,
                        },
                        {
                            "cluster_id": "security-001",
                            "representative_title": "Security fix",
                            "summary": "Auth vulnerability",
                            "topic_area": "security",
                            "member_issue_ids": [102],
                            "novelty": 0.2,
                            "feasibility": 0.9,
                            "desirability": 1.0,
                            "attention": 0.9,
                        },
                    ]
                }
            ),
            "done": True,
        }

        mock_llm_client.generate.return_value = mock_llm_response
        mock_llm_client.parse_json_response.return_value = json.loads(mock_llm_response["response"])

        clusters = pipeline.group_batch(sample_summaries)

        assert len(clusters) == 2
        assert all(isinstance(c, IdeaCluster) for c in clusters)
        assert clusters[0].cluster_id == "ui-ux-001"
        assert len(clusters[0].member_issue_ids) == 2
        assert clusters[1].cluster_id == "security-001"
        assert len(clusters[1].member_issue_ids) == 1

        # Verify LLM was called
        mock_llm_client.generate.assert_called_once()

    def test_group_batch_empty(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
    ) -> None:
        """Test grouping empty batch returns empty list."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        clusters = pipeline.group_batch([])
        assert clusters == []
        mock_llm_client.generate.assert_not_called()

    def test_group_batch_validation_error_retry(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test retry on validation error."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        # First response has validation error (missing issue)
        bad_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "test-001",
                            "representative_title": "Test",
                            "summary": "Test",
                            "topic_area": "test",
                            "member_issue_ids": [100],  # Missing 101, 102
                            "novelty": 0.5,
                            "feasibility": 0.5,
                            "desirability": 0.5,
                            "attention": 0.5,
                        }
                    ]
                }
            ),
            "done": True,
        }

        # Second response is valid
        good_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "ui-ux-001",
                            "representative_title": "UI",
                            "summary": "UI features",
                            "topic_area": "UI/UX",
                            "member_issue_ids": [100, 101],
                            "novelty": 0.35,
                            "feasibility": 0.75,
                            "desirability": 0.88,
                            "attention": 0.65,
                        },
                        {
                            "cluster_id": "security-001",
                            "representative_title": "Security",
                            "summary": "Security fix",
                            "topic_area": "security",
                            "member_issue_ids": [102],
                            "novelty": 0.2,
                            "feasibility": 0.9,
                            "desirability": 1.0,
                            "attention": 0.9,
                        },
                    ]
                }
            ),
            "done": True,
        }

        mock_llm_client.generate.side_effect = [bad_response, good_response]
        mock_llm_client.parse_json_response.side_effect = [
            json.loads(bad_response["response"]),
            json.loads(good_response["response"]),
        ]

        clusters = pipeline.group_batch(sample_summaries, retry_on_validation_error=True)

        assert len(clusters) == 2
        assert mock_llm_client.generate.call_count == 2  # Retried once

    def test_group_batch_llm_error(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test error handling when LLM fails."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        mock_llm_client.generate.side_effect = OllamaError("LLM request failed")

        with pytest.raises(GroupingError, match="LLM request failed"):
            pipeline.group_batch(sample_summaries)


class TestGroupSummaries:
    """Tests for full multi-batch grouping."""

    def test_group_summaries_single_batch(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
    ) -> None:
        """Test grouping with single batch."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_batch_size=10,
        )

        mock_llm_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "ui-ux-001",
                            "representative_title": "Theme",
                            "summary": "Theme features",
                            "topic_area": "UI/UX",
                            "member_issue_ids": [100, 101],
                            "novelty": 0.35,
                            "feasibility": 0.75,
                            "desirability": 0.88,
                            "attention": 0.65,
                        },
                        {
                            "cluster_id": "security-001",
                            "representative_title": "Security",
                            "summary": "Security fix",
                            "topic_area": "security",
                            "member_issue_ids": [102],
                            "novelty": 0.2,
                            "feasibility": 0.9,
                            "desirability": 1.0,
                            "attention": 0.9,
                        },
                    ]
                }
            ),
            "done": True,
        }

        mock_llm_client.generate.return_value = mock_llm_response
        mock_llm_client.parse_json_response.return_value = json.loads(mock_llm_response["response"])

        clusters = pipeline.group_summaries(sample_summaries)

        assert len(clusters) == 2
        mock_llm_client.generate.assert_called_once()

    def test_group_summaries_skip_noise(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_summaries: list[SummarizedIssue],
        noise_summary: SummarizedIssue,
    ) -> None:
        """Test that noise summaries are skipped when requested."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        all_summaries = sample_summaries + [noise_summary]

        mock_llm_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "ui-ux-001",
                            "representative_title": "Theme",
                            "summary": "Theme features",
                            "topic_area": "UI/UX",
                            "member_issue_ids": [100, 101],
                            "novelty": 0.35,
                            "feasibility": 0.75,
                            "desirability": 0.88,
                            "attention": 0.65,
                        },
                        {
                            "cluster_id": "security-001",
                            "representative_title": "Security",
                            "summary": "Security fix",
                            "topic_area": "security",
                            "member_issue_ids": [102],
                            "novelty": 0.2,
                            "feasibility": 0.9,
                            "desirability": 1.0,
                            "attention": 0.9,
                        },
                    ]
                }
            ),
            "done": True,
        }

        mock_llm_client.generate.return_value = mock_llm_response
        mock_llm_client.parse_json_response.return_value = json.loads(mock_llm_response["response"])

        clusters = pipeline.group_summaries(all_summaries, skip_noise=True)

        # Noise summary should not be in any cluster
        all_member_ids = {iid for c in clusters for iid in c.member_issue_ids}
        assert 999 not in all_member_ids

    def test_group_summaries_empty(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
    ) -> None:
        """Test grouping empty list returns empty."""
        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        clusters = pipeline.group_summaries([])
        assert clusters == []
        mock_llm_client.generate.assert_not_called()

    def test_group_summaries_multiple_batches(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
    ) -> None:
        """Test grouping across multiple batches."""
        # Create enough summaries to force multiple batches
        summaries = [
            SummarizedIssue(
                issue_id=i,
                source_number=i,
                title=f"Issue {i}",
                summary=f"Summary {i}",
                topic_area="test",
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url=f"https://github.com/owner/repo/issues/{i}",
            )
            for i in range(5)
        ]

        pipeline = GroupingPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_batch_size=2,  # Force 3 batches (2, 2, 1)
        )

        # Create proper mock responses for 3 batches
        batch1_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "test-001",
                            "representative_title": "Batch 1 cluster",
                            "summary": "Issues 0-1",
                            "topic_area": "test",
                            "member_issue_ids": [0, 1],
                            "novelty": 0.5,
                            "feasibility": 0.5,
                            "desirability": 0.5,
                            "attention": 0.5,
                        }
                    ]
                }
            ),
            "done": True,
        }

        batch2_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "test-001",
                            "representative_title": "Batch 2 cluster",
                            "summary": "Issues 2-3",
                            "topic_area": "test",
                            "member_issue_ids": [2, 3],
                            "novelty": 0.5,
                            "feasibility": 0.5,
                            "desirability": 0.5,
                            "attention": 0.5,
                        }
                    ]
                }
            ),
            "done": True,
        }

        batch3_response = {
            "response": json.dumps(
                {
                    "clusters": [
                        {
                            "cluster_id": "test-001",
                            "representative_title": "Batch 3 cluster",
                            "summary": "Issue 4",
                            "topic_area": "test",
                            "member_issue_ids": [4],
                            "novelty": 0.5,
                            "feasibility": 0.5,
                            "desirability": 0.5,
                            "attention": 0.5,
                        }
                    ]
                }
            ),
            "done": True,
        }

        mock_llm_client.generate.side_effect = [batch1_response, batch2_response, batch3_response]
        mock_llm_client.parse_json_response.side_effect = [
            json.loads(batch1_response["response"]),
            json.loads(batch2_response["response"]),
            json.loads(batch3_response["response"]),
        ]

        clusters = pipeline.group_summaries(summaries)

        assert len(clusters) == 3  # One cluster per batch
        assert mock_llm_client.generate.call_count == 3  # Called for each batch
