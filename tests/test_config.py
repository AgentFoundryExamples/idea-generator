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

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from idea_generator.config import Config, load_config


class TestConfig:
    """Test suite for configuration management."""

    def test_config_defaults(self) -> None:
        """Test that Config has sensible defaults."""
        config = Config()
        assert config.ollama_host == "http://localhost"
        assert config.ollama_port == 11434
        assert config.model_innovator == "llama3.2:latest"
        assert config.model_critic == "llama3.2:latest"
        assert config.model_grouping == "llama3.2:latest"
        assert config.model_summarizing == "llama3.2:latest"
        assert config.batch_size == 10
        assert config.max_workers == 4
        assert config.github_per_page == 100
        assert config.github_max_retries == 3
        assert config.max_text_length == 8000
        assert config.noise_filter_enabled is True

    def test_config_github_repo_validation(self) -> None:
        """Test GitHub repository format validation."""
        # Valid format
        config = Config(github_repo="owner/repo")
        assert config.github_repo == "owner/repo"

        # Invalid format
        with pytest.raises(ValidationError):
            Config(github_repo="invalid-format")

        # Empty string is allowed (will be validated elsewhere)
        config = Config(github_repo="")
        assert config.github_repo == ""

    def test_config_port_validation(self) -> None:
        """Test port number validation."""
        # Valid ports
        config = Config(ollama_port=8080)
        assert config.ollama_port == 8080

        # Invalid ports
        with pytest.raises(ValidationError):
            Config(ollama_port=0)

        with pytest.raises(ValidationError):
            Config(ollama_port=70000)

    def test_config_batch_size_validation(self) -> None:
        """Test batch size validation."""
        # Valid batch size
        config = Config(batch_size=50)
        assert config.batch_size == 50

        # Invalid batch sizes
        with pytest.raises(ValidationError):
            Config(batch_size=0)

        with pytest.raises(ValidationError):
            Config(batch_size=2000)

    def test_config_ollama_base_url(self) -> None:
        """Test ollama_base_url property."""
        config = Config(ollama_host="http://example.com", ollama_port=8080)
        assert config.ollama_base_url == "http://example.com:8080"

    def test_config_ensure_directories(self) -> None:
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            data_dir = Path(tmpdir) / "data"
            persona_dir = Path(tmpdir) / "personas"

            config = Config(
                output_dir=output_dir,
                data_dir=data_dir,
                persona_dir=persona_dir,
            )

            # Directories should not exist yet
            assert not output_dir.exists()
            assert not data_dir.exists()
            assert not persona_dir.exists()

            # Create directories
            config.ensure_directories()

            # Directories should now exist
            assert output_dir.exists()
            assert data_dir.exists()
            assert persona_dir.exists()

    def test_config_from_env_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading config from environment variables."""
        monkeypatch.setenv("IDEA_GEN_GITHUB_REPO", "test/repo")
        monkeypatch.setenv("IDEA_GEN_OLLAMA_HOST", "http://testhost")
        monkeypatch.setenv("IDEA_GEN_OLLAMA_PORT", "9999")
        monkeypatch.setenv("IDEA_GEN_MODEL_INNOVATOR", "test-model-1")
        monkeypatch.setenv("IDEA_GEN_MODEL_GROUPING", "test-grouping-model")
        monkeypatch.setenv("IDEA_GEN_MODEL_SUMMARIZING", "test-summarizing-model")
        monkeypatch.setenv("IDEA_GEN_BATCH_SIZE", "25")

        config = Config()
        assert config.github_repo == "test/repo"
        assert config.ollama_host == "http://testhost"
        assert config.ollama_port == 9999
        assert config.model_innovator == "test-model-1"
        assert config.model_grouping == "test-grouping-model"
        assert config.model_summarizing == "test-summarizing-model"
        assert config.batch_size == 25

    def test_load_config_with_overrides(self) -> None:
        """Test load_config function with CLI argument overrides."""
        config = load_config(
            github_repo="override/repo",
            ollama_port=7777,
            batch_size=15,
            model_grouping="custom-grouping",
            model_summarizing="custom-summarizer",
        )
        assert config.github_repo == "override/repo"
        assert config.ollama_port == 7777
        assert config.batch_size == 15
        assert config.model_grouping == "custom-grouping"
        assert config.model_summarizing == "custom-summarizer"

    def test_load_config_none_values_ignored(self) -> None:
        """Test that None values in load_config don't override defaults."""
        config = load_config(
            github_repo=None,
            ollama_port=None,
        )
        # Should use defaults
        assert config.ollama_port == 11434

    def test_config_path_resolution(self) -> None:
        """Test that paths are resolved to absolute paths."""
        config = Config(
            output_dir=Path("relative/output"),
            data_dir=Path("relative/data"),
        )
        # Paths should be absolute
        assert config.output_dir.is_absolute()
        assert config.data_dir.is_absolute()


class TestConfigEnvFile:
    """Test suite for .env file loading."""

    def test_config_loads_from_env_file(self) -> None:
        """Test loading configuration from .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "IDEA_GEN_GITHUB_REPO=envfile/repo\n"
                "IDEA_GEN_OLLAMA_PORT=8888\n"
                "IDEA_GEN_BATCH_SIZE=30\n"
            )

            # Change to tmpdir to make .env file discoverable
            original_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = Config()
                assert config.github_repo == "envfile/repo"
                assert config.ollama_port == 8888
                assert config.batch_size == 30
            finally:
                os.chdir(original_dir)
