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

import json
from pathlib import Path
from typing import Annotated

import typer

from .cleaning import normalize_github_issue
from .config import load_config
from .github_client import GitHubAPIError, GitHubClient
from .models import NormalizedIssue
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
        envvar="IDEA_GEN_GITHUB_TOKEN",
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
    Ingest open issues from a GitHub repository.

    This command:
    - Fetches all open issues with pagination
    - Retrieves comment threads for each issue
    - Normalizes and cleans the data
    - Applies noise filtering
    - Saves normalized JSON to the data directory
    """
    try:
        config = load_config(
            github_repo=github_repo,
            github_token=github_token,
            data_dir=data_dir,
        )

        # Validate required configuration
        if not config.github_repo:
            typer.echo(
                "Error: GitHub repository not configured.\n"
                "Provide via --github-repo or set IDEA_GEN_GITHUB_REPO in .env",
                err=True,
            )
            raise typer.Exit(code=1)

        # Parse owner/repo
        try:
            owner, repo = config.github_repo.split("/")
        except ValueError:
            typer.echo(
                f"Error: Invalid repository format '{config.github_repo}'. "
                "Expected format: 'owner/repo'",
                err=True,
            )
            raise typer.Exit(code=1) from None

        typer.echo(f"Ingesting issues from {config.github_repo}...")
        typer.echo(f"Data directory: {config.data_dir}\n")

        # Ensure data directory exists
        config.ensure_directories()

        # Setup cache directory for raw responses
        cache_dir = config.data_dir / "cache"
        cache_dir.mkdir(exist_ok=True)

        # Initialize GitHub client
        with GitHubClient(
            token=config.github_token,
            per_page=config.github_per_page,
            max_retries=config.github_max_retries,
            cache_dir=cache_dir,
        ) as client:
            # Check repository access
            typer.echo("Checking repository access...")
            try:
                if not client.check_repository_access(owner, repo):
                    typer.echo(
                        f"Error: Repository '{config.github_repo}' not found or not accessible.\n"
                        "For private repositories, ensure IDEA_GEN_GITHUB_TOKEN is set with "
                        "'repo' scope.",
                        err=True,
                    )
                    raise typer.Exit(code=1)
                typer.echo("✓ Repository accessible\n")
            except GitHubAPIError as e:
                typer.echo(f"Error checking repository access: {e}", err=True)
                raise typer.Exit(code=1) from e

            # Fetch issues
            typer.echo("Fetching open issues...")
            try:
                issues = client.fetch_issues(owner, repo, state="open")
                typer.echo(f"✓ Found {len(issues)} open issues\n")
            except GitHubAPIError as e:
                typer.echo(f"Error fetching issues: {e}", err=True)
                raise typer.Exit(code=1) from e

            if not issues:
                typer.echo("No open issues found. Nothing to ingest.")
                return

            # Process each issue
            typer.echo("Processing issues and comments...")
            normalized_issues: list[NormalizedIssue] = []
            noise_count = 0
            truncated_count = 0

            for i, issue_data in enumerate(issues, 1):
                issue_number = issue_data["number"]
                typer.echo(f"  [{i}/{len(issues)}] Issue #{issue_number}...", nl=False)

                # Fetch comments
                try:
                    comments = client.fetch_issue_comments(owner, repo, issue_number)
                except GitHubAPIError as e:
                    typer.echo(f"\n  ⚠ Warning: Failed to fetch comments: {e}")
                    comments = []
                    typer.echo(f"  [{i}/{len(issues)}] Issue #{issue_number}...", nl=False)

                # Normalize issue
                normalized = normalize_github_issue(
                    issue_data,
                    comments,
                    max_text_length=config.max_text_length,
                    noise_filter_enabled=config.noise_filter_enabled,
                )
                normalized_issues.append(normalized)

                # Track metrics
                if normalized.is_noise:
                    noise_count += 1
                if normalized.truncated:
                    truncated_count += 1

                typer.echo(" ✓")

            typer.echo(f"\n✓ Processed {len(normalized_issues)} issues")
            typer.echo(f"  - Flagged as noise: {noise_count}")
            typer.echo(f"  - Truncated: {truncated_count}\n")

            # Save to JSON
            output_file = config.data_dir / f"{owner}_{repo}_issues.json"
            typer.echo(f"Saving normalized issues to {output_file}...")

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    [issue.model_dump(mode="json") for issue in normalized_issues],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            typer.echo(f"✓ Saved {len(normalized_issues)} issues\n")

            # Summary
            typer.echo("✅ Ingestion completed successfully!")
            typer.echo(f"\nOutput: {output_file}")
            typer.echo(f"Cache: {cache_dir}")

            if noise_count > 0:
                typer.echo(
                    f"\nNote: {noise_count} issues were flagged as noise. "
                    "They are included in the output but marked with 'is_noise: true'."
                )

    except Exception as e:
        typer.echo(f"Unexpected error during ingestion: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def summarize(
    github_repo: GithubRepoOption = None,
    data_dir: DataDirOption = None,
    output_dir: OutputDirOption = None,
    ollama_host: OllamaHostOption = None,
    ollama_port: OllamaPortOption = None,
    model_innovator: ModelInnovatorOption = None,
    skip_cache: Annotated[
        bool,
        typer.Option("--skip-cache", help="Skip cache and regenerate all summaries"),
    ] = False,
    skip_noise: Annotated[
        bool,
        typer.Option("--skip-noise", help="Skip issues already flagged as noise"),
    ] = False,
) -> None:
    """
    Summarize normalized issues using the LLM summarizer persona.

    This command:
    - Loads normalized issues from the data directory
    - Processes each issue sequentially through the summarizer LLM
    - Generates structured summaries with quantitative metrics
    - Caches results to avoid redundant API calls
    - Saves summarized issues to the output directory

    The summarizer uses a 3-8B parameter model (e.g., llama3.2) running locally
    through Ollama. Each issue is processed independently to avoid context ballooning.

    Metrics generated:
    - Novelty (0.0-1.0): How innovative or unique is this idea
    - Feasibility (0.0-1.0): How practical to implement
    - Desirability (0.0-1.0): How valuable to users
    - Attention (0.0-1.0): Community engagement level
    """
    from pathlib import Path

    from .llm.client import OllamaClient, OllamaError
    from .pipelines.summarize import SummarizationError, SummarizationPipeline

    try:
        config = load_config(
            github_repo=github_repo,
            data_dir=data_dir,
            output_dir=output_dir,
            ollama_host=ollama_host,
            ollama_port=ollama_port,
            model_innovator=model_innovator,
        )

        # Validate required configuration
        if not config.github_repo:
            typer.echo(
                "Error: GitHub repository not configured.\n"
                "Provide via --github-repo or set IDEA_GEN_GITHUB_REPO in .env",
                err=True,
            )
            raise typer.Exit(code=1)

        # Parse owner/repo
        try:
            owner, repo = config.github_repo.split("/")
        except ValueError:
            typer.echo(
                f"Error: Invalid repository format '{config.github_repo}'. "
                "Expected format: 'owner/repo'",
                err=True,
            )
            raise typer.Exit(code=1) from None

        typer.echo(f"Summarizing issues from {config.github_repo}...")
        typer.echo(f"Data directory: {config.data_dir}")
        typer.echo(f"Output directory: {config.output_dir}")
        typer.echo(f"Model: {config.model_innovator}")
        typer.echo(f"Ollama endpoint: {config.ollama_base_url}\n")

        # Ensure directories exist
        config.ensure_directories()

        # Load normalized issues
        issues_file = config.data_dir / f"{owner}_{repo}_issues.json"
        if not issues_file.exists():
            typer.echo(
                f"Error: Normalized issues file not found: {issues_file}\n"
                "Please run 'idea-generator ingest' first.",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(f"Loading issues from {issues_file}...")
        with open(issues_file, encoding="utf-8") as f:
            issues_data = json.load(f)

        issues = [NormalizedIssue(**issue_data) for issue_data in issues_data]
        typer.echo(f"✓ Loaded {len(issues)} issues\n")

        if not issues:
            typer.echo("No issues to summarize.")
            return

        # Initialize Ollama client
        typer.echo("Connecting to Ollama server...")
        try:
            llm_client = OllamaClient(
                base_url=config.ollama_base_url,
                timeout=config.llm_timeout,
                max_retries=config.llm_max_retries,
            )

            if not llm_client.check_health():
                typer.echo(
                    f"Error: Unable to connect to Ollama server at {config.ollama_base_url}\n"
                    "Please ensure Ollama is running:\n"
                    "  - Start server with: ollama serve\n"
                    "  - Or check if running on a different port",
                    err=True,
                )
                raise typer.Exit(code=1)

            typer.echo(f"✓ Connected to Ollama at {config.ollama_base_url}\n")

        except OllamaError as e:
            typer.echo(f"Error connecting to Ollama: {e}", err=True)
            raise typer.Exit(code=1) from e

        # Initialize summarization pipeline
        prompt_path = Path(__file__).parent / "llm" / "prompts" / "summarizer.txt"
        cache_dir = config.output_dir / "summarization_cache"

        try:
            pipeline = SummarizationPipeline(
                llm_client=llm_client,
                model=config.model_innovator,
                prompt_template_path=prompt_path,
                max_tokens=config.summarization_max_tokens,
                cache_dir=cache_dir,
            )
        except SummarizationError as e:
            typer.echo(f"Error initializing pipeline: {e}", err=True)
            raise typer.Exit(code=1) from e

        # Summarize issues
        typer.echo("Processing issues through summarizer persona...")
        typer.echo(f"Configuration: skip_cache={skip_cache}, skip_noise={skip_noise}\n")

        try:
            summaries = pipeline.summarize_issues(
                issues, skip_cache=skip_cache, skip_noise=skip_noise
            )
        except Exception as e:
            typer.echo(f"Error during summarization: {e}", err=True)
            raise typer.Exit(code=1) from e
        finally:
            llm_client.close()

        if not summaries:
            typer.echo("No summaries generated.")
            return

        # Save summaries
        output_file = config.output_dir / f"{owner}_{repo}_summaries.json"
        typer.echo(f"\nSaving summaries to {output_file}...")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                [summary.model_dump(mode="json") for summary in summaries],
                f,
                indent=2,
                ensure_ascii=False,
            )

        typer.echo(f"✓ Saved {len(summaries)} summaries\n")

        # Summary statistics
        avg_novelty = sum(s.novelty for s in summaries) / len(summaries)
        avg_feasibility = sum(s.feasibility for s in summaries) / len(summaries)
        avg_desirability = sum(s.desirability for s in summaries) / len(summaries)
        noise_count = sum(1 for s in summaries if s.noise_flag)

        typer.echo("✅ Summarization completed successfully!\n")
        typer.echo("Summary Statistics:")
        typer.echo(f"  - Total summaries: {len(summaries)}")
        typer.echo(f"  - Flagged as noise: {noise_count}")
        typer.echo(f"  - Average novelty: {avg_novelty:.2f}")
        typer.echo(f"  - Average feasibility: {avg_feasibility:.2f}")
        typer.echo(f"  - Average desirability: {avg_desirability:.2f}")
        typer.echo(f"\nOutput: {output_file}")
        typer.echo(f"Cache: {cache_dir}")

    except ValueError as e:
        # Configuration or validation errors
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except FileNotFoundError as e:
        # Missing files
        typer.echo(f"File not found: {e}", err=True)
        raise typer.Exit(code=1) from e
    except PermissionError as e:
        # Permission issues
        typer.echo(f"Permission denied: {e}", err=True)
        raise typer.Exit(code=1) from e
    except json.JSONDecodeError as e:
        # Invalid JSON in issues file
        typer.echo(f"Invalid JSON in issues file: {e}", err=True)
        raise typer.Exit(code=1) from e
    except OllamaError as e:
        # LLM/Ollama specific errors
        typer.echo(f"Ollama error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except SummarizationError as e:
        # Summarization pipeline errors
        typer.echo(f"Summarization error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        # Unexpected errors
        typer.echo(f"Unexpected error during summarization: {e}", err=True)
        raise typer.Exit(code=1) from e


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
