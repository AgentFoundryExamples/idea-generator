# idea-generator

A CLI tool that generates ideas from GitHub repositories using Ollama LLM personas. The tool uses two distinct personas—an innovator and a critic—to analyze codebases and generate creative, well-evaluated ideas for improvements and new features.

## Overview

The idea-generator leverages large language models running locally through Ollama to:
- Analyze GitHub repository structure and content
- Generate innovative ideas through an "innovator" persona
- Critically evaluate ideas through a "critic" persona
- Produce actionable insights and recommendations

## Prerequisites

### Required Software

1. **Python 3.11+**: The project requires Python 3.11 or later
   - Check version: `python --version`
   - Download from: https://www.python.org/downloads/

2. **Ollama**: Local LLM runtime for running models
   - Download from: https://ollama.ai/download
   - Follow installation instructions for your operating system
   - Verify installation: `ollama --version`
   - Start the server: `ollama serve`

### System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL
- **RAM**: 8GB minimum (16GB+ recommended for larger models)
- **Disk Space**: At least 10GB free (models can be several GB each)
- **Network**: Internet connection for initial model downloads

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AgentFoundryExamples/idea-generator.git
cd idea-generator
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install the Package

Install in development mode with all dependencies:

```bash
pip install -e ".[dev]"
```

Or for production use:

```bash
pip install -e .
```

### 4. Verify Installation

```bash
idea-generator --help
```

You should see the CLI help output with available commands.

## Configuration

### Environment Variables

The tool can be configured using environment variables, a `.env` file, or CLI arguments.

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and configure your settings:

```bash
# Required: GitHub repository to analyze
IDEA_GEN_GITHUB_REPO=owner/repo

# Optional: GitHub token for private repos or higher rate limits
IDEA_GEN_GITHUB_TOKEN=your_github_token_here

# Ollama configuration (defaults shown)
IDEA_GEN_OLLAMA_HOST=http://localhost
IDEA_GEN_OLLAMA_PORT=11434

# Model selection (both default to llama3.2:latest)
IDEA_GEN_MODEL_INNOVATOR=llama3.2:latest
IDEA_GEN_MODEL_CRITIC=llama3.2:latest
```

### Getting a GitHub Token

For private repositories or to avoid rate limits:

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token (classic) with `repo` scope for private repos, or `public_repo` scope for public repos
3. Copy the token and add it to your `.env` file

**Token Scopes:**
- `public_repo`: Required for accessing public repositories (read-only)
- `repo`: Required for accessing private repositories (includes `public_repo`)

## Usage

### Step 1: Setup

Run the setup command to prepare your environment:

```bash
idea-generator setup
```

This command will:
- ✓ Verify Ollama is installed and accessible
- ✓ Connect to the Ollama server
- ✓ Pull required models (innovator and critic personas)
- ✓ Create necessary directories (`output/`, `data/`, `personas/`)
- ✓ Save persona metadata and system prompts

**Options:**
- `--skip-pull`: Skip model pulling (useful if models are already installed)
- `--offline`: Skip all network operations (for air-gapped environments)
- `--model-innovator MODEL`: Override the innovator model
- `--model-critic MODEL`: Override the critic model

**Example:**

```bash
# Use different models for each persona
idea-generator setup --model-innovator llama3.2:latest --model-critic llama3.1:latest

# Skip pulling if models are already installed
idea-generator setup --skip-pull

# Offline mode (requires models to be pre-installed)
idea-generator setup --offline
```

### Step 2: Ingest Repository Data

```bash
idea-generator ingest --github-repo owner/repo
```

This command will:
- ✓ Fetch all open issues with pagination
- ✓ Retrieve comment threads for each issue
- ✓ Normalize and clean the data (strip markdown noise, deduplicate comments)
- ✓ Apply noise filtering to flag low-signal issues
- ✓ Truncate combined text to fit within token limits (default: 8000 characters)
- ✓ Save normalized JSON to the data directory

**Options:**
- `--github-repo`, `-r`: GitHub repository in format 'owner/repo' (required)
- `--github-token`, `-t`: GitHub API token (optional, can be set via `IDEA_GEN_GITHUB_TOKEN`)
- `--data-dir`, `-d`: Data directory (default: ./data)

**Examples:**

```bash
# Ingest from a public repository
idea-generator ingest --github-repo facebook/react

# Ingest from a private repository (requires token)
idea-generator ingest --github-repo myorg/private-repo --github-token ghp_xxx

# Use custom data directory
idea-generator ingest --github-repo owner/repo --data-dir /custom/data
```

**Pagination and Rate Limits:**

The ingestion process automatically handles:
- **Pagination**: Fetches all issues and comments across multiple pages (100 items per page by default)
- **Rate Limits**: Implements exponential backoff and retry logic when rate limits are hit
- **Caching**: Raw API responses are cached to `data/cache/` for offline re-use and debugging

**Truncation Behavior:**

To ensure data fits within LLM context windows:
- Combined issue body + comments are limited to 8000 characters by default (configurable via `IDEA_GEN_MAX_TEXT_LENGTH`)
- Issue body gets priority (at least 50% of the limit)
- Comments are included in order until the limit is reached
- Truncation is logged and tracked in the output JSON

**Noise Filtering:**

Issues are automatically flagged (but not removed) if they match noise patterns:
- Spam labels (spam, invalid, wontfix, duplicate)
- Bot authors (dependabot, renovate, etc.)
- Single-word titles
- Empty or very short bodies
- Common spam patterns (test, testing, hello, hi, hey)

Flagged issues are included in the output with `is_noise: true` and a `noise_reason` field.

**Output Format:**

Normalized issues are saved to `data/owner_repo_issues.json` with this structure:

```json
[
  {
    "id": 123456789,
    "number": 42,
    "title": "Issue title",
    "body": "Cleaned issue body (markdown stripped)",
    "labels": ["bug", "enhancement"],
    "state": "open",
    "reactions": {"+1": 5, "heart": 2},
    "comments": [
      {
        "id": 987654321,
        "author": "username",
        "body": "Cleaned comment body",
        "created_at": "2025-01-01T12:00:00+00:00",
        "reactions": {"+1": 1}
      }
    ],
    "url": "https://github.com/owner/repo/issues/42",
    "created_at": "2025-01-01T10:00:00+00:00",
    "updated_at": "2025-01-02T10:00:00+00:00",
    "is_noise": false,
    "noise_reason": null,
    "truncated": false,
    "original_length": 1234
  }
]
```

**Edge Cases Handled:**

- **Large repositories**: Streams paginated requests without exhausting memory
- **Deleted users**: Issues/comments from deleted accounts have `author: null`
- **Missing content**: Issues with null/empty bodies are handled gracefully
- **Non-UTF8 characters**: Emoji and RTL scripts are preserved in valid JSON
- **API errors**: 410 (Gone) on deleted comments returns empty object; 403/404 errors are retried or skipped
- **Private repos**: Insufficient token scopes raise actionable errors

### Step 3: Summarize Issues with LLM Persona

```bash
idea-generator summarize --github-repo owner/repo
```

This command:
- ✓ Loads normalized issues from the data directory
- ✓ Processes each issue sequentially through the summarizer LLM persona
- ✓ Generates structured summaries with quantitative metrics
- ✓ Caches results to avoid redundant LLM API calls
- ✓ Saves summarized issues to the output directory

**Options:**
- `--github-repo`, `-r`: GitHub repository in format 'owner/repo' (required)
- `--data-dir`, `-d`: Data directory containing normalized issues (default: ./data)
- `--output-dir`, `-o`: Output directory for summaries (default: ./output)
- `--ollama-host`: Ollama server host (default: http://localhost)
- `--ollama-port`: Ollama server port (default: 11434)
- `--model-innovator`: Model to use for summarization (default: llama3.2:latest)
- `--skip-cache`: Bypass cache and regenerate all summaries
- `--skip-noise`: Skip issues already flagged as noise

**Examples:**

```bash
# Summarize issues from a repository
idea-generator summarize --github-repo facebook/react

# Use a different model
idea-generator summarize --github-repo owner/repo --model-innovator llama3.2:8b

# Regenerate all summaries (bypass cache)
idea-generator summarize --github-repo owner/repo --skip-cache

# Skip noise issues
idea-generator summarize --github-repo owner/repo --skip-noise
```

**Summarizer Persona Behavior:**

The summarizer uses a 3-8B parameter model (e.g., `llama3.2:latest`) running locally through Ollama. It analyzes each normalized issue independently to avoid context ballooning and generates:

1. **Condensed Summary**: 2-3 sentence summary of the issue and key discussion points
2. **Topic Classification**: Primary area (e.g., performance, security, UI/UX, bug, feature)
3. **Quantitative Metrics** (0.0-1.0 scale):
   - **Novelty**: How innovative or unique is this idea
   - **Feasibility**: How practical to implement given typical constraints
   - **Desirability**: How valuable to users/stakeholders
   - **Attention**: Community engagement level (reactions, comments)
4. **Noise Flag**: Whether issue is likely spam/low-quality

**Context and Batching:**

- **Sequential Processing**: Issues are processed one at a time to prevent context overflow
- **Token Budget**: Each issue is limited to ~4000 tokens (configurable via `IDEA_GEN_SUMMARIZATION_MAX_TOKENS`)
- **Truncation**: Long issue bodies and comments are truncated deterministically with metadata preserved
- **Progress Logging**: Real-time feedback on processing status
- **Caching**: Successful summaries are cached by issue ID to enable resumption after failures

**Configuration Keys:**

Environment variables (set in `.env` or system environment):

```bash
# Summarization-specific configuration
IDEA_GEN_SUMMARIZATION_MAX_TOKENS=4000   # Max tokens per issue (~4 chars/token)
IDEA_GEN_LLM_TIMEOUT=120.0               # LLM request timeout (seconds)
IDEA_GEN_LLM_MAX_RETRIES=3               # Max retry attempts for failed requests
```

**Output Format:**

Summaries are saved to `output/owner_repo_summaries.json`:

```json
[
  {
    "issue_id": 123456789,
    "source_number": 42,
    "title": "Add dark mode support",
    "summary": "Users request dark mode to reduce eye strain during night use. Discussion suggests CSS variables for theming. Strong community support.",
    "topic_area": "UI/UX",
    "novelty": 0.3,
    "feasibility": 0.8,
    "desirability": 0.9,
    "attention": 0.7,
    "noise_flag": false,
    "raw_issue_url": "https://github.com/owner/repo/issues/42"
  }
]
```

**Edge Cases:**

- **Malformed JSON**: LLM responses are validated and parsed with fallback extraction from markdown code blocks
- **Missing Metrics**: Issues with incomplete LLM responses are retried up to 3 times before being marked as failed
- **Truncation**: Issues exceeding token limits are truncated deterministically with metadata preserved for debugging
- **LLM Unavailable**: Connection failures trigger actionable error messages with retry suggestions
- **Noise Issues**: Can be automatically skipped using `--skip-noise` flag

**Important Notes:**

⚠️ **LLM Execution**: This command requires a running Ollama server with the specified model pulled. Ensure Ollama is running before executing:

```bash
# Start Ollama server
ollama serve

# Pull required model (if not already installed)
ollama pull llama3.2:latest
```

⚠️ **Processing Time**: Summarization is performed sequentially and can take several minutes for large repositories (1-2 seconds per issue for 3-8B models). Progress is logged in real-time.

⚠️ **No Batch Processing**: Issues are intentionally processed one at a time to avoid context overflow with small models. This is by design for deterministic, per-issue summaries.

### Step 4: Generate Ideas (Coming Soon)

```bash
idea-generator run --github-repo owner/repo
```

## Project Structure

```
idea-generator/
├── idea_generator/           # Main package directory
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # CLI interface (Typer commands)
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models (NormalizedIssue, SummarizedIssue)
│   ├── setup.py             # Setup workflow and Ollama integration
│   ├── cleaning.py          # Issue cleaning and normalization
│   ├── github_client.py     # GitHub API client with caching
│   ├── llm/                 # LLM integration components
│   │   ├── __init__.py     # LLM module initialization
│   │   ├── client.py        # Ollama HTTP client wrapper
│   │   └── prompts/         # LLM persona prompts
│   │       └── summarizer.txt  # Summarizer persona system prompt
│   └── pipelines/           # Processing pipelines
│       ├── __init__.py     # Pipeline module initialization
│       └── summarize.py     # Summarization pipeline
├── tests/                   # Test suite
│   ├── test_config.py       # Configuration tests
│   ├── test_models.py       # Model validation tests
│   ├── test_setup.py        # Setup workflow tests
│   ├── test_cleaning.py     # Data cleaning tests
│   ├── test_github_client.py # GitHub API client tests
│   ├── test_llm_client.py   # LLM client tests
│   ├── test_summarize_pipeline.py  # Summarization pipeline tests
│   ├── test_integration.py  # End-to-end integration tests
│   └── test_cli.py          # CLI integration tests
├── output/                  # Generated ideas and reports (created by setup)
├── data/                    # Ingested repository data (created by setup)
├── personas/                # Persona metadata and prompts (created by setup)
├── pyproject.toml          # Package configuration and dependencies
├── .env.example            # Example environment variables
├── .gitignore              # Git ignore patterns
└── README.md               # This file
```

## Troubleshooting

### Ollama Not Found

**Error**: `Ollama binary not found in PATH`

**Solution**:
1. Install Ollama from https://ollama.ai/download
2. Verify installation: `ollama --version`
3. Ensure Ollama is in your system PATH

### Ollama Server Not Running

**Error**: `Unable to connect to Ollama server`

**Solution**:
1. Start the Ollama server: `ollama serve`
2. Check if running on a different port: `ps aux | grep ollama`
3. Update `IDEA_GEN_OLLAMA_PORT` in `.env` if needed

### Model Download Fails

**Error**: Model pull fails or times out

**Solution**:
1. Check internet connection
2. Retry: `ollama pull llama3.2:latest`
3. Try a smaller model: `--model-innovator llama3.2:1b`
4. For air-gapped environments, manually transfer models (see Ollama docs)

### Permission Denied Creating Directories

**Error**: Cannot create output directories

**Solution**:
1. Check directory permissions
2. Specify custom directories: `--output-dir /path/to/writable/dir`
3. Run with appropriate permissions

## Advanced Configuration

### Using Different Models

You can use different models for each persona:

```bash
# Use a larger model for the innovator, smaller for critic
idea-generator setup \
  --model-innovator llama3.2:70b \
  --model-critic llama3.2:8b
```

### Custom Ollama Server

If Ollama is running on a different host or port:

```bash
idea-generator setup \
  --ollama-host http://192.168.1.100 \
  --ollama-port 11434
```

### Directory Customization

Customize where data is stored:

```bash
idea-generator setup \
  --output-dir /my/custom/output \
  --data-dir /my/custom/data \
  --persona-dir /my/custom/personas
```

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code with Black
black idea_generator tests

# Lint with Ruff
ruff check idea_generator tests

# Type check with MyPy
mypy idea_generator
```

### Adding New Dependencies

When adding dependencies, always pin versions in `pyproject.toml`:

```toml
dependencies = [
    "new-package==1.2.3",
]
```

Then regenerate the lock file:

```bash
pip install -e ".[dev]"
pip freeze > requirements.txt  # Optional: for legacy tooling
```



# Permanents (License, Contributing, Author)

Do not change any of the below sections

## License

This Agent Foundry Project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Contributing

Feel free to submit issues and enhancement requests!

## Author

Created by Agent Foundry and John Brosnihan
