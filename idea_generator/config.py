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

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """
    Configuration for the idea-generator CLI.

    Settings are loaded from (in priority order):
    1. CLI arguments (passed directly to commands)
    2. Environment variables (from .env file or system)
    3. Config file (config.yaml)
    4. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IDEA_GEN_",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )

    # GitHub configuration
    github_repo: str = Field(
        default="",
        description="GitHub repository in format 'owner/repo'",
    )
    github_token: str | None = Field(
        default=None,
        description="GitHub API token for private repositories",
    )

    # Ollama configuration
    ollama_host: str = Field(
        default="http://localhost",
        description="Ollama server host",
    )
    ollama_port: int = Field(
        default=11434,
        description="Ollama server port",
        ge=1,
        le=65535,
    )

    # Model configuration
    model_innovator: str = Field(
        default="llama3.2:latest",
        description="Ollama model name for the innovator persona",
    )
    model_critic: str = Field(
        default="llama3.2:latest",
        description="Ollama model name for the critic persona",
    )

    # Processing configuration
    batch_size: int = Field(
        default=10,
        description="Number of items to process in a batch",
        ge=1,
        le=1000,
    )
    max_workers: int = Field(
        default=4,
        description="Maximum number of concurrent workers",
        ge=1,
        le=32,
    )

    # GitHub API configuration
    github_per_page: int = Field(
        default=100,
        description="Number of items per page for GitHub API requests",
        ge=1,
        le=100,
    )
    github_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for GitHub API requests",
        ge=0,
        le=10,
    )

    # Text processing configuration
    max_text_length: int = Field(
        default=8000,
        description="Maximum combined length of issue body and comments (in characters)",
        ge=1000,
        le=100000,
    )
    noise_filter_enabled: bool = Field(
        default=True,
        description="Enable noise/spam filtering for issues",
    )

    # LLM/Summarization configuration
    llm_timeout: float = Field(
        default=120.0,
        description="LLM request timeout in seconds (suitable for 3-8B models)",
        ge=10.0,
        le=600.0,
    )
    llm_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for LLM requests",
        ge=0,
        le=10,
    )
    summarization_max_tokens: int = Field(
        default=4000,
        description="Maximum tokens for issue text in summarization (rough estimate: 4 chars/token)",
        ge=1000,
        le=16000,
    )
    cache_max_file_size: int = Field(
        default=1_000_000,
        description="Maximum cache file size in bytes (default: 1MB)",
        ge=100_000,
        le=10_000_000,
    )

    # Grouping configuration
    grouping_max_batch_size: int = Field(
        default=20,
        description="Maximum number of summaries to process in a single grouping batch",
        ge=5,
        le=100,
    )
    grouping_max_batch_chars: int = Field(
        default=50000,
        description="Maximum character count for a single grouping batch",
        ge=10000,
        le=200000,
    )

    # Directory configuration
    output_dir: Path = Field(
        default=Path("output"),
        description="Directory for generated output",
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for ingested data",
    )
    persona_dir: Path = Field(
        default=Path("personas"),
        description="Directory for persona metadata and prompts",
    )

    @field_validator("github_repo")
    @classmethod
    def validate_github_repo(cls, v: str) -> str:
        """Validate GitHub repository format."""
        if v and "/" not in v:
            raise ValueError("github_repo must be in format 'owner/repo'")
        return v

    @field_validator("output_dir", "data_dir", "persona_dir")
    @classmethod
    def resolve_path(cls, v: Path) -> Path:
        """Resolve paths to absolute paths."""
        return v.resolve()

    @property
    def ollama_base_url(self) -> str:
        """Get the full Ollama API base URL."""
        return f"{self.ollama_host}:{self.ollama_port}"

    def ensure_directories(self) -> None:
        """Create all configured directories if they don't exist."""
        for directory in [self.output_dir, self.data_dir, self.persona_dir]:
            directory.mkdir(parents=True, exist_ok=True)


def load_config(
    github_repo: str | None = None,
    github_token: str | None = None,
    ollama_host: str | None = None,
    ollama_port: int | None = None,
    model_innovator: str | None = None,
    model_critic: str | None = None,
    batch_size: int | None = None,
    max_workers: int | None = None,
    github_per_page: int | None = None,
    github_max_retries: int | None = None,
    max_text_length: int | None = None,
    noise_filter_enabled: bool | None = None,
    output_dir: Path | None = None,
    data_dir: Path | None = None,
    persona_dir: Path | None = None,
) -> Config:
    """
    Load configuration from environment and CLI arguments.

    CLI arguments override environment variables and config file values.
    """
    # Build kwargs explicitly to maintain type safety
    kwargs: dict[str, str | int | Path | bool] = {}
    if github_repo is not None:
        kwargs["github_repo"] = github_repo
    if github_token is not None:
        kwargs["github_token"] = github_token
    if ollama_host is not None:
        kwargs["ollama_host"] = ollama_host
    if ollama_port is not None:
        kwargs["ollama_port"] = ollama_port
    if model_innovator is not None:
        kwargs["model_innovator"] = model_innovator
    if model_critic is not None:
        kwargs["model_critic"] = model_critic
    if batch_size is not None:
        kwargs["batch_size"] = batch_size
    if max_workers is not None:
        kwargs["max_workers"] = max_workers
    if github_per_page is not None:
        kwargs["github_per_page"] = github_per_page
    if github_max_retries is not None:
        kwargs["github_max_retries"] = github_max_retries
    if max_text_length is not None:
        kwargs["max_text_length"] = max_text_length
    if noise_filter_enabled is not None:
        kwargs["noise_filter_enabled"] = noise_filter_enabled
    if output_dir is not None:
        kwargs["output_dir"] = output_dir
    if data_dir is not None:
        kwargs["data_dir"] = data_dir
    if persona_dir is not None:
        kwargs["persona_dir"] = persona_dir

    return Config(**kwargs)  # type: ignore[arg-type]
