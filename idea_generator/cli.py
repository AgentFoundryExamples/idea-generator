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
from typing import Annotated

import typer

from .config import load_config
from .setup import SetupError, run_setup

app = typer.Typer(
    name="idea-generator",
    help="Generate ideas from GitHub repositories using Ollama LLM personas",
    add_completion=False,
)


# Common CLI options
GithubRepoOption = Annotated[
    str | None,
    typer.Option("--github-repo", "-r", help="GitHub repository in format 'owner/repo'"),
]
GithubTokenOption = Annotated[
    str | None,
    typer.Option(
        "--github-token",
        "-t",
        help="GitHub API token for private repositories",
        envvar="GITHUB_TOKEN",
    ),
]
OllamaHostOption = Annotated[
    str | None,
    typer.Option("--ollama-host", help="Ollama server host (default: http://localhost)"),
]
OllamaPortOption = Annotated[
    int | None,
    typer.Option("--ollama-port", help="Ollama server port (default: 11434)"),
]
ModelInnovatorOption = Annotated[
    str | None,
    typer.Option(
        "--model-innovator", help="Model for innovator persona (default: llama3.2:latest)"
    ),
]
ModelCriticOption = Annotated[
    str | None,
    typer.Option("--model-critic", help="Model for critic persona (default: llama3.2:latest)"),
]
OutputDirOption = Annotated[
    Path | None,
    typer.Option("--output-dir", "-o", help="Output directory (default: ./output)"),
]
DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", "-d", help="Data directory (default: ./data)"),
]
PersonaDirOption = Annotated[
    Path | None,
    typer.Option("--persona-dir", "-p", help="Persona directory (default: ./personas)"),
]


@app.command()
def setup(
    github_repo: GithubRepoOption = None,
    github_token: GithubTokenOption = None,
    ollama_host: OllamaHostOption = None,
    ollama_port: OllamaPortOption = None,
    model_innovator: ModelInnovatorOption = None,
    model_critic: ModelCriticOption = None,
    output_dir: OutputDirOption = None,
    data_dir: DataDirOption = None,
    persona_dir: PersonaDirOption = None,
    skip_pull: Annotated[
        bool,
        typer.Option(
            "--skip-pull", help="Skip pulling models (for testing or when already installed)"
        ),
    ] = False,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Offline mode - skip all network operations"),
    ] = False,
) -> None:
    """
    Set up the idea-generator environment.

    This command:
    - Validates Ollama installation and server connection
    - Pulls required Ollama models (innovator and critic personas)
    - Creates necessary directories
    - Saves persona metadata and system prompts
    """
    try:
        config = load_config(
            github_repo=github_repo,
            github_token=github_token,
            ollama_host=ollama_host,
            ollama_port=ollama_port,
            model_innovator=model_innovator,
            model_critic=model_critic,
            output_dir=output_dir,
            data_dir=data_dir,
            persona_dir=persona_dir,
        )
        run_setup(config, skip_pull=skip_pull, offline=offline)
    except SetupError as e:
        typer.echo(f"Setup failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Unexpected error during setup: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def ingest(
    github_repo: GithubRepoOption = None,
    github_token: GithubTokenOption = None,
    data_dir: DataDirOption = None,
) -> None:
    """
    Ingest data from a GitHub repository.

    This command will be implemented in a future iteration to:
    - Clone or fetch the specified GitHub repository
    - Extract relevant information (issues, PRs, code structure)
    - Store processed data for later analysis
    """
    config = load_config(
        github_repo=github_repo,
        github_token=github_token,
        data_dir=data_dir,
    )
    typer.echo("Ingesting repository data...")
    typer.echo(f"Repository: {config.github_repo or 'Not configured'}")
    typer.echo(f"Data directory: {config.data_dir}")
    typer.echo("\n⚠ This command is not yet implemented.")
    typer.echo("This is a placeholder for future development.")


@app.command()
def summarize(
    data_dir: DataDirOption = None,
    output_dir: OutputDirOption = None,
) -> None:
    """
    Summarize ingested repository data.

    This command will be implemented in a future iteration to:
    - Process ingested repository data
    - Generate summaries and insights
    - Prepare data for idea generation
    """
    config = load_config(
        data_dir=data_dir,
        output_dir=output_dir,
    )
    typer.echo("Summarizing repository data...")
    typer.echo(f"Data directory: {config.data_dir}")
    typer.echo(f"Output directory: {config.output_dir}")
    typer.echo("\n⚠ This command is not yet implemented.")
    typer.echo("This is a placeholder for future development.")


@app.command()
def run(
    github_repo: GithubRepoOption = None,
    github_token: GithubTokenOption = None,
    ollama_host: OllamaHostOption = None,
    ollama_port: OllamaPortOption = None,
    model_innovator: ModelInnovatorOption = None,
    model_critic: ModelCriticOption = None,
    output_dir: OutputDirOption = None,
    data_dir: DataDirOption = None,
    persona_dir: PersonaDirOption = None,
) -> None:
    """
    Run the complete idea generation pipeline.

    This command will be implemented in a future iteration to:
    - Execute the innovator persona to generate ideas
    - Execute the critic persona to evaluate ideas
    - Generate final reports and recommendations
    """
    config = load_config(
        github_repo=github_repo,
        github_token=github_token,
        ollama_host=ollama_host,
        ollama_port=ollama_port,
        model_innovator=model_innovator,
        model_critic=model_critic,
        output_dir=output_dir,
        data_dir=data_dir,
        persona_dir=persona_dir,
    )
    typer.echo("Running idea generation pipeline...")
    typer.echo(f"Repository: {config.github_repo or 'Not configured'}")
    typer.echo(f"Innovator model: {config.model_innovator}")
    typer.echo(f"Critic model: {config.model_critic}")
    typer.echo(f"Output directory: {config.output_dir}")
    typer.echo("\n⚠ This command is not yet implemented.")
    typer.echo("This is a placeholder for future development.")


@app.callback()
def main() -> None:
    """
    idea-generator: Generate ideas from GitHub repositories using Ollama LLM personas.

    This tool uses two LLM personas (innovator and critic) to analyze GitHub repositories
    and generate creative, well-evaluated ideas for improvements and new features.
    """
    pass


if __name__ == "__main__":
    app()
