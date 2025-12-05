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
import shutil
import subprocess
from pathlib import Path

import httpx
import typer

from .config import Config

# Persona system prompts
INNOVATOR_PROMPT = """You are an innovative thinker with a creative and optimistic mindset. Your role is to:
- Generate novel ideas and creative solutions
- Think outside the box and challenge conventional approaches
- Focus on possibilities and opportunities
- Embrace experimentation and calculated risks
- Look for connections and synergies between different concepts

When analyzing code or issues, you should propose innovative solutions, suggest new features,
and identify opportunities for improvement with an emphasis on creativity and forward-thinking."""

CRITIC_PROMPT = """You are a critical thinker with a pragmatic and analytical mindset. Your role is to:
- Evaluate ideas objectively and identify potential issues
- Consider practical constraints and implementation challenges
- Focus on risks, edge cases, and potential problems
- Ensure quality, maintainability, and robustness
- Ground discussions in reality and feasibility

When analyzing code or issues, you should critically evaluate proposals, identify potential
problems, and ensure solutions are practical, maintainable, and well-thought-out."""


class SetupError(Exception):
    """Exception raised when setup fails."""

    pass


def check_ollama_binary() -> bool:
    """
    Check if the ollama binary is available in PATH.

    Returns:
        True if ollama is available, False otherwise.
    """
    return shutil.which("ollama") is not None


def check_ollama_server(base_url: str, timeout: float = 5.0) -> bool:
    """
    Check if the Ollama server is running and accessible.

    Args:
        base_url: The base URL of the Ollama server (e.g., "http://localhost:11434")
        timeout: Request timeout in seconds

    Returns:
        True if server is accessible, False otherwise.
    """
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


def pull_model(model_name: str, show_progress: bool = True) -> bool:
    """
    Pull an Ollama model using the ollama CLI.

    Args:
        model_name: Name of the model to pull (e.g., "llama3.2:latest")
        show_progress: Whether to show progress output

    Returns:
        True if pull was successful, False otherwise.

    Raises:
        SetupError: If the ollama binary is not available.
    """
    if not check_ollama_binary():
        raise SetupError(
            "ollama binary not found in PATH. "
            "Please install Ollama from https://ollama.ai/download"
        )

    try:
        if show_progress:
            typer.echo(f"Pulling model: {model_name}")
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=not show_progress,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            if show_progress:
                typer.echo(f"Warning: Failed to pull model {model_name}", err=True)
                if result.stderr:
                    typer.echo(f"Error: {result.stderr}", err=True)
            return False
        if show_progress:
            typer.echo(f"✓ Successfully pulled model: {model_name}")
        return True
    except Exception as e:
        if show_progress:
            typer.echo(f"Error pulling model {model_name}: {e}", err=True)
        return False


def list_installed_models(base_url: str) -> list[str]:
    """
    List models currently installed in Ollama.

    Args:
        base_url: The base URL of the Ollama server

    Returns:
        List of installed model names, or empty list if unable to query.
    """
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
    except Exception:
        pass
    return []


def save_persona_metadata(persona_dir: Path, model_name: str, role: str, prompt: str) -> None:
    """
    Save persona metadata and system prompt to disk.

    Args:
        persona_dir: Directory to save persona files
        model_name: Name of the Ollama model for this persona
        role: Role name (e.g., "innovator" or "critic")
        prompt: System prompt for this persona
    """
    persona_dir.mkdir(parents=True, exist_ok=True)

    # Save metadata
    metadata = {
        "role": role,
        "model": model_name,
        "description": f"{role.capitalize()} persona using {model_name}",
    }
    metadata_file = persona_dir / f"{role}.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    # Save system prompt
    prompt_file = persona_dir / f"{role}_prompt.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)


def run_setup(config: Config, skip_pull: bool = False, offline: bool = False) -> None:
    """
    Run the complete setup workflow.

    Args:
        config: Configuration object
        skip_pull: Skip model pulling (useful for testing or when models are already installed)
        offline: Offline mode - skip all network operations

    Raises:
        SetupError: If setup fails at any critical step.
    """
    typer.echo("Starting idea-generator setup...\n")

    # Step 1: Check Ollama binary
    typer.echo("1. Checking for Ollama binary...")
    if not check_ollama_binary():
        raise SetupError(
            "❌ Ollama binary not found in PATH.\n\n"
            "Please install Ollama:\n"
            "  - Visit: https://ollama.ai/download\n"
            "  - Follow installation instructions for your OS\n"
            "  - Verify installation with: ollama --version"
        )
    typer.echo("✓ Ollama binary found\n")

    # Step 2: Check Ollama server (optional in offline mode)
    if not offline:
        typer.echo("2. Checking Ollama server connection...")
        server_url = config.ollama_base_url
        if not check_ollama_server(server_url):
            typer.echo(
                f"⚠ Warning: Unable to connect to Ollama server at {server_url}\n"
                f"Please ensure Ollama is running:\n"
                f"  - Start server with: ollama serve\n"
                f"  - Or check if running on a different port\n",
                err=True,
            )
            if not skip_pull:
                raise SetupError(
                    "Cannot proceed with model pulling without server connection. "
                    "Use --offline flag to skip network operations."
                )
        else:
            typer.echo(f"✓ Connected to Ollama server at {server_url}\n")

            # List installed models
            installed = list_installed_models(server_url)
            if installed:
                typer.echo(f"Currently installed models: {', '.join(installed)}\n")
    else:
        typer.echo("2. Skipping server check (offline mode)\n")

    # Step 3: Pull models
    if not skip_pull and not offline:
        typer.echo("3. Pulling Ollama models...")
        models_to_pull = {config.model_innovator, config.model_critic}

        success = True
        for model in models_to_pull:
            if not pull_model(model, show_progress=True):
                success = False

        if not success:
            typer.echo(
                "\n⚠ Warning: Some models failed to pull. "
                "You may need to pull them manually:\n"
                f"  ollama pull {config.model_innovator}\n"
                f"  ollama pull {config.model_critic}\n",
                err=True,
            )
        typer.echo()
    else:
        typer.echo("3. Skipping model pull (offline mode or skip-pull flag)\n")

    # Step 4: Create directories
    typer.echo("4. Creating output directories...")
    config.ensure_directories()
    typer.echo(f"✓ Created: {config.output_dir}")
    typer.echo(f"✓ Created: {config.data_dir}")
    typer.echo(f"✓ Created: {config.persona_dir}\n")

    # Step 5: Save persona metadata
    typer.echo("5. Saving persona metadata...")
    save_persona_metadata(
        config.persona_dir,
        config.model_innovator,
        "innovator",
        INNOVATOR_PROMPT,
    )
    save_persona_metadata(
        config.persona_dir,
        config.model_critic,
        "critic",
        CRITIC_PROMPT,
    )
    typer.echo(f"✓ Saved innovator persona (model: {config.model_innovator})")
    typer.echo(f"✓ Saved critic persona (model: {config.model_critic})\n")

    # Success message
    typer.echo("✅ Setup completed successfully!")
    typer.echo("\nNext steps:")
    typer.echo("  1. Configure your GitHub repository in .env or via --github-repo")
    typer.echo("  2. Run: idea-generator ingest")
    typer.echo("  3. Run: idea-generator generate")
