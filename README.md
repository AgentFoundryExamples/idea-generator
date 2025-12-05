# idea-generator

A CLI tool that generates ideas from GitHub repositories using Ollama LLM personas. The tool uses two distinct personas—an innovator and a critic—to analyze codebases and generate creative, well-evaluated ideas for improvements and new features.

## Overview

The idea-generator leverages large language models running locally through Ollama to:
- Analyze GitHub repository structure and content
- Generate innovative ideas through an "innovator" persona
- Critically evaluate ideas through a "critic" persona
- Produce actionable insights and recommendations

## Quick Start

Get started in 5 minutes:

```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve  # Keep running in separate terminal

# 2. Clone and install
git clone https://github.com/AgentFoundryExamples/idea-generator.git
cd idea-generator
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Setup
idea-generator setup

# 4. Analyze a repository
idea-generator run --github-repo facebook/react

# 5. View results
cat output/reports/top-ideas.md
```

📚 **Need more details?** See the [detailed usage guide](docs/USAGE.md) for comprehensive instructions.

## Architecture

The idea-generator follows a multi-stage pipeline architecture:

```mermaid
graph LR
    A[GitHub Issues] -->|Ingest| B[Normalized Data]
    B -->|Summarize| C[Issue Summaries]
    C -->|Group| D[Idea Clusters]
    D -->|Rank| E[Scored Ideas]
    E -->|Generate| F[Reports]
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#e1ffe1
    style E fill:#f5e1ff
    style F fill:#ffe1e1
```

### Pipeline Stages

1. **Ingest** (`idea-generator ingest`)
   - Fetches open issues from GitHub API
   - Retrieves comment threads
   - Cleans markdown and normalizes data
   - Filters noise/spam
   - Caches raw responses
   - **Output**: `data/owner_repo_issues.json`

2. **Summarize** (`idea-generator summarize`)
   - Processes each issue through LLM
   - Generates 2-3 sentence summaries
   - Classifies topic areas
   - Scores novelty, feasibility, desirability, attention
   - Caches individual summaries
   - **Output**: `output/owner_repo_summaries.json`

3. **Group** (`idea-generator group`)
   - Clusters similar issues together
   - Merges duplicates
   - Splits multi-topic issues
   - Aggregates metrics
   - Validates coverage
   - **Output**: `output/owner_repo_clusters.json`

4. **Rank** (part of `idea-generator run`)
   - Calculates composite scores
   - Applies weighted metrics
   - Deterministic tie-breaking
   - Sorts by priority
   - **Output**: Ranked cluster list

5. **Generate Reports** (part of `idea-generator run`)
   - Creates JSON dataset
   - Generates Markdown report
   - Formats with visual indicators
   - Links to source issues
   - **Output**: `output/reports/ideas.json` and `output/reports/top-ideas.md`

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant GitHub
    participant Ollama
    participant Cache
    
    User->>CLI: run --github-repo owner/repo
    CLI->>GitHub: Fetch issues + comments
    GitHub-->>CLI: Raw issue data
    CLI->>Cache: Store raw responses
    CLI->>Ollama: Summarize each issue
    Ollama-->>CLI: Summary + metrics
    CLI->>Cache: Store summaries
    CLI->>Ollama: Group summaries
    Ollama-->>CLI: Clusters
    CLI->>CLI: Rank clusters
    CLI->>CLI: Generate reports
    CLI-->>User: output/reports/
```

## Key Features

### 🚀 Intelligent Analysis
- **AI-Powered Summaries**: Local LLM generates concise, structured summaries
- **Quantitative Metrics**: Four-dimensional scoring (novelty, feasibility, desirability, attention)
- **Smart Clustering**: Automatically groups related issues and merges duplicates
- **Topic Classification**: Categorizes issues by domain (UI/UX, performance, security, etc.)

### 🔒 Privacy-Focused
- **100% Local**: All processing happens on your machine
- **No External APIs**: Only GitHub for data, Ollama for AI (both configurable)
- **Data Control**: You control where data is stored and cached

### ⚡ Performance Optimized
- **Smart Caching**: Avoids redundant API calls and LLM processing
- **Batched Operations**: Groups multiple issues for efficient processing
- **Resumable**: Failed runs can resume from last successful stage
- **Configurable**: Tune batch sizes, timeouts, and model selection for your hardware

### 🛠️ Developer Friendly
- **CLI-First**: Easy to use, script, and integrate into workflows
- **Well-Tested**: 225+ unit tests with 70%+ coverage
- **Type-Safe**: Full type hints with MyPy validation
- **Extensible**: Modular architecture, easy to customize personas and prompts

## What's New

### Version 0.1.0 (Initial Release)

This is the first public release of idea-generator! Key features include:

✨ **Core Capabilities**
- Complete CLI tool with 5 commands: setup, ingest, summarize, group, run
- AI-powered issue summarization with 4 quantitative metrics
- Intelligent clustering and deduplication
- Weighted ranking system with customizable priorities
- JSON and Markdown report generation

🔧 **Technical Features**
- Full Ollama integration with multiple model support
- GitHub API client with pagination and rate limit handling
- Smart caching for offline re-use
- Noise/spam filtering
- 225+ unit tests

📚 **Documentation**
- Comprehensive README with quick start
- Detailed usage guide in [docs/USAGE.md](docs/USAGE.md)
- Complete environment variable reference
- Troubleshooting guide and advanced topics
- CI/CD integration examples

See [CHANGELOG.md](CHANGELOG.md) for complete details, technical specifications, and roadmap.

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

2. Edit `.env` and configure your settings (see table below for all options)

### Quick Configuration

**Minimal setup for public repository:**
```bash
IDEA_GEN_GITHUB_REPO=owner/repo
```

**With authentication (private repo or higher rate limits):**
```bash
IDEA_GEN_GITHUB_REPO=owner/repo
IDEA_GEN_GITHUB_TOKEN=<your_token_here>
```

**Custom model:**
```bash
IDEA_GEN_MODEL_INNOVATOR=llama3.2:3b  # Faster, lighter
```

### Environment Variable Reference

| Category | Variable | Default | Description | Required | Storage |
|----------|----------|---------|-------------|----------|---------|
| **GitHub** | `IDEA_GEN_GITHUB_REPO` | None | Repository to analyze (`owner/repo`) | For ingest/run | `.env` or CLI |
| | `IDEA_GEN_GITHUB_TOKEN` | None | Personal Access Token (PAT) | For private repos | `.env` only* |
| **Ollama** | `IDEA_GEN_OLLAMA_HOST` | `http://localhost` | Ollama server URL | No | `.env` or CLI |
| | `IDEA_GEN_OLLAMA_PORT` | `11434` | Ollama server port | No | `.env` or CLI |
| **Models** | `IDEA_GEN_MODEL_INNOVATOR` | `llama3.2:latest` | Model for summarization/grouping | No | `.env` or CLI |
| | `IDEA_GEN_MODEL_CRITIC` | `llama3.2:latest` | Model for critic persona (unused) | No | `.env` or CLI |
| **Directories** | `IDEA_GEN_OUTPUT_DIR` | `output` | Output directory for results | No | `.env` or CLI |
| | `IDEA_GEN_DATA_DIR` | `data` | Data directory for ingested issues | No | `.env` or CLI |
| | `IDEA_GEN_PERSONA_DIR` | `personas` | Persona metadata directory | No | `.env` or CLI |
| **Processing** | `IDEA_GEN_MAX_TEXT_LENGTH` | `8000` | Max chars for issue body + comments | No | `.env` |
| | `IDEA_GEN_SUMMARIZATION_MAX_TOKENS` | `4000` | Max tokens per issue for summarization | No | `.env` |
| | `IDEA_GEN_GROUPING_MAX_BATCH_SIZE` | `20` | Max summaries per grouping batch | No | `.env` |
| | `IDEA_GEN_GROUPING_MAX_BATCH_CHARS` | `50000` | Max chars per grouping batch | No | `.env` |
| **API** | `IDEA_GEN_GITHUB_PER_PAGE` | `100` | Items per GitHub API page (max: 100) | No | `.env` |
| | `IDEA_GEN_GITHUB_MAX_RETRIES` | `3` | Max retry attempts for GitHub API | No | `.env` |
| | `IDEA_GEN_LLM_TIMEOUT` | `120.0` | LLM request timeout (seconds) | No | `.env` |
| | `IDEA_GEN_LLM_MAX_RETRIES` | `3` | Max retry attempts for LLM requests | No | `.env` |
| **Ranking** | `IDEA_GEN_RANKING_WEIGHT_NOVELTY` | `0.25` | Weight for novelty metric | No | `.env` |
| | `IDEA_GEN_RANKING_WEIGHT_FEASIBILITY` | `0.25` | Weight for feasibility metric | No | `.env` |
| | `IDEA_GEN_RANKING_WEIGHT_DESIRABILITY` | `0.30` | Weight for desirability metric | No | `.env` |
| | `IDEA_GEN_RANKING_WEIGHT_ATTENTION` | `0.20` | Weight for attention metric | No | `.env` |
| | `IDEA_GEN_TOP_IDEAS_COUNT` | `10` | Number of ideas in Markdown report | No | `.env` |
| **Other** | `IDEA_GEN_NOISE_FILTER_ENABLED` | `true` | Enable noise/spam detection | No | `.env` |
| | `IDEA_GEN_CACHE_MAX_FILE_SIZE` | `1000000` | Max cache file size (bytes) | No | `.env` |

\* **Security Note**: Store tokens in `.env` file only (never commit to git). Avoid CLI arguments or shell exports as they may be exposed in logs and command history.

📚 **See [docs/USAGE.md](docs/USAGE.md)** for detailed descriptions of each variable and configuration examples.

### Getting a GitHub Token

For private repositories or to avoid rate limits:

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes:
   - **`public_repo`**: For public repositories (read-only) - provides 5000 requests/hour
   - **`repo`**: For private repositories (full access) - includes public_repo
4. Copy the token and add it to your `.env` file

⚠️ **Important**: Never commit `.env` files to version control. The `.gitignore` includes this by default.

**Token Scopes:**
- `public_repo`: Read-only access to public repositories, higher rate limits (5000/hour vs 60/hour)
- `repo`: Full access to public and private repositories (includes all repo permissions)

**Security**: Store tokens only in `.env` file. Avoid CLI arguments or shell exports as they appear in command history and process listings.

## Usage

The idea-generator follows a multi-stage pipeline. You can run each stage individually or use `run` to execute everything at once.

📚 **For detailed instructions, see [docs/USAGE.md](docs/USAGE.md)** - comprehensive guide with examples, troubleshooting, and advanced topics.

### Quick Command Reference

```bash
# Full pipeline (all stages)
idea-generator run --github-repo owner/repo

# Individual stages
idea-generator setup                    # 1. Prepare environment
idea-generator ingest -r owner/repo     # 2. Fetch issues
idea-generator summarize -r owner/repo  # 3. Generate summaries
idea-generator group -r owner/repo      # 4. Cluster issues
```

**All commands support `--help` for detailed options.**

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

### Step 4: Group Summarized Issues

```bash
idea-generator group --github-repo owner/repo
```

This command:
- ✓ Loads summarized issues from the output directory
- ✓ Groups summaries in batches through the grouper LLM persona
- ✓ Merges duplicate or highly similar issues into clusters
- ✓ Splits multi-topic issues when appropriate
- ✓ Preserves unique issues as singleton clusters
- ✓ Aggregates metrics deterministically (averages)
- ✓ Saves idea clusters to the output directory

**Options:**
- `--github-repo`, `-r`: GitHub repository in format 'owner/repo' (required)
- `--output-dir`, `-o`: Output directory (default: ./output)
- `--ollama-host`: Ollama server host (default: http://localhost)
- `--ollama-port`: Ollama server port (default: 11434)
- `--model-innovator`: Model to use for grouping (default: llama3.2:latest)
- `--skip-noise`: Skip summaries already flagged as noise
- `--max-batch-size`: Maximum summaries per batch (default: 20)
- `--max-batch-chars`: Maximum characters per batch (default: 50000)

**Examples:**

```bash
# Group summaries from a repository
idea-generator group --github-repo facebook/react

# Use custom batch limits
idea-generator group --github-repo owner/repo --max-batch-size 15 --max-batch-chars 40000

# Skip noise-flagged summaries
idea-generator group --github-repo owner/repo --skip-noise
```

**Grouper Persona Behavior:**

The grouper uses the same Ollama model as the summarizer but with a distinct system prompt optimized for clustering and deduplication. It analyzes batches of summarized issues to:

1. **Merge Duplicates**: Combines issues addressing the same core problem or feature
2. **Split Multi-Topic**: Separates issues that combine multiple distinct concerns
3. **Preserve Singletons**: Keeps unique issues as individual clusters
4. **Aggregate Metrics**: Calculates averages for novelty, feasibility, desirability, and attention

**Batching Strategy:**

Issues are processed in batches to respect LLM context limits:
- **Max Batch Size**: Controls the number of summaries per request (default: 20)
- **Max Batch Chars**: Controls the character count per request (default: 50000)
- **Deterministic Ordering**: Issues are processed in consistent order across runs
- **Cursor State**: Pipeline tracks progress through batches automatically

**Validation and Post-Processing:**

The pipeline validates every cluster to ensure:
- All referenced issue IDs exist in the input batch
- No issue appears in multiple clusters
- All input issues are covered by exactly one cluster
- Metrics are aggregated deterministically using averages

**Model Reuse:**

The grouper reuses the same Ollama model weights as the summarizer (default: `llama3.2:latest`) but with a different system prompt. This means:
- No additional model download required
- Consistent model behavior across personas
- Different prompts produce different analysis styles
- Prompts are stored in version control for transparency

**Output Format:**

Clusters are saved to `output/owner_repo_clusters.json`:

```json
[
  {
    "cluster_id": "ui-ux-001",
    "representative_title": "Theme customization support",
    "summary": "Users request dark mode and theme switching for visual customization.",
    "topic_area": "UI/UX",
    "member_issue_ids": [100, 101],
    "novelty": 0.35,
    "feasibility": 0.75,
    "desirability": 0.88,
    "attention": 0.65
  }
]
```

**Edge Cases Handled:**

- **Large Datasets**: Automatically splits into multiple batches without losing ordering
- **Overlapping Assignments**: Resolves deterministically (smallest cluster_id wins)
- **Unknown Issue IDs**: Forces retry or drops cluster with logged diagnostics
- **No Overlaps**: Emits singleton clusters mirroring original summaries
- **Validation Failures**: Retries once automatically before failing

**Important Notes:**

⚠️ **LLM Execution**: This command requires a running Ollama server. Ensure Ollama is running:

```bash
# Start Ollama server
ollama serve

# Verify model is available
ollama list | grep llama3.2
```

⚠️ **Processing Time**: Grouping is faster than summarization due to batching but can still take several minutes for large datasets. Progress is logged per batch.

⚠️ **Batch Processing**: Unlike summarization, grouping uses batches to process multiple issues simultaneously within context limits.

### Step 5: Rank and Generate Reports

```bash
idea-generator run --github-repo owner/repo
```

This command orchestrates the complete end-to-end pipeline:
1. **Ingest** issues from GitHub (or reuse cached data)
2. **Summarize** issues with LLM (or reuse cached summaries)
3. **Group** summaries into clusters (or reuse cached clusters)
4. **Rank** clusters by composite score with deterministic tie-breaking
5. **Generate** JSON and Markdown reports in `output/reports/`

📊 **Output Reports:**

The pipeline generates two complementary reports:

**1. `output/reports/ideas.json`** - Machine-readable complete dataset
```json
{
  "clusters": [
    {
      "cluster_id": "ui-ux-001",
      "title": "Theme customization and dark mode",
      "summary": "Users request dark mode and theme switching...",
      "topic_area": "UI/UX",
      "metrics": {
        "novelty": 0.35,
        "feasibility": 0.75,
        "desirability": 0.88,
        "attention": 0.65,
        "composite_score": 0.67
      },
      "member_issues": [42, 89, 103],
      "source_urls": ["https://github.com/..."]
    }
  ],
  "metadata": {
    "total_clusters": 48,
    "repository": "owner/repo",
    "generated_at": "2025-12-05T23:30:00Z"
  }
}
```

**2. `output/reports/top-ideas.md`** - Human-readable summary
```markdown
# Top 10 Ideas for owner/repo

## 🔥 #1: Theme customization and dark mode
**Score: 0.67** | 📊 Novelty: 0.35 | ⚙️ Feasibility: 0.75 | ⭐ Desirability: 0.88 | 👥 Attention: 0.65

Users request dark mode and theme switching capabilities...

**Topic**: UI/UX | **Priority**: High
**Source Issues**: #42, #89, #103
```

**Options:**
- `--github-repo`, `-r`: GitHub repository in format 'owner/repo' (required)
- `--github-token`, `-t`: GitHub API token (optional)
- `--output-dir`, `-o`: Output directory (default: ./output)
- `--data-dir`, `-d`: Data directory (default: ./data)
- `--ollama-host`: Ollama server host (default: http://localhost)
- `--ollama-port`: Ollama server port (default: 11434)
- `--model-innovator`: Model for LLM operations (default: llama3.2:latest)
- `--force`: Regenerate all artifacts, skip cached data
- `--skip-json`: Skip JSON report generation
- `--skip-markdown`: Skip Markdown report generation
- `--top-ideas`: Number of top ideas in Markdown report (default: 10)

**Examples:**

```bash
# Full pipeline with default settings
idea-generator run --github-repo facebook/react

# Force regeneration (ignore cache)
idea-generator run --github-repo owner/repo --force

# Generate only JSON report
idea-generator run --github-repo owner/repo --skip-markdown

# Custom top N ideas in Markdown
idea-generator run --github-repo owner/repo --top-ideas 15

# JSON-only mode (automation-friendly)
idea-generator run --github-repo owner/repo --skip-markdown
```

**Caching and Resumption:**

The pipeline caches intermediate artifacts to enable resumption after failures:
- `data/owner_repo_issues.json`: Normalized issues from GitHub
- `output/owner_repo_summaries.json`: LLM-generated summaries
- `output/owner_repo_clusters.json`: Grouped idea clusters
- `output/summarization_cache/`: Individual summary cache files

By default, the pipeline reuses cached artifacts if they exist. Use `--force` to regenerate everything from scratch.

**Output Reports:**

Two reports are generated in `output/reports/`:

1. **ideas.json**: Complete dataset with all clusters, including:
   - Normalized metrics (novelty, feasibility, desirability, attention)
   - Composite scores (weighted combination of metrics)
   - Noise indicators (flagged from source issues)
   - Source issue URLs for traceability

2. **top-ideas.md**: Human-readable report with top N ranked clusters, including:
   - Cluster summaries and topic areas
   - Metric breakdowns with visual indicators
   - Priority tags (🔥 Critical, ⭐ High, ✅ Medium, 💡 Low)
   - Links to source GitHub issues

**Scoring and Ranking:**

Ideas are ranked using a weighted composite score:

```
composite_score = (novelty × w_n) + (feasibility × w_f) + 
                  (desirability × w_d) + (attention × w_a)
```

Default weights (configurable via environment variables):
- **Novelty**: 0.25 (how innovative or unique the idea is)
- **Feasibility**: 0.25 (how practical to implement)
- **Desirability**: 0.30 (how valuable to users/stakeholders)
- **Attention**: 0.20 (community engagement level)

Tie-breaking is deterministic:
1. Primary: Composite score (descending)
2. Secondary: Desirability (descending)
3. Tertiary: Feasibility (descending)
4. Final: Title (ascending alphabetically)

**Customizing Weights:**

Override default weights in `.env`:

```bash
# Emphasize desirability and feasibility
IDEA_GEN_RANKING_WEIGHT_NOVELTY=0.15
IDEA_GEN_RANKING_WEIGHT_FEASIBILITY=0.35
IDEA_GEN_RANKING_WEIGHT_DESIRABILITY=0.40
IDEA_GEN_RANKING_WEIGHT_ATTENTION=0.10

# How many top ideas to include in Markdown report
IDEA_GEN_TOP_IDEAS_COUNT=20
```

Weights must sum to 1.0 (±0.01 tolerance). The pipeline validates this at runtime.

**Edge Cases Handled:**

- **No open issues**: Generates empty JSON array and friendly Markdown message without errors
- **Score ties**: Resolved deterministically using desirability, feasibility, and title for consistent ordering
- **Missing artifacts**: Pipeline automatically detects missing cached files and regenerates them
- **Partial failures**: If a stage fails, cached artifacts from previous stages remain intact for debugging

**Important Notes:**

⚠️ **LLM Execution**: This command requires a running Ollama server for the summarization and grouping stages. Ensure Ollama is running:

```bash
# Start Ollama server
ollama serve

# Verify model is available
ollama list | grep llama3.2
```

⚠️ **Processing Time**: The full pipeline can take several minutes for large repositories:
- Ingestion: ~1-2 seconds per 100 issues
- Summarization: ~1-2 seconds per issue (sequential processing)
- Grouping: ~5-10 seconds per batch of 20 issues
- Ranking and reports: <1 second

Progress is logged in real-time with stage-by-stage updates.

⚠️ **Token Budget**: Ensure your GitHub token (if using a private repo) has sufficient API rate limit quota. The pipeline makes multiple API calls during ingestion.

## Project Structure

```
idea-generator/
├── idea_generator/           # Main package directory
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # CLI interface (Typer commands)
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models (NormalizedIssue, SummarizedIssue, IdeaCluster)
│   ├── setup.py             # Setup workflow and Ollama integration
│   ├── cleaning.py          # Issue cleaning and normalization
│   ├── filters.py           # Scoring and ranking utilities
│   ├── output.py            # JSON and Markdown report generation
│   ├── github_client.py     # GitHub API client with caching
│   ├── llm/                 # LLM integration components
│   │   ├── __init__.py     # LLM module initialization
│   │   ├── client.py        # Ollama HTTP client wrapper
│   │   └── prompts/         # LLM persona prompts
│   │       ├── summarizer.txt  # Summarizer persona system prompt
│   │       └── grouper.txt     # Grouper persona system prompt
│   └── pipelines/           # Processing pipelines
│       ├── __init__.py     # Pipeline module initialization
│       ├── summarize.py     # Summarization pipeline
│       ├── grouping.py      # Grouping/clustering pipeline
│       └── orchestrator.py  # End-to-end pipeline orchestration
├── tests/                   # Test suite
│   ├── test_config.py       # Configuration tests
│   ├── test_models.py       # Model validation tests
│   ├── test_setup.py        # Setup workflow tests
│   ├── test_cleaning.py     # Data cleaning tests
│   ├── test_filters.py      # Scoring and ranking tests
│   ├── test_output.py       # Report generation tests
│   ├── test_orchestrator.py # Orchestration pipeline tests
│   ├── test_github_client.py # GitHub API client tests
│   ├── test_llm_client.py   # LLM client tests
│   ├── test_summarize_pipeline.py  # Summarization pipeline tests
│   ├── test_grouping_pipeline.py   # Grouping pipeline tests
│   ├── test_integration.py  # End-to-end integration tests
│   └── test_cli.py          # CLI integration tests
├── output/                  # Generated ideas and reports (created by setup)
│   └── reports/             # Final JSON and Markdown reports
│       ├── ideas.json       # Complete dataset with all clusters
│       └── top-ideas.md     # Human-readable top N ideas
├── data/                    # Ingested repository data (created by setup)
├── personas/                # Persona metadata and prompts (created by setup)
├── pyproject.toml          # Package configuration and dependencies
├── .env.example            # Example environment variables
├── .gitignore              # Git ignore patterns
└── README.md               # This file
```

## Troubleshooting

### Quick Fixes

**Ollama Not Found**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Verify
ollama --version
```

**Ollama Server Not Running**
```bash
# Start in separate terminal
ollama serve

# Or in background
nohup ollama serve > /tmp/ollama.log 2>&1 &
```

**Model Download Fails**
```bash
# Try smaller model first
ollama pull llama3.2:3b

# For air-gapped: copy ~/.ollama/models from another machine
```

**GitHub API Rate Limit**
```bash
# Create token at https://github.com/settings/tokens
# Add to .env:
IDEA_GEN_GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Provides 5000 requests/hour (vs 60 without token)
```

**Out of Memory (LLM)**
```bash
# Use smaller model
IDEA_GEN_MODEL_INNOVATOR=llama3.2:3b

# Or reduce batch sizes
IDEA_GEN_GROUPING_MAX_BATCH_SIZE=10
```

**Permission Denied**
```bash
# Use custom directories
idea-generator setup --output-dir ~/my-output --data-dir ~/my-data

# Or fix permissions
chmod u+w .
```

📚 **For more help, see [docs/USAGE.md#troubleshooting](docs/USAGE.md#troubleshooting)** - comprehensive troubleshooting guide with 10+ common issues and solutions.

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

# Generate HTML coverage report
pytest --cov=idea_generator --cov-report=html
open htmlcov/index.html
```

### Code Quality

```bash
# Format code with Black
black idea_generator tests

# Lint with Ruff
ruff check idea_generator tests

# Fix linting issues automatically
ruff check --fix idea_generator tests

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

Then reinstall:

```bash
pip install -e ".[dev]"
```

### Project Structure

```
idea-generator/
├── idea_generator/           # Main package
│   ├── cli.py               # CLI interface (Typer commands)
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models
│   ├── setup.py             # Setup workflow
│   ├── cleaning.py          # Data cleaning
│   ├── filters.py           # Scoring and ranking
│   ├── output.py            # Report generation
│   ├── github_client.py     # GitHub API client
│   ├── llm/                 # LLM integration
│   │   ├── client.py        # Ollama client
│   │   └── prompts/         # Persona prompts
│   └── pipelines/           # Processing pipelines
│       ├── summarize.py     # Summarization
│       ├── grouping.py      # Clustering
│       └── orchestrator.py  # Orchestration
├── tests/                   # Test suite (225+ tests)
├── docs/                    # Documentation
│   └── USAGE.md            # Detailed usage guide
├── output/                  # Generated output (created by setup)
├── data/                    # Ingested data (created by setup)
├── pyproject.toml          # Package configuration
├── .env.example            # Environment template
├── CHANGELOG.md            # Version history
└── README.md               # This file
```

## Documentation

### Available Documentation

- **[README.md](README.md)** (this file): Quick start, architecture overview, command reference
- **[docs/USAGE.md](docs/USAGE.md)**: Comprehensive usage guide with detailed instructions
  - Prerequisites and installation
  - Configuration reference
  - Step-by-step workflow
  - Complete command reference
  - Troubleshooting (10+ scenarios)
  - Advanced topics (offline use, performance tuning, CI/CD integration)
- **[CHANGELOG.md](CHANGELOG.md)**: Version history, features, breaking changes, roadmap
- **[.env.example](.env.example)**: Annotated configuration template

### Documentation Topics

**Getting Started**
- [Quick Start](#quick-start) - 5-minute setup
- [Installation](docs/USAGE.md#installation) - Detailed setup steps
- [Configuration](docs/USAGE.md#configuration) - Environment variables

**Using the Tool**
- [Usage Workflow](docs/USAGE.md#usage-workflow) - Stage-by-stage guide
- [Command Reference](docs/USAGE.md#command-reference) - All CLI commands with examples
- [Troubleshooting](docs/USAGE.md#troubleshooting) - Common issues and solutions

**Advanced**
- [Architecture](#architecture) - System design and data flow
- [Performance Tuning](docs/USAGE.md#performance-tuning) - Optimization strategies
- [Offline Use](docs/USAGE.md#offline--air-gapped-environments) - Air-gapped deployment
- [CI/CD Integration](docs/USAGE.md#cicd-integration) - Automation examples

**Reference**
- [Environment Variables](#environment-variable-reference) - Configuration table
- [Project Structure](#project-structure) - Code organization
- [Version History](CHANGELOG.md) - Changes and roadmap



# Permanents (License, Contributing, Author)

Do not change any of the below sections

## License

This Agent Foundry Project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Contributing

Feel free to submit issues and enhancement requests!

## Author

Created by Agent Foundry and John Brosnihan
