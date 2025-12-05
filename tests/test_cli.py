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

import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from idea_generator.cli import app
from idea_generator.setup import SetupError

runner = CliRunner()


class TestCLIBasics:
    """Test suite for basic CLI functionality."""

    def test_cli_help(self) -> None:
        """Test CLI help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "idea-generator" in result.stdout
        assert "Generate ideas from GitHub repositories" in result.stdout

    def test_cli_commands_available(self) -> None:
        """Test CLI shows available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Help should show available commands
        assert "setup" in result.stdout
        assert "ingest" in result.stdout
        assert "summarize" in result.stdout
        assert "run" in result.stdout


class TestSetupCommand:
    """Test suite for setup command."""

    def test_setup_help(self) -> None:
        """Test setup command help."""
        result = runner.invoke(app, ["setup", "--help"])
        assert result.exit_code == 0
        assert "Set up the idea-generator environment" in result.stdout
        # Check that key options are present (without relying on exact formatting with ANSI codes)
        assert "skip" in result.stdout and "pull" in result.stdout
        assert "offline" in result.stdout

    def test_setup_success(self) -> None:
        """Test successful setup command."""
        with patch("idea_generator.cli.run_setup") as mock_setup:
            result = runner.invoke(app, ["setup", "--skip-pull"])
            assert result.exit_code == 0
            mock_setup.assert_called_once()

    def test_setup_with_custom_models(self) -> None:
        """Test setup with custom model names."""
        with patch("idea_generator.cli.run_setup") as mock_setup:
            result = runner.invoke(
                app,
                [
                    "setup",
                    "--model-innovator",
                    "llama3.2:70b",
                    "--model-critic",
                    "llama3.2:8b",
                    "--skip-pull",
                ],
            )
            assert result.exit_code == 0
            mock_setup.assert_called_once()

    def test_setup_offline_mode(self) -> None:
        """Test setup in offline mode."""
        with patch("idea_generator.cli.run_setup") as mock_setup:
            result = runner.invoke(app, ["setup", "--offline"])
            assert result.exit_code == 0
            mock_setup.assert_called_once()
            # Verify offline flag was passed
            call_kwargs = mock_setup.call_args[1]
            assert call_kwargs["offline"] is True

    def test_setup_error_handling(self) -> None:
        """Test setup command error handling."""
        with patch("idea_generator.cli.run_setup", side_effect=SetupError("Test error")):
            result = runner.invoke(app, ["setup"])
            assert result.exit_code == 1
            assert "Setup failed" in result.stdout

    def test_setup_unexpected_error(self) -> None:
        """Test setup command handles unexpected errors."""
        with patch("idea_generator.cli.run_setup", side_effect=RuntimeError("Unexpected")):
            result = runner.invoke(app, ["setup"])
            assert result.exit_code == 1
            assert "Unexpected error" in result.stdout


class TestIngestCommand:
    """Test suite for ingest command."""

    def test_ingest_help(self) -> None:
        """Test ingest command help."""
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "Ingest open issues from a GitHub repository" in result.stdout

    def test_ingest_requires_github_repo(self) -> None:
        """Test ingest command requires GitHub repo."""
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 1
        assert "GitHub repository not configured" in result.stdout

    def test_ingest_with_github_repo(self) -> None:
        """Test ingest with GitHub repo argument."""
        from unittest.mock import MagicMock, patch

        with patch("idea_generator.cli.GitHubClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.check_repository_access = MagicMock(return_value=True)
            mock_client.fetch_issues = MagicMock(return_value=[])
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["ingest", "--github-repo", "owner/repo"])
            assert result.exit_code == 0
            assert "owner/repo" in result.stdout
            assert "No open issues found" in result.stdout


class TestSummarizeCommand:
    """Test suite for summarize command."""

    def test_summarize_help(self) -> None:
        """Test summarize command help."""
        result = runner.invoke(app, ["summarize", "--help"])
        assert result.exit_code == 0
        assert "Summarize normalized issues" in result.stdout

    def test_summarize_placeholder(self) -> None:
        """Test summarize command requires repo configuration."""
        result = runner.invoke(app, ["summarize"])
        assert result.exit_code == 1
        assert "GitHub repository not configured" in result.stdout

    def test_summarize_with_directories(self) -> None:
        """Test summarize with custom directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            output_dir = Path(tmpdir) / "output"

            result = runner.invoke(
                app,
                [
                    "summarize",
                    "--github-repo",
                    "owner/repo",
                    "--data-dir",
                    str(data_dir),
                    "--output-dir",
                    str(output_dir),
                ],
            )
            # Will fail because issues file doesn't exist, but checks CLI parsing
            assert result.exit_code == 1
            assert "Normalized issues file not found" in result.stdout


class TestRunCommand:
    """Test suite for run command."""

    def test_run_help(self) -> None:
        """Test run command help."""
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run the complete idea generation pipeline" in result.stdout

    def test_run_placeholder(self) -> None:
        """Test run command requires github_repo configuration."""
        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1
        assert "GitHub repository not configured" in result.stdout

    def test_run_with_all_options(self) -> None:
        """Test run with multiple options validates repo format."""
        result = runner.invoke(
            app,
            [
                "run",
                "--github-repo",
                "owner/repo",
                "--model-innovator",
                "llama3.2:latest",
                "--output-dir",
                "/custom/output",
            ],
        )
        # Will fail because it tries to actually run the pipeline
        # But it should at least parse arguments correctly
        assert result.exit_code == 1  # Will fail at runtime
        assert "owner/repo" in result.stdout or "Pipeline error" in result.stdout
