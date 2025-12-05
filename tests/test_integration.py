"""
Copyright 2025 John Brosnihan

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from idea_generator.cli import app

runner = CliRunner()


class TestIngestIntegration:
    """Integration tests for the ingest command."""

    def test_ingest_end_to_end_with_mocked_api(self) -> None:
        """Test complete ingestion workflow with mocked GitHub API."""
        # Sample GitHub API response data
        mock_issues = [
            {
                "id": 1,
                "number": 1,
                "title": "First Issue",
                "body": "**This** is the first issue with `code`",
                "state": "open",
                "html_url": "https://github.com/test/repo/issues/1",
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-02T12:00:00Z",
                "labels": [{"name": "bug"}],
                "reactions": {"+1": 5, "-1": 0},
                "user": {"login": "testuser"},
            },
            {
                "id": 2,
                "number": 2,
                "title": "spam",
                "body": "spam content",
                "state": "open",
                "html_url": "https://github.com/test/repo/issues/2",
                "created_at": "2025-01-03T12:00:00Z",
                "updated_at": "2025-01-04T12:00:00Z",
                "labels": [{"name": "spam"}],
                "reactions": {},
                "user": {"login": "spammer"},
            },
        ]

        mock_comments = {
            1: [
                {
                    "id": 101,
                    "user": {"login": "commenter1"},
                    "body": "Great issue! I agree.",
                    "created_at": "2025-01-01T13:00:00Z",
                    "reactions": {"+1": 2},
                }
            ],
            2: [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"

            with patch("idea_generator.cli.GitHubClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.check_repository_access = MagicMock(return_value=True)
                mock_client.fetch_issues = MagicMock(return_value=mock_issues)

                def mock_fetch_comments(owner: str, repo: str, issue_number: int):
                    return mock_comments.get(issue_number, [])

                mock_client.fetch_issue_comments = MagicMock(side_effect=mock_fetch_comments)
                mock_client_class.return_value = mock_client

                result = runner.invoke(
                    app,
                    [
                        "ingest",
                        "--github-repo",
                        "test/repo",
                        "--data-dir",
                        str(data_dir),
                    ],
                )

                # Check command succeeded
                assert result.exit_code == 0
                assert "✅ Ingestion completed successfully!" in result.stdout

                # Check output file was created
                output_file = data_dir / "test_repo_issues.json"
                assert output_file.exists()

                # Load and validate output
                with open(output_file) as f:
                    issues = json.load(f)

                assert len(issues) == 2

                # Check first issue (normal issue)
                issue1 = issues[0]
                assert issue1["number"] == 1
                assert issue1["title"] == "First Issue"
                assert "**" not in issue1["body"]  # Markdown cleaned
                assert "`" not in issue1["body"]
                assert "This" in issue1["body"]
                assert issue1["labels"] == ["bug"]
                assert issue1["is_noise"] is False
                assert len(issue1["comments"]) == 1
                assert issue1["comments"][0]["author"] == "commenter1"

                # Check second issue (noise issue)
                issue2 = issues[1]
                assert issue2["number"] == 2
                assert issue2["is_noise"] is True
                assert "spam" in issue2["noise_reason"].lower()

    def test_ingest_with_truncation(self) -> None:
        """Test ingestion with text truncation."""
        mock_issues = [
            {
                "id": 1,
                "number": 1,
                "title": "Long Issue",
                "body": "A" * 10000,  # Very long body
                "state": "open",
                "html_url": "https://github.com/test/repo/issues/1",
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-02T12:00:00Z",
                "labels": [],
                "reactions": {},
                "user": {"login": "testuser"},
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"

            with patch("idea_generator.cli.GitHubClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.check_repository_access = MagicMock(return_value=True)
                mock_client.fetch_issues = MagicMock(return_value=mock_issues)
                mock_client.fetch_issue_comments = MagicMock(return_value=[])
                mock_client_class.return_value = mock_client

                result = runner.invoke(
                    app,
                    ["ingest", "--github-repo", "test/repo", "--data-dir", str(data_dir)],
                )

                assert result.exit_code == 0
                assert "Truncated: 1" in result.stdout

                # Verify truncation metadata
                output_file = data_dir / "test_repo_issues.json"
                with open(output_file) as f:
                    issues = json.load(f)

                assert issues[0]["truncated"] is True
                assert issues[0]["original_length"] == 10000
                assert len(issues[0]["body"]) < 10000

    def test_ingest_handles_api_errors_gracefully(self) -> None:
        """Test ingestion handles API errors gracefully."""
        mock_issues = [
            {
                "id": 1,
                "number": 1,
                "title": "Issue with bad comments",
                "body": "Some body",
                "state": "open",
                "html_url": "https://github.com/test/repo/issues/1",
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-02T12:00:00Z",
                "labels": [],
                "reactions": {},
                "user": {"login": "testuser"},
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"

            with patch("idea_generator.cli.GitHubClient") as mock_client_class:
                from idea_generator.github_client import GitHubAPIError

                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.check_repository_access = MagicMock(return_value=True)
                mock_client.fetch_issues = MagicMock(return_value=mock_issues)
                # Simulate error fetching comments
                mock_client.fetch_issue_comments = MagicMock(
                    side_effect=GitHubAPIError("Failed to fetch comments")
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(
                    app,
                    ["ingest", "--github-repo", "test/repo", "--data-dir", str(data_dir)],
                )

                # Should complete despite error
                assert result.exit_code == 0
                assert "Warning: Failed to fetch comments" in result.stdout

                # Issue should still be saved (without comments)
                output_file = data_dir / "test_repo_issues.json"
                with open(output_file) as f:
                    issues = json.load(f)

                assert len(issues) == 1
                assert len(issues[0]["comments"]) == 0
