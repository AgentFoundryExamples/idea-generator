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
ModelGroupingOption = Annotated[
    str | None,
    typer.Option(
        "--model-grouping",
        help="Model for grouping agent (default: llama3.2:latest, can use custom modelfile)",
    ),
]
ModelSummarizingOption = Annotated[
    str | None,
    typer.Option(
        "--model-summarizing",
        help="Model for summarizing agent (default: llama3.2:latest, can use custom modelfile)",
    ),
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
IssueLimitOption = Annotated[
    int | None,
    typer.Option(
        "--issue-limit",
        help="Maximum number of issues to ingest (default: no limit)",
        min=1,
    ),
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
    issue_limit: IssueLimitOption = None,
) -> None:
    """
    Ingest open issues from a GitHub repository.

    This command:
    - Fetches open issues sorted by most recently updated
    - Retrieves comment threads for each issue
    - Normalizes and cleans the data
    - Applies noise filtering
    - Saves normalized JSON to the data directory
    - Optionally limits the number of issues ingested (--issue-limit)
    """
    try:
        config = load_config(
            github_repo=github_repo,
            github_token=github_token,
            data_dir=data_dir,
            github_issue_limit=issue_limit,
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
            limit_msg = f" (limit: {config.github_issue_limit})" if config.github_issue_limit else ""
            typer.echo(f"Fetching open issues{limit_msg}...")
            try:
                issues = client.fetch_issues(owner, repo, state="open", limit=config.github_issue_limit)
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
    model_summarizing: ModelSummarizingOption = None,
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
            model_summarizing=model_summarizing,
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
        typer.echo(f"Model: {config.model_summarizing}")
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
            # Validate model exists
            if not llm_client.model_exists(config.model_summarizing):
                available = llm_client.list_models()
                typer.echo(
                    f"Error: Summarization model '{config.model_summarizing}' not found on Ollama server.\n"
                    f"Available models: {', '.join(available) or 'none'}\n\n"
                    f"To build the custom modelfile:\n"
                    f"  ollama create {config.model_summarizing} -f idea_generator/llm/modelfiles/summarizer.Modelfile\n\n"
                    f"Or use a default model:\n"
                    f"  export IDEA_GEN_MODEL_SUMMARIZING=llama3.2:latest",
                    err=True,
                )
                raise typer.Exit(code=1)

            pipeline = SummarizationPipeline(
                llm_client=llm_client,
                model=config.model_summarizing,
                prompt_template_path=prompt_path,
                max_tokens=config.summarization_max_tokens,
                cache_dir=cache_dir,
                cache_max_file_size=config.cache_max_file_size,
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
def group(
    github_repo: GithubRepoOption = None,
    output_dir: OutputDirOption = None,
    ollama_host: OllamaHostOption = None,
    ollama_port: OllamaPortOption = None,
    model_grouping: ModelGroupingOption = None,
    skip_noise: Annotated[
        bool,
        typer.Option("--skip-noise", help="Skip summaries already flagged as noise"),
    ] = False,
    max_batch_size: Annotated[
        int | None,
        typer.Option("--max-batch-size", help="Maximum summaries per batch (default: 20)"),
    ] = None,
    max_batch_chars: Annotated[
        int | None,
        typer.Option("--max-batch-chars", help="Maximum characters per batch (default: 50000)"),
    ] = None,
) -> None:
    """
    Group summarized issues into actionable idea clusters.

    This command:
    - Loads summarized issues from the output directory
    - Processes summaries in batches through the grouper LLM persona
    - Merges duplicate issues and splits multi-topic issues
    - Aggregates metrics deterministically across cluster members
    - Saves idea clusters to the output directory

    The grouper uses the same Ollama model as the summarizer but with a
    different system prompt optimized for clustering and deduplication.

    Batching is used to respect context window limits. Issues are processed
    in chunks defined by --max-batch-size and --max-batch-chars.
    """
    from pathlib import Path

    from .llm.client import OllamaClient, OllamaError
    from .models import SummarizedIssue
    from .pipelines.grouping import GroupingError, GroupingPipeline

    try:
        config = load_config(
            github_repo=github_repo,
            output_dir=output_dir,
            ollama_host=ollama_host,
            ollama_port=ollama_port,
            model_grouping=model_grouping,
        )

        # Apply CLI overrides for grouping config
        if max_batch_size is not None:
            config.grouping_max_batch_size = max_batch_size
        if max_batch_chars is not None:
            config.grouping_max_batch_chars = max_batch_chars

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

        typer.echo(f"Grouping summaries from {config.github_repo}...")
        typer.echo(f"Output directory: {config.output_dir}")
        typer.echo(f"Model: {config.model_grouping}")
        typer.echo(f"Ollama endpoint: {config.ollama_base_url}")
        typer.echo(
            f"Batch limits: size={config.grouping_max_batch_size}, "
            f"chars={config.grouping_max_batch_chars}\n"
        )

        # Ensure directories exist
        config.ensure_directories()

        # Load summaries
        summaries_file = config.output_dir / f"{owner}_{repo}_summaries.json"
        if not summaries_file.exists():
            typer.echo(
                f"Error: Summaries file not found: {summaries_file}\n"
                "Please run 'idea-generator summarize' first.",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(f"Loading summaries from {summaries_file}...")
        with open(summaries_file, encoding="utf-8") as f:
            summaries_data = json.load(f)

        summaries = [SummarizedIssue(**s) for s in summaries_data]
        typer.echo(f"✓ Loaded {len(summaries)} summaries\n")

        if not summaries:
            typer.echo("No summaries to group.")
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

        # Initialize grouping pipeline
        prompt_path = Path(__file__).parent / "llm" / "prompts" / "grouper.txt"

        try:
            # Validate model exists
            if not llm_client.model_exists(config.model_grouping):
                available = llm_client.list_models()
                typer.echo(
                    f"Error: Grouping model '{config.model_grouping}' not found on Ollama server.\n"
                    f"Available models: {', '.join(available) or 'none'}\n\n"
                    f"To build the custom modelfile:\n"
                    f"  ollama create {config.model_grouping} -f idea_generator/llm/modelfiles/grouping.Modelfile\n\n"
                    f"Or use a default model:\n"
                    f"  export IDEA_GEN_MODEL_GROUPING=llama3.2:latest",
                    err=True,
                )
                raise typer.Exit(code=1)

            pipeline = GroupingPipeline(
                llm_client=llm_client,
                model=config.model_grouping,
                prompt_template_path=prompt_path,
                max_batch_size=config.grouping_max_batch_size,
                max_batch_chars=config.grouping_max_batch_chars,
            )
        except GroupingError as e:
            typer.echo(f"Error initializing pipeline: {e}", err=True)
            raise typer.Exit(code=1) from e

        # Group summaries
        typer.echo("Processing summaries through grouper persona...")
        typer.echo(f"Configuration: skip_noise={skip_noise}\n")

        try:
            clusters = pipeline.group_summaries(summaries, skip_noise=skip_noise)
        except Exception as e:
            typer.echo(f"Error during grouping: {e}", err=True)
            raise typer.Exit(code=1) from e
        finally:
            llm_client.close()

        if not clusters:
            typer.echo("No clusters generated.")
            return

        # Save clusters
        output_file = config.output_dir / f"{owner}_{repo}_clusters.json"
        typer.echo(f"\nSaving clusters to {output_file}...")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                [cluster.model_dump(mode="json") for cluster in clusters],
                f,
                indent=2,
                ensure_ascii=False,
            )

        typer.echo(f"✓ Saved {len(clusters)} clusters\n")

        # Summary statistics
        total_issues = sum(len(c.member_issue_ids) for c in clusters)
        singleton_count = sum(1 for c in clusters if len(c.member_issue_ids) == 1)
        avg_cluster_size = total_issues / len(clusters)

        typer.echo("✅ Grouping completed successfully!\n")
        typer.echo("Cluster Statistics:")
        typer.echo(f"  - Total clusters: {len(clusters)}")
        typer.echo(f"  - Singleton clusters: {singleton_count}")
        typer.echo(f"  - Multi-member clusters: {len(clusters) - singleton_count}")
        typer.echo(f"  - Average cluster size: {avg_cluster_size:.1f} issues")
        typer.echo(f"  - Total issues covered: {total_issues}")
        typer.echo(f"\nOutput: {output_file}")

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
        # Invalid JSON in summaries file
        typer.echo(f"Invalid JSON in summaries file: {e}", err=True)
        raise typer.Exit(code=1) from e
    except OllamaError as e:
        # LLM/Ollama specific errors
        typer.echo(f"Ollama error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except GroupingError as e:
        # Grouping pipeline errors
        typer.echo(f"Grouping error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        # Unexpected errors
        typer.echo(f"Unexpected error during grouping: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def run(
    github_repo: GithubRepoOption = None,
    github_token: GithubTokenOption = None,
    ollama_host: OllamaHostOption = None,
    ollama_port: OllamaPortOption = None,
    model_innovator: ModelInnovatorOption = None,
    output_dir: OutputDirOption = None,
    data_dir: DataDirOption = None,
    issue_limit: IssueLimitOption = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Force regeneration of all artifacts (skip cache)"),
    ] = False,
    skip_json: Annotated[
        bool,
        typer.Option("--skip-json", help="Skip JSON report generation"),
    ] = False,
    skip_markdown: Annotated[
        bool,
        typer.Option("--skip-markdown", help="Skip Markdown report generation"),
    ] = False,
    top_ideas: Annotated[
        int | None,
        typer.Option("--top-ideas", help="Number of top ideas in Markdown report (default: 10)"),
    ] = None,
) -> None:
    """
    Run the complete idea generation pipeline end-to-end.

    This command orchestrates all stages:
    1. Ingest issues from GitHub
    2. Summarize with LLM persona
    3. Group into clusters
    4. Rank by composite score
    5. Generate JSON and Markdown reports

    Intermediate artifacts are cached to enable resumption after failures.
    Use --force to regenerate all artifacts from scratch.
    """
    from .pipelines.orchestrator import Orchestrator, OrchestratorError

    try:
        config = load_config(
            github_repo=github_repo,
            github_token=github_token,
            ollama_host=ollama_host,
            ollama_port=ollama_port,
            model_innovator=model_innovator,
            output_dir=output_dir,
            data_dir=data_dir,
            github_issue_limit=issue_limit,
        )

        # Override top_ideas if provided
        if top_ideas is not None:
            config.top_ideas_count = top_ideas

        # Validate required configuration
        if not config.github_repo:
            typer.echo(
                "Error: GitHub repository not configured.\n"
                "Provide via --github-repo or set IDEA_GEN_GITHUB_REPO in .env",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo("=" * 60)
        typer.echo("🚀 Running Complete Idea Generation Pipeline")
        typer.echo("=" * 60)
        typer.echo(f"\nRepository: {config.github_repo}")
        typer.echo(f"Model: {config.model_innovator}")
        typer.echo(f"Ollama endpoint: {config.ollama_base_url}")
        typer.echo(f"Output directory: {config.output_dir}")
        typer.echo(f"Data directory: {config.data_dir}")
        typer.echo(f"\nOptions:")
        typer.echo(f"  - Force regeneration: {force}")
        typer.echo(f"  - Skip JSON: {skip_json}")
        typer.echo(f"  - Skip Markdown: {skip_markdown}")
        typer.echo(f"  - Top ideas count: {config.top_ideas_count}")
        typer.echo(f"\nScoring Weights:")
        typer.echo(f"  - Novelty: {config.ranking_weight_novelty:.2f}")
        typer.echo(f"  - Feasibility: {config.ranking_weight_feasibility:.2f}")
        typer.echo(f"  - Desirability: {config.ranking_weight_desirability:.2f}")
        typer.echo(f"  - Attention: {config.ranking_weight_attention:.2f}")
        typer.echo("\n" + "=" * 60 + "\n")

        # Run orchestrator
        orchestrator = Orchestrator(config)
        results = orchestrator.run(
            force=force,
            skip_json=skip_json,
            skip_markdown=skip_markdown,
        )

        # Display results
        typer.echo("\n" + "=" * 60)
        typer.echo("✅ Pipeline Completed Successfully!")
        typer.echo("=" * 60 + "\n")
        typer.echo("Summary:")
        if "issues_count" in results:
            typer.echo(f"  - Issues ingested: {results['issues_count']}")
        if "summaries_count" in results:
            typer.echo(f"  - Summaries generated: {results['summaries_count']}")
        if "clusters_count" in results:
            typer.echo(f"  - Clusters created: {results['clusters_count']}")

        typer.echo("\nReports generated:")
        if "json_report" in results:
            typer.echo(f"  - JSON: {results['json_report']}")
        if "markdown_report" in results:
            typer.echo(f"  - Markdown: {results['markdown_report']}")

        typer.echo("\n" + "=" * 60)

    except OrchestratorError as e:
        typer.echo(f"Pipeline error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(code=1) from e


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
