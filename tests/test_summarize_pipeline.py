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
Tests for the summarization pipeline.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from idea_generator.llm.client import OllamaClient, OllamaError
from idea_generator.models import NormalizedComment, NormalizedIssue, SummarizedIssue
from idea_generator.pipelines.summarize import SummarizationError, SummarizationPipeline


@pytest.fixture
def sample_issue() -> NormalizedIssue:
    """Create a sample normalized issue for testing."""
    return NormalizedIssue(
        id=123456,
        number=42,
        title="Add dark mode support",
        body="Users have requested dark mode for better night-time viewing.",
        labels=["enhancement", "UI"],
        state="open",
        reactions={"+1": 15, "heart": 3},
        comments=[
            NormalizedComment(
                id=1,
                author="user1",
                body="This would be great!",
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                reactions={"+1": 5},
            ),
            NormalizedComment(
                id=2,
                author="user2",
                body="We could use CSS variables for theming.",
                created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                reactions={},
            ),
        ],
        url="https://github.com/owner/repo/issues/42",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        is_noise=False,
        truncated=False,
        original_length=100,
    )


@pytest.fixture
def noise_issue() -> NormalizedIssue:
    """Create a noise-flagged issue for testing."""
    return NormalizedIssue(
        id=999,
        number=1,
        title="test",
        body="test",
        labels=["spam"],
        state="open",
        reactions={},
        comments=[],
        url="https://github.com/owner/repo/issues/1",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        is_noise=True,
        noise_reason="Single-word title",
        truncated=False,
        original_length=8,
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
        prompt_path = Path(tmpdir) / "summarizer.txt"
        prompt_path.write_text(
            "You are a test summarizer. Respond with valid JSON containing: "
            "title, summary, topic_area, novelty, feasibility, desirability, attention, noise_flag."
        )
        yield prompt_path


class TestSummarizationPipelineInit:
    """Tests for pipeline initialization."""

    def test_pipeline_initialization(
        self, mock_llm_client: Mock, temp_prompt_file: Path
    ) -> None:
        """Test that pipeline initializes correctly."""
        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"

            pipeline = SummarizationPipeline(
                llm_client=mock_llm_client,
                model="llama3.2:latest",
                prompt_template_path=temp_prompt_file,
                max_tokens=4000,
                cache_dir=cache_dir,
            )

            assert pipeline.llm_client == mock_llm_client
            assert pipeline.model == "llama3.2:latest"
            assert pipeline.max_tokens == 4000
            assert pipeline.cache_dir == cache_dir
            assert cache_dir.exists()
            assert len(pipeline.system_prompt) > 0

    def test_pipeline_missing_prompt_template(self, mock_llm_client: Mock) -> None:
        """Test error when prompt template doesn't exist."""
        with pytest.raises(SummarizationError, match="Prompt template not found"):
            SummarizationPipeline(
                llm_client=mock_llm_client,
                model="llama3.2:latest",
                prompt_template_path=Path("/nonexistent/prompt.txt"),
            )

    def test_pipeline_without_cache_dir(
        self, mock_llm_client: Mock, temp_prompt_file: Path
    ) -> None:
        """Test pipeline works without cache directory."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            cache_dir=None,
        )

        assert pipeline.cache_dir is None


class TestTruncateText:
    """Tests for text truncation."""

    def test_truncate_short_text(
        self, mock_llm_client: Mock, temp_prompt_file: Path
    ) -> None:
        """Test that short text is not truncated."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        text = "Short text"
        result, was_truncated = pipeline._truncate_text(text, 100)

        assert result == text
        assert was_truncated is False

    def test_truncate_long_text(
        self, mock_llm_client: Mock, temp_prompt_file: Path
    ) -> None:
        """Test that long text is truncated at word boundary."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        text = "This is a long text that needs to be truncated at some point."
        result, was_truncated = pipeline._truncate_text(text, 30)

        assert len(result) <= 33  # 30 + "..."
        assert was_truncated is True
        assert result.endswith("...")
        assert not result[:-3].endswith(" ")  # Should truncate at word boundary


class TestFormatIssuePrompt:
    """Tests for issue prompt formatting."""

    def test_format_simple_issue(
        self, mock_llm_client: Mock, temp_prompt_file: Path, sample_issue: NormalizedIssue
    ) -> None:
        """Test formatting a simple issue into a prompt."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        prompt = pipeline._format_issue_prompt(sample_issue)

        assert "Title: Add dark mode support" in prompt
        assert "Body:" in prompt
        assert "dark mode" in prompt
        assert "Comments:" in prompt
        assert "[user1]:" in prompt
        assert "Reactions: 18 reactions" in prompt
        assert "Labels: enhancement, UI" in prompt

    def test_format_issue_without_comments(
        self, mock_llm_client: Mock, temp_prompt_file: Path, sample_issue: NormalizedIssue
    ) -> None:
        """Test formatting issue without comments."""
        issue = sample_issue.model_copy(update={"comments": []})

        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        prompt = pipeline._format_issue_prompt(issue)

        assert "Title:" in prompt
        assert "Body:" in prompt
        assert "Comments:" not in prompt

    def test_format_issue_truncates_long_body(
        self, mock_llm_client: Mock, temp_prompt_file: Path, sample_issue: NormalizedIssue
    ) -> None:
        """Test that long body text is truncated."""
        long_body = "A" * 10000
        issue = sample_issue.model_copy(update={"body": long_body})

        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
            max_tokens=1000,  # Small budget
        )

        prompt = pipeline._format_issue_prompt(issue)

        # Body should be truncated
        assert "(Body truncated due to length)" in prompt or len(prompt) < len(long_body)

    def test_format_issue_with_deleted_user(
        self, mock_llm_client: Mock, temp_prompt_file: Path, sample_issue: NormalizedIssue
    ) -> None:
        """Test formatting comment from deleted user."""
        comment = NormalizedComment(
            id=99,
            author=None,
            body="Comment from deleted user",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            reactions={},
        )
        issue = sample_issue.model_copy(update={"comments": [comment]})

        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        prompt = pipeline._format_issue_prompt(issue)

        assert "[deleted-user]:" in prompt


class TestParseResponse:
    """Tests for parsing LLM responses."""

    def test_parse_valid_response(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test parsing a valid LLM response."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        llm_response = {
            "response": json.dumps(
                {
                    "title": "Add dark mode",
                    "summary": "Users want dark mode for night viewing.",
                    "topic_area": "UI/UX",
                    "novelty": 0.3,
                    "feasibility": 0.8,
                    "desirability": 0.9,
                    "attention": 0.7,
                    "noise_flag": False,
                }
            )
        }

        mock_llm_client.parse_json_response.return_value = json.loads(
            llm_response["response"]
        )

        result = pipeline._parse_llm_response(sample_issue, llm_response)

        assert isinstance(result, SummarizedIssue)
        assert result.issue_id == sample_issue.id
        assert result.source_number == sample_issue.number
        assert result.title == "Add dark mode"
        assert result.novelty == 0.3
        assert result.feasibility == 0.8
        assert result.raw_issue_url == sample_issue.url

    def test_parse_response_missing_field(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test error when response is missing required fields."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        llm_response = {
            "response": json.dumps(
                {
                    "title": "Test",
                    "summary": "Test summary",
                    # Missing: topic_area, metrics, noise_flag
                }
            )
        }

        mock_llm_client.parse_json_response.return_value = json.loads(
            llm_response["response"]
        )

        with pytest.raises(SummarizationError, match="missing required fields"):
            pipeline._parse_llm_response(sample_issue, llm_response)

    def test_parse_response_invalid_metric_range(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test error when metrics are out of valid range."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        llm_response = {
            "response": json.dumps(
                {
                    "title": "Test",
                    "summary": "Test summary",
                    "topic_area": "test",
                    "novelty": 1.5,  # Invalid: > 1.0
                    "feasibility": 0.5,
                    "desirability": 0.5,
                    "attention": 0.5,
                    "noise_flag": False,
                }
            )
        }

        mock_llm_client.parse_json_response.return_value = json.loads(
            llm_response["response"]
        )

        with pytest.raises(SummarizationError, match="Invalid summary data"):
            pipeline._parse_llm_response(sample_issue, llm_response)


class TestSummarizeIssue:
    """Tests for single issue summarization."""

    def test_summarize_issue_success(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test successful issue summarization."""
        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"

            pipeline = SummarizationPipeline(
                llm_client=mock_llm_client,
                model="llama3.2:latest",
                prompt_template_path=temp_prompt_file,
                cache_dir=cache_dir,
            )

            # Mock LLM response
            mock_llm_response = {
                "response": json.dumps(
                    {
                        "title": "Dark mode support",
                        "summary": "Add dark mode for better UX.",
                        "topic_area": "UI/UX",
                        "novelty": 0.4,
                        "feasibility": 0.8,
                        "desirability": 0.9,
                        "attention": 0.7,
                        "noise_flag": False,
                    }
                ),
                "done": True,
            }
            mock_llm_client.generate.return_value = mock_llm_response
            mock_llm_client.parse_json_response.return_value = json.loads(
                mock_llm_response["response"]
            )

            result = pipeline.summarize_issue(sample_issue)

            assert isinstance(result, SummarizedIssue)
            assert result.issue_id == sample_issue.id
            assert result.title == "Dark mode support"
            assert result.novelty == 0.4

            # Verify LLM was called
            mock_llm_client.generate.assert_called_once()
            call_kwargs = mock_llm_client.generate.call_args[1]
            assert call_kwargs["model"] == "llama3.2:latest"
            assert "Add dark mode" in call_kwargs["prompt"]

            # Verify cache was created
            cache_file = cache_dir / f"summary_{sample_issue.id}.json"
            assert cache_file.exists()

    def test_summarize_issue_uses_cache(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test that cached summaries are reused."""
        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()

            # Pre-populate cache
            cached_summary = SummarizedIssue(
                issue_id=sample_issue.id,
                source_number=sample_issue.number,
                title="Cached title",
                summary="Cached summary",
                topic_area="test",
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url=sample_issue.url,
            )

            cache_file = cache_dir / f"summary_{sample_issue.id}.json"
            with open(cache_file, "w") as f:
                json.dump(cached_summary.model_dump(mode="json"), f)

            pipeline = SummarizationPipeline(
                llm_client=mock_llm_client,
                model="llama3.2:latest",
                prompt_template_path=temp_prompt_file,
                cache_dir=cache_dir,
            )

            result = pipeline.summarize_issue(sample_issue)

            # Should use cached version
            assert result.title == "Cached title"

            # LLM should not be called
            mock_llm_client.generate.assert_not_called()

    def test_summarize_issue_skip_cache(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test that skip_cache bypasses cache."""
        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()

            # Pre-populate cache
            cached_summary = SummarizedIssue(
                issue_id=sample_issue.id,
                source_number=sample_issue.number,
                title="Cached title",
                summary="Cached summary",
                topic_area="test",
                novelty=0.5,
                feasibility=0.5,
                desirability=0.5,
                attention=0.5,
                noise_flag=False,
                raw_issue_url=sample_issue.url,
            )

            cache_file = cache_dir / f"summary_{sample_issue.id}.json"
            with open(cache_file, "w") as f:
                json.dump(cached_summary.model_dump(mode="json"), f)

            pipeline = SummarizationPipeline(
                llm_client=mock_llm_client,
                model="llama3.2:latest",
                prompt_template_path=temp_prompt_file,
                cache_dir=cache_dir,
            )

            # Mock new LLM response
            mock_llm_response = {
                "response": json.dumps(
                    {
                        "title": "Fresh title",
                        "summary": "Fresh summary",
                        "topic_area": "test",
                        "novelty": 0.6,
                        "feasibility": 0.7,
                        "desirability": 0.8,
                        "attention": 0.9,
                        "noise_flag": False,
                    }
                ),
                "done": True,
            }
            mock_llm_client.generate.return_value = mock_llm_response
            mock_llm_client.parse_json_response.return_value = json.loads(
                mock_llm_response["response"]
            )

            result = pipeline.summarize_issue(sample_issue, skip_cache=True)

            # Should use fresh LLM response
            assert result.title == "Fresh title"

            # LLM should be called
            mock_llm_client.generate.assert_called_once()

    def test_summarize_issue_llm_error(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test error handling when LLM fails."""
        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        mock_llm_client.generate.side_effect = OllamaError("LLM request failed")

        with pytest.raises(SummarizationError, match="Failed to generate summary"):
            pipeline.summarize_issue(sample_issue)


class TestSummarizeIssues:
    """Tests for batch issue summarization."""

    def test_summarize_multiple_issues(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test summarizing multiple issues."""
        issue2 = sample_issue.model_copy(
            update={"id": 456, "number": 43, "title": "Another issue"}
        )
        issues = [sample_issue, issue2]

        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        # Mock LLM responses
        def mock_generate(**kwargs: dict) -> dict:
            return {
                "response": json.dumps(
                    {
                        "title": "Test",
                        "summary": "Test summary",
                        "topic_area": "test",
                        "novelty": 0.5,
                        "feasibility": 0.5,
                        "desirability": 0.5,
                        "attention": 0.5,
                        "noise_flag": False,
                    }
                ),
                "done": True,
            }

        mock_llm_client.generate.side_effect = mock_generate
        mock_llm_client.parse_json_response.side_effect = lambda r: json.loads(
            r["response"]
        )

        results = pipeline.summarize_issues(issues)

        assert len(results) == 2
        assert all(isinstance(r, SummarizedIssue) for r in results)
        assert mock_llm_client.generate.call_count == 2

    def test_summarize_issues_skip_noise(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
        noise_issue: NormalizedIssue,
    ) -> None:
        """Test that noise issues are skipped when requested."""
        issues = [sample_issue, noise_issue]

        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        mock_llm_response = {
            "response": json.dumps(
                {
                    "title": "Test",
                    "summary": "Test",
                    "topic_area": "test",
                    "novelty": 0.5,
                    "feasibility": 0.5,
                    "desirability": 0.5,
                    "attention": 0.5,
                    "noise_flag": False,
                }
            ),
            "done": True,
        }
        mock_llm_client.generate.return_value = mock_llm_response
        mock_llm_client.parse_json_response.return_value = json.loads(
            mock_llm_response["response"]
        )

        results = pipeline.summarize_issues(issues, skip_noise=True)

        # Only non-noise issue should be processed
        assert len(results) == 1
        assert results[0].issue_id == sample_issue.id
        assert mock_llm_client.generate.call_count == 1

    def test_summarize_issues_handles_failures(
        self,
        mock_llm_client: Mock,
        temp_prompt_file: Path,
        sample_issue: NormalizedIssue,
    ) -> None:
        """Test that failures don't crash the entire batch."""
        issue2 = sample_issue.model_copy(update={"id": 456, "number": 43})
        issues = [sample_issue, issue2]

        pipeline = SummarizationPipeline(
            llm_client=mock_llm_client,
            model="llama3.2:latest",
            prompt_template_path=temp_prompt_file,
        )

        # First call succeeds, second fails
        call_count = 0

        def mock_generate(**kwargs: dict) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "response": json.dumps(
                        {
                            "title": "Success",
                            "summary": "Success",
                            "topic_area": "test",
                            "novelty": 0.5,
                            "feasibility": 0.5,
                            "desirability": 0.5,
                            "attention": 0.5,
                            "noise_flag": False,
                        }
                    ),
                    "done": True,
                }
            raise OllamaError("Failed")

        mock_llm_client.generate.side_effect = mock_generate
        mock_llm_client.parse_json_response.side_effect = lambda r: json.loads(
            r["response"]
        )

        results = pipeline.summarize_issues(issues)

        # Only first issue should succeed
        assert len(results) == 1
        assert results[0].issue_id == sample_issue.id
