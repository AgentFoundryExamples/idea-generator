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
from typing import Optional

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
    github_token: Optional[str] = Field(
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
        return v.resolve() if v.is_absolute() else Path.cwd() / v

    @property
    def ollama_base_url(self) -> str:
        """Get the full Ollama API base URL."""
        return f"{self.ollama_host}:{self.ollama_port}"

    def ensure_directories(self) -> None:
        """Create all configured directories if they don't exist."""
        for directory in [self.output_dir, self.data_dir, self.persona_dir]:
            directory.mkdir(parents=True, exist_ok=True)


def load_config(
    github_repo: Optional[str] = None,
    github_token: Optional[str] = None,
    ollama_host: Optional[str] = None,
    ollama_port: Optional[int] = None,
    model_innovator: Optional[str] = None,
    model_critic: Optional[str] = None,
    batch_size: Optional[int] = None,
    max_workers: Optional[int] = None,
    output_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    persona_dir: Optional[Path] = None,
) -> Config:
    """
    Load configuration from environment and CLI arguments.
    
    CLI arguments override environment variables and config file values.
    """
    overrides = {}
    if github_repo is not None:
        overrides["github_repo"] = github_repo
    if github_token is not None:
        overrides["github_token"] = github_token
    if ollama_host is not None:
        overrides["ollama_host"] = ollama_host
    if ollama_port is not None:
        overrides["ollama_port"] = ollama_port
    if model_innovator is not None:
        overrides["model_innovator"] = model_innovator
    if model_critic is not None:
        overrides["model_critic"] = model_critic
    if batch_size is not None:
        overrides["batch_size"] = batch_size
    if max_workers is not None:
        overrides["max_workers"] = max_workers
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if data_dir is not None:
        overrides["data_dir"] = data_dir
    if persona_dir is not None:
        overrides["persona_dir"] = persona_dir

    return Config(**overrides)
