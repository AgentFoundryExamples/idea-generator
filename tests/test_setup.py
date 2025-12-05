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
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from idea_generator.config import Config
from idea_generator.setup import (
    CRITIC_PROMPT,
    INNOVATOR_PROMPT,
    SetupError,
    check_ollama_binary,
    check_ollama_server,
    list_installed_models,
    pull_model,
    run_setup,
    save_persona_metadata,
)


class TestCheckOllamaBinary:
    """Test suite for check_ollama_binary function."""

    def test_ollama_binary_found(self) -> None:
        """Test when ollama binary is found."""
        with patch("shutil.which", return_value="/usr/local/bin/ollama"):
            assert check_ollama_binary() is True

    def test_ollama_binary_not_found(self) -> None:
        """Test when ollama binary is not found."""
        with patch("shutil.which", return_value=None):
            assert check_ollama_binary() is False


class TestCheckOllamaServer:
    """Test suite for check_ollama_server function."""

    def test_server_accessible(self) -> None:
        """Test when Ollama server is accessible."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            assert check_ollama_server("http://localhost:11434") is True
            mock_get.assert_called_once_with(
                "http://localhost:11434/api/tags", timeout=5.0
            )

    def test_server_not_accessible(self) -> None:
        """Test when Ollama server is not accessible."""
        with patch("httpx.get", side_effect=httpx.RequestError("Connection failed")):
            assert check_ollama_server("http://localhost:11434") is False

    def test_server_timeout(self) -> None:
        """Test when server request times out."""
        with patch("httpx.get", side_effect=httpx.TimeoutException("Timeout")):
            assert check_ollama_server("http://localhost:11434") is False

    def test_server_error_status(self) -> None:
        """Test when server returns error status."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            assert check_ollama_server("http://localhost:11434") is False


class TestPullModel:
    """Test suite for pull_model function."""

    def test_pull_model_success(self) -> None:
        """Test successful model pull."""
        with patch("idea_generator.setup.check_ollama_binary", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = pull_model("llama3.2:latest", show_progress=False)
                assert result is True
                mock_run.assert_called_once()

    def test_pull_model_failure(self) -> None:
        """Test failed model pull."""
        with patch("idea_generator.setup.check_ollama_binary", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="Error message")

                result = pull_model("llama3.2:latest", show_progress=False)
                assert result is False

    def test_pull_model_no_binary(self) -> None:
        """Test model pull when ollama binary not found."""
        with patch("idea_generator.setup.check_ollama_binary", return_value=False):
            with pytest.raises(SetupError) as exc_info:
                pull_model("llama3.2:latest", show_progress=False)

            assert "ollama binary not found" in str(exc_info.value)

    def test_pull_model_exception(self) -> None:
        """Test model pull when subprocess raises exception."""
        with patch("idea_generator.setup.check_ollama_binary", return_value=True):
            with patch("subprocess.run", side_effect=Exception("Unexpected error")):
                result = pull_model("llama3.2:latest", show_progress=False)
                assert result is False


class TestListInstalledModels:
    """Test suite for list_installed_models function."""

    def test_list_models_success(self) -> None:
        """Test successfully listing installed models."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [
                    {"name": "llama3.2:latest"},
                    {"name": "mistral:latest"},
                ]
            }
            mock_get.return_value = mock_response

            models = list_installed_models("http://localhost:11434")
            assert models == ["llama3.2:latest", "mistral:latest"]

    def test_list_models_empty(self) -> None:
        """Test listing models when none are installed."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": []}
            mock_get.return_value = mock_response

            models = list_installed_models("http://localhost:11434")
            assert models == []

    def test_list_models_error(self) -> None:
        """Test listing models when request fails."""
        with patch("httpx.get", side_effect=httpx.RequestError("Connection failed")):
            models = list_installed_models("http://localhost:11434")
            assert models == []


class TestSavePersonaMetadata:
    """Test suite for save_persona_metadata function."""

    def test_save_persona_metadata(self) -> None:
        """Test saving persona metadata and prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persona_dir = Path(tmpdir)
            model_name = "llama3.2:latest"
            role = "innovator"
            prompt = "Test prompt"

            save_persona_metadata(persona_dir, model_name, role, prompt)

            # Check metadata file
            metadata_file = persona_dir / f"{role}.json"
            assert metadata_file.exists()
            with open(metadata_file) as f:
                metadata = json.load(f)
            assert metadata["role"] == role
            assert metadata["model"] == model_name
            assert "description" in metadata

            # Check prompt file
            prompt_file = persona_dir / f"{role}_prompt.txt"
            assert prompt_file.exists()
            assert prompt_file.read_text() == prompt

    def test_save_persona_metadata_creates_directory(self) -> None:
        """Test that persona directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persona_dir = Path(tmpdir) / "nested" / "personas"
            assert not persona_dir.exists()

            save_persona_metadata(persona_dir, "llama3.2:latest", "critic", "Test")

            assert persona_dir.exists()
            assert (persona_dir / "critic.json").exists()


class TestRunSetup:
    """Test suite for run_setup function."""

    def test_run_setup_success(self) -> None:
        """Test successful setup workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                output_dir=Path(tmpdir) / "output",
                data_dir=Path(tmpdir) / "data",
                persona_dir=Path(tmpdir) / "personas",
            )

            with patch("idea_generator.setup.check_ollama_binary", return_value=True):
                with patch("idea_generator.setup.check_ollama_server", return_value=True):
                    with patch("idea_generator.setup.list_installed_models", return_value=[]):
                        with patch("idea_generator.setup.pull_model", return_value=True):
                            run_setup(config, skip_pull=False, offline=False)

            # Verify directories created
            assert config.output_dir.exists()
            assert config.data_dir.exists()
            assert config.persona_dir.exists()

            # Verify persona files created
            assert (config.persona_dir / "innovator.json").exists()
            assert (config.persona_dir / "innovator_prompt.txt").exists()
            assert (config.persona_dir / "critic.json").exists()
            assert (config.persona_dir / "critic_prompt.txt").exists()

            # Verify prompt content
            innovator_prompt = (config.persona_dir / "innovator_prompt.txt").read_text()
            assert innovator_prompt == INNOVATOR_PROMPT
            critic_prompt = (config.persona_dir / "critic_prompt.txt").read_text()
            assert critic_prompt == CRITIC_PROMPT

    def test_run_setup_no_ollama_binary(self) -> None:
        """Test setup fails when ollama binary not found."""
        config = Config()
        with patch("idea_generator.setup.check_ollama_binary", return_value=False):
            with pytest.raises(SetupError) as exc_info:
                run_setup(config, skip_pull=False, offline=False)

            assert "Ollama binary not found" in str(exc_info.value)

    def test_run_setup_server_not_running(self) -> None:
        """Test setup fails when server not running and pulling required."""
        config = Config()
        with patch("idea_generator.setup.check_ollama_binary", return_value=True):
            with patch("idea_generator.setup.check_ollama_server", return_value=False):
                with pytest.raises(SetupError) as exc_info:
                    run_setup(config, skip_pull=False, offline=False)

                assert "Cannot proceed with model pulling" in str(exc_info.value)

    def test_run_setup_skip_pull(self) -> None:
        """Test setup with skip_pull flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                output_dir=Path(tmpdir) / "output",
                data_dir=Path(tmpdir) / "data",
                persona_dir=Path(tmpdir) / "personas",
            )

            with patch("idea_generator.setup.check_ollama_binary", return_value=True):
                with patch("idea_generator.setup.check_ollama_server", return_value=True):
                    with patch("idea_generator.setup.pull_model") as mock_pull:
                        run_setup(config, skip_pull=True, offline=False)

                        # pull_model should not be called
                        mock_pull.assert_not_called()

            # Persona files should still be created
            assert (config.persona_dir / "innovator.json").exists()
            assert (config.persona_dir / "critic.json").exists()

    def test_run_setup_offline_mode(self) -> None:
        """Test setup in offline mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                output_dir=Path(tmpdir) / "output",
                data_dir=Path(tmpdir) / "data",
                persona_dir=Path(tmpdir) / "personas",
            )

            with patch("idea_generator.setup.check_ollama_binary", return_value=True):
                with patch("idea_generator.setup.check_ollama_server") as mock_server:
                    with patch("idea_generator.setup.pull_model") as mock_pull:
                        run_setup(config, skip_pull=False, offline=True)

                        # Server check should be skipped
                        mock_server.assert_not_called()
                        # Model pull should be skipped
                        mock_pull.assert_not_called()

            # Persona files should still be created
            assert (config.persona_dir / "innovator.json").exists()

    def test_run_setup_same_model_both_personas(self) -> None:
        """Test setup when same model is used for both personas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                output_dir=Path(tmpdir) / "output",
                data_dir=Path(tmpdir) / "data",
                persona_dir=Path(tmpdir) / "personas",
                model_innovator="llama3.2:latest",
                model_critic="llama3.2:latest",
            )

            with patch("idea_generator.setup.check_ollama_binary", return_value=True):
                with patch("idea_generator.setup.check_ollama_server", return_value=True):
                    with patch("idea_generator.setup.list_installed_models", return_value=[]):
                        with patch("idea_generator.setup.pull_model", return_value=True) as mock_pull:
                            run_setup(config, skip_pull=False, offline=False)

                            # Model should only be pulled once (using set)
                            assert mock_pull.call_count == 1

            # Both persona files should be created
            assert (config.persona_dir / "innovator.json").exists()
            assert (config.persona_dir / "critic.json").exists()

            # Verify different prompts despite same model
            innovator_prompt = (config.persona_dir / "innovator_prompt.txt").read_text()
            critic_prompt = (config.persona_dir / "critic_prompt.txt").read_text()
            assert innovator_prompt != critic_prompt
