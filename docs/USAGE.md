# Idea Generator - Detailed Usage Guide

This guide provides comprehensive instructions for setting up and using the idea-generator CLI tool to analyze GitHub repositories and generate actionable insights using local LLM models.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage Workflow](#usage-workflow)
5. [Command Reference](#command-reference)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Topics](#advanced-topics)

## Prerequisites

### System Requirements

Before installing idea-generator, ensure your system meets these requirements:

- **Operating System**: Linux, macOS, or Windows with WSL2
- **Python**: Version 3.11 or later (verify with `python --version`)
- **RAM**: Minimum 8GB (16GB+ recommended for optimal performance)
- **Disk Space**: At least 10GB free space for model downloads
- **Network**: Internet connection required for initial setup and model downloads

### Required Software

#### 1. Python 3.11+

**Check if installed:**
```bash
python --version
# or
python3 --version
```

**Installation:**
- **macOS**: `brew install python@3.11`
- **Ubuntu/Debian**: `sudo apt install python3.11 python3.11-venv`
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

#### 2. Ollama

Ollama is the local LLM runtime that powers the idea-generator's AI capabilities.

**Check if installed:**
```bash
ollama --version
```

**Installation:**
- **macOS/Linux**: Visit [ollama.ai/download](https://ollama.ai/download) and follow platform-specific instructions
- **Windows**: Use WSL2 and follow Linux instructions

**Start the Ollama server:**
```bash
ollama serve
```

Keep this running in a separate terminal while using idea-generator.

**Verify server is running:**
```bash
curl http://localhost:11434/api/version
```

You should see a JSON response with the Ollama version.

### Optional: GitHub Personal Access Token

A GitHub token is **required** for:
- Analyzing private repositories
- Avoiding GitHub API rate limits (60 requests/hour without token, 5000 with token)

A token is **optional** for:
- Analyzing public repositories (unless you need higher rate limits)

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/AgentFoundryExamples/idea-generator.git
cd idea-generator
```

### Step 2: Create Virtual Environment

It's strongly recommended to use a virtual environment:

```bash
python -m venv .venv

# Activate on Linux/macOS:
source .venv/bin/activate

# Activate on Windows:
.venv\Scripts\activate
```

### Step 3: Install Dependencies

**For production use:**
```bash
pip install -e .
```

**For development (includes testing tools):**
```bash
pip install -e ".[dev]"
```

### Step 4: Verify Installation

```bash
idea-generator --help
```

If you see the help output listing available commands, installation was successful!

## Configuration

### Schema Contract

The idea-generator enforces strict schema adherence through carefully designed LLM prompts and Pydantic data models. This ensures consistent, reliable output from smaller LLMs even as context windows grow.

#### Why Schema Enforcement Matters

Small local LLMs (1B-8B parameters) can drift when processing large batches, producing:
- Malformed JSON (missing commas, unclosed brackets)
- Extra fields not in the schema
- Missing required fields
- Invalid metric ranges
- Incorrect data types

Our approach prevents drift through:
1. **Explicit schema reminders** in every prompt
2. **Minimal success examples** showing exact format
3. **Pydantic validation** catching errors early
4. **Refusal guidance** when LLM is uncertain

#### Data Models

The pipeline uses three core Pydantic models with strict validation:

**1. SummarizedIssue (Summarizer Output)**
```python
{
  "issue_id": int,              # GitHub issue ID
  "source_number": int,         # Issue number in repo
  "title": str,                 # Max 100 characters
  "summary": str,               # 2-3 sentences, no newlines
  "topic_area": str,            # e.g., "UI/UX", "security"
  "novelty": float,             # 0.0-1.0, how innovative
  "feasibility": float,         # 0.0-1.0, how practical
  "desirability": float,        # 0.0-1.0, how valuable
  "attention": float,           # 0.0-1.0, engagement level
  "noise_flag": bool,           # true if spam/low-quality
  "raw_issue_url": str          # GitHub URL
}
```

**Validation Rules:**
- `title`: Auto-truncated to 100 chars
- `summary`: Cannot be empty or whitespace-only
- Metrics: Must be floats in range [0.0, 1.0]
- All fields required, no nulls allowed

**2. IdeaCluster (Grouper Output)**
```python
{
  "cluster_id": str,            # Format: "topic-001"
  "representative_title": str,  # Max 100 chars
  "summary": str,               # Condensed, no newlines
  "topic_area": str,            # Primary topic
  "member_issue_ids": [int],    # At least 1, no duplicates
  "novelty": float,             # 0.0-1.0, averaged
  "feasibility": float,         # 0.0-1.0, averaged
  "desirability": float,        # 0.0-1.0, averaged
  "attention": float            # 0.0-1.0, averaged
}
```

**Validation Rules:**
- `cluster_id`: Cannot be empty/whitespace
- `representative_title`: Max 100 chars
- `member_issue_ids`: Must have at least 1, all unique
- Metrics: Averaged across members, rounded to 2 decimals

#### Prompt Design Principles

Both `summarizer.txt` and `grouper.txt` follow these design principles:

1. **Explicit Schema Section**
   - Lists all required fields with types
   - Shows exact JSON structure
   - Warns against extra fields

2. **Minimal Success Example**
   - Shows one perfect output
   - Annotated with reminders
   - Demonstrates proper formatting

3. **Text Normalization Rules**
   - Replace newlines with spaces
   - No tabs or control characters
   - Single spaces, no multiples

4. **Refusal Guidance**
   - "Refuse if unsure" instruction
   - Better to fail fast than return garbage
   - Retry logic handles transient errors

5. **Concise Language**
   - Optimized for small LLM context windows
   - No redundant explanations
   - Clear, imperative instructions

#### Schema Evolution

When modifying schemas:

1. **Update Pydantic Models** (`idea_generator/models.py`)
   - Add field with proper type hints
   - Include Pydantic validators if needed
   - Update docstrings

2. **Update Prompt Templates** (`idea_generator/llm/prompts/*.txt`)
   - Add field to "Required JSON Schema" section
   - Update example output
   - Add validation notes if complex

3. **Add Regression Tests** (`tests/test_*_pipeline.py`)
   - Verify prompt contains new field name
   - Test Pydantic validation catches invalid values
   - Test parsing handles new field

4. **Update Documentation** (this file, README.md)
   - Explain new field's purpose
   - Show updated examples
   - Note any breaking changes

#### Common Pitfalls

**Newline Handling**
- Issue: LLMs may include `\n` in summaries
- Solution: Prompts explicitly say "no newlines, replace with spaces"
- Fallback: Pipeline can strip/replace if needed

**Extra Fields**
- Issue: LLM adds creative fields like "priority" or "tags"
- Solution: Prompts warn "Do NOT add extra fields"
- Fallback: Pydantic ignores unknowns with `model_validate(data, strict=False)`

**Metric Ranges**
- Issue: LLM outputs 1.2 or -0.1 for metrics
- Solution: Prompts show "0.0-1.0" range repeatedly
- Fallback: Pydantic validators raise errors on invalid range

**Missing Fields**
- Issue: LLM omits optional-looking fields
- Solution: Prompts list "All fields are REQUIRED"
- Fallback: Parser raises `SummarizationError` or `GroupingError`

### Environment Variables

The idea-generator can be configured using:
1. Environment variables set in your shell
2. A `.env` file in the project root directory
3. Command-line arguments (override all other sources)

#### Creating Your .env File

Copy the example file:
```bash
cp .env.example .env
```

Edit `.env` with your preferred text editor:
```bash
nano .env  # or vim, code, etc.
```

#### Environment Variable Reference

| Variable | Required | Default | Description | Storage |
|----------|----------|---------|-------------|---------|
| **GitHub Configuration** |
| `IDEA_GEN_GITHUB_REPO` | No* | None | Repository to analyze (format: `owner/repo`) | `.env` or CLI |
| `IDEA_GEN_GITHUB_TOKEN` | No† | None | GitHub Personal Access Token | `.env` recommended‡ |
| **Ollama Configuration** |
| `IDEA_GEN_OLLAMA_HOST` | No | `http://localhost` | Ollama server host URL | `.env` or CLI |
| `IDEA_GEN_OLLAMA_PORT` | No | `11434` | Ollama server port | `.env` or CLI |
| **Model Selection** |
| `IDEA_GEN_MODEL_INNOVATOR` | No | `llama3.2:latest` | Model for innovator persona (summarization & grouping) | `.env` or CLI |
| `IDEA_GEN_MODEL_CRITIC` | No | `llama3.2:latest` | Model for critic persona (currently unused) | `.env` or CLI |
| **Directory Configuration** |
| `IDEA_GEN_OUTPUT_DIR` | No | `output` | Directory for generated output files | `.env` or CLI |
| `IDEA_GEN_DATA_DIR` | No | `data` | Directory for ingested data | `.env` or CLI |
| `IDEA_GEN_PERSONA_DIR` | No | `personas` | Directory for persona metadata | `.env` or CLI |
| **Processing Configuration** |
| `IDEA_GEN_BATCH_SIZE` | No | `10` | Items to process in a batch (legacy, not actively used) | `.env` |
| `IDEA_GEN_MAX_WORKERS` | No | `4` | Maximum concurrent workers (legacy, not actively used) | `.env` |
| **GitHub API Configuration** |
| `IDEA_GEN_GITHUB_PER_PAGE` | No | `100` | Items per page for GitHub API requests (max: 100) | `.env` |
| `IDEA_GEN_GITHUB_MAX_RETRIES` | No | `3` | Maximum retry attempts for failed API requests | `.env` |
| `IDEA_GEN_GITHUB_ISSUE_LIMIT` | No | `None` | Maximum number of issues to ingest per repository (None for no limit). Use for large repositories to focus on most recently updated issues. | `.env` or CLI |
| **Text Processing** |
| `IDEA_GEN_MAX_TEXT_LENGTH` | No | `8000` | Maximum combined length of issue body + comments (chars) | `.env` |
| **Filtering Configuration** |
| `IDEA_GEN_NOISE_FILTER_ENABLED` | No | `true` | Enable automatic noise/spam detection | `.env` |
| `IDEA_GEN_SUPPORT_FILTER_ENABLED` | No | `true` | Enable support ticket/question filtering | `.env` |
| **LLM Configuration** |
| `IDEA_GEN_LLM_TIMEOUT` | No | `120.0` | LLM request timeout in seconds | `.env` |
| `IDEA_GEN_LLM_MAX_RETRIES` | No | `3` | Maximum retry attempts for failed LLM requests | `.env` |
| `IDEA_GEN_SUMMARIZATION_MAX_TOKENS` | No | `4000` | Maximum tokens per issue for summarization | `.env` |
| `IDEA_GEN_CACHE_MAX_FILE_SIZE` | No | `1000000` | Maximum cache file size in bytes (1MB) | `.env` |
| **Grouping Configuration** |
| `IDEA_GEN_GROUPING_MAX_BATCH_SIZE` | No | `20` | Maximum summaries per grouping batch | `.env` |
| `IDEA_GEN_GROUPING_MAX_BATCH_CHARS` | No | `50000` | Maximum characters per grouping batch | `.env` |
| **Ranking Configuration** |
| `IDEA_GEN_RANKING_WEIGHT_NOVELTY` | No | `0.25` | Weight for novelty metric (how innovative) | `.env` |
| `IDEA_GEN_RANKING_WEIGHT_FEASIBILITY` | No | `0.25` | Weight for feasibility metric (how practical) | `.env` |
| `IDEA_GEN_RANKING_WEIGHT_DESIRABILITY` | No | `0.30` | Weight for desirability metric (how valuable) | `.env` |
| `IDEA_GEN_RANKING_WEIGHT_ATTENTION` | No | `0.20` | Weight for attention metric (community engagement) | `.env` |
| `IDEA_GEN_TOP_IDEAS_COUNT` | No | `10` | Number of top ideas in Markdown report | `.env` |

**Notes:**
- \* Required when using commands that need a repository (ingest, summarize, group, run)
- † Required for private repositories or to avoid rate limits on public repositories
- ‡ **Security**: Store tokens in `.env` file (never committed to git) rather than shell exports or CLI arguments to avoid exposure in logs and command history

**Storage Guidelines:**
- **`.env` file**: Recommended for all configuration, especially sensitive data like tokens. Never commit to version control.
- **CLI arguments**: Temporary overrides for testing. Avoid using for tokens as they appear in shell history and process listings.
- **Shell exports**: Can be used but tokens may persist in shell history. Clear history after use if storing tokens this way.

**Important:** Ranking weights must sum to 1.0 (within ±0.01 tolerance). The pipeline validates this at runtime.

### GitHub Personal Access Token Setup

#### Creating a Token

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a descriptive name (e.g., "idea-generator")
4. Set expiration (90 days recommended for security)
5. Select scopes:
   - **For public repositories**: `public_repo`
   - **For private repositories**: `repo` (includes all repo permissions)
6. Click "Generate token"
7. **Copy the token immediately** - you won't be able to see it again!

#### Token Scope Details

| Scope | Access Level | Use Case |
|-------|-------------|----------|
| `public_repo` | Read-only access to public repositories | Sufficient for analyzing public repos; provides higher rate limits (5000/hour vs 60/hour) |
| `repo` | Full access to public and private repositories | Required for private repos; includes read/write access to code, issues, and PRs |

#### Storing Your Token Securely

**Option 1: In .env file (recommended)**
```bash
IDEA_GEN_GITHUB_TOKEN=<your_token_here>
```

**Option 2: Environment variable**
```bash
export IDEA_GEN_GITHUB_TOKEN=<your_token_here>
```

**Option 3: Command-line argument (not recommended for security)**
```bash
idea-generator ingest --github-repo owner/repo --github-token <your_token_here>
```

⚠️ **Security Best Practices:**
- Never commit `.env` files to version control (included in `.gitignore`)
- Use tokens with minimal necessary permissions
- Set expiration dates on tokens
- Rotate tokens regularly
- Consider using environment-specific tokens (dev vs production)
- **Avoid passing tokens via CLI arguments** - they appear in shell history and process listings
- Store tokens in `.env` file or use secure secret management tools

### Ollama Model Configuration

#### Recommended Models

The idea-generator works best with 3-8B parameter models:

| Model | Size | RAM Required | Speed | Quality | Best For |
|-------|------|--------------|-------|---------|----------|
| `llama3.2:1b` | ~1GB | 4GB | Very Fast | Good | Quick testing, low-end hardware |
| `llama3.2:3b` | ~2GB | 6GB | Fast | Better | Balanced performance |
| `llama3.2:latest` (8B) | ~5GB | 10GB | Moderate | Best | Recommended default |
| `llama3.1:8b` | ~5GB | 10GB | Moderate | Best | Alternative to 3.2 |
| `llama3.2:70b` | ~40GB | 64GB | Slow | Excellent | High-end systems only |

#### Pulling Models

Before first use, pull the required models:

```bash
# Default recommended model
ollama pull llama3.2:latest

# For faster/lighter processing
ollama pull llama3.2:3b

# For best quality (high-end hardware)
ollama pull llama3.2:70b
```

#### Using Different Models

You can use different models for different personas:

```bash
# In .env file
IDEA_GEN_MODEL_INNOVATOR=llama3.2:8b
IDEA_GEN_MODEL_CRITIC=llama3.2:3b

# Or via command-line
idea-generator setup --model-innovator llama3.2:8b --model-critic llama3.2:3b
```

#### Model Selection Guidelines

**For laptops/limited hardware:**
- Use `llama3.2:3b` or `llama3.2:1b`
- Expect slightly lower quality summaries
- Processing will be faster

**For workstations:**
- Use `llama3.2:latest` (8B) - recommended default
- Good balance of quality and performance

**For servers/high-end systems:**
- Use `llama3.2:70b` or `llama3.1:70b`
- Best quality summaries
- Processing will be significantly slower

## Usage Workflow

The idea-generator follows a multi-stage pipeline:

```
1. Setup      → Install models and create directories
2. Ingest     → Fetch issues from GitHub
3. Summarize  → Generate AI summaries of each issue
4. Group      → Cluster similar issues together
5. Run        → Rank and generate reports
```

You can run each stage individually or use `run` to execute the entire pipeline.

### Stage 1: Setup

**Purpose:** Prepare your environment for first-time use.

**Command:**
```bash
idea-generator setup
```

**What it does:**
- ✓ Verifies Ollama is installed and accessible
- ✓ Connects to the Ollama server at configured host/port
- ✓ Pulls required models (innovator and critic personas)
- ✓ Creates necessary directories (`output/`, `data/`, `personas/`)
- ✓ Saves persona metadata and system prompts

**Available options:**
```bash
# Skip model pulling (if already installed)
idea-generator setup --skip-pull

# Offline mode (no network operations)
idea-generator setup --offline

# Use specific models
idea-generator setup \
  --model-innovator llama3.2:8b \
  --model-critic llama3.2:3b

# Custom Ollama server
idea-generator setup \
  --ollama-host http://192.168.1.100 \
  --ollama-port 11434
```

**When to run:**
- First time using the tool
- After changing models
- After cleaning/resetting directories
- When switching between different Ollama servers

**Expected output:**
```
Checking Ollama installation...
✓ Ollama binary found

Connecting to Ollama server at http://localhost:11434...
✓ Connected successfully

Pulling model: llama3.2:latest
⠋ Downloading... (this may take several minutes)
✓ Model pulled successfully

Creating directories...
✓ Created: ./output
✓ Created: ./data
✓ Created: ./personas

Saving persona metadata...
✓ Persona metadata saved

Setup complete! You're ready to use idea-generator.
```

### Stage 2: Ingest

**Purpose:** Fetch and normalize issues from a GitHub repository.

**Command:**
```bash
idea-generator ingest --github-repo owner/repo
```

**What it does:**
- ✓ Validates repository access
- ✓ Fetches all open issues with pagination
- ✓ Retrieves comment threads for each issue
- ✓ Normalizes and cleans the data (strips markdown noise)
- ✓ Deduplicates comments
- ✓ Applies noise/spam filtering
- ✓ Truncates text to fit within token limits
- ✓ Caches raw API responses for offline re-use
- ✓ Saves normalized JSON to data directory

**Available options:**
```bash
# Basic usage with repository
idea-generator ingest --github-repo facebook/react

# With authentication token (stored in .env recommended)
idea-generator ingest \
  --github-repo myorg/private-repo

# Custom data directory
idea-generator ingest \
  --github-repo owner/repo \
  --data-dir /custom/data/path
```

**Input:** GitHub repository identifier (`owner/repo`)

**Output:** `data/owner_repo_issues.json` containing normalized issues

**Example output structure:**
```json
[
  {
    "id": 123456789,
    "number": 42,
    "title": "Add dark mode support",
    "body": "Users are requesting a dark theme option...",
    "labels": ["enhancement", "ui"],
    "state": "open",
    "reactions": {"+1": 12, "heart": 3, "hooray": 1},
    "comments": [
      {
        "id": 987654321,
        "author": "contributor_name",
        "body": "I'd be happy to work on this...",
        "created_at": "2025-01-15T10:30:00+00:00",
        "reactions": {"+1": 5}
      }
    ],
    "url": "https://github.com/owner/repo/issues/42",
    "created_at": "2025-01-10T08:00:00+00:00",
    "updated_at": "2025-01-15T10:30:00+00:00",
    "is_noise": false,
    "noise_reason": null,
    "truncated": false,
    "original_length": 856
  }
]
```

**Performance considerations:**
- **Pagination**: Automatically handles large repositories with many issues
- **Rate limiting**: Implements exponential backoff when rate limits are hit
- **Caching**: Raw responses cached in `data/cache/` for debugging and offline re-use

**Expected output:**
```
Ingesting issues from facebook/react...
Data directory: ./data

Checking repository access...
✓ Repository accessible

Fetching open issues...
✓ Found 127 open issues

Processing issues and comments...
  [1/127] Issue #28450... ✓
  [2/127] Issue #28448... ✓
  [3/127] Issue #28447... ✓
  ...
  [127/127] Issue #28001... ✓

Summary:
  Total issues: 127
  Noise flagged: 3
  Truncated: 12

Saved normalized issues to: data/facebook_react_issues.json
```

#### Filtering Configuration

The ingestion stage applies two types of filters to identify low-signal issues:

**1. Basic Noise/Spam Detection** (always enabled when `IDEA_GEN_NOISE_FILTER_ENABLED=true`):
- **Non-actionable labels**: spam, invalid, wontfix, duplicate, off-topic, declined, stale
- **Bot authors**: dependabot, renovate, and other automated contributors
- **Low-quality content**: Single-word titles, empty or very short bodies (< 10 chars)
- **Spam patterns**: Common test messages like "test", "testing", "hello", "hi", "hey"

**2. Support Ticket/Question Detection** (configurable via `IDEA_GEN_SUPPORT_FILTER_ENABLED`):

Enabled by default to filter out support requests and questions that aren't feature requests or bug reports:

- **Support labels**: support, question, help wanted, needs help, how-to, usage, discussion
- **Question keywords** (case-insensitive, in title or body):
  - "how do I", "how can I", "how to"
  - "what is the", "what are the"
  - "where do I", "where can I"
  - "why is", "why doesn't"
  - "need help", "can someone help"
  - "cannot figure out", "cannot understand"

**Configuration:**

```bash
# In .env file
IDEA_GEN_NOISE_FILTER_ENABLED=true         # Enable basic noise/spam detection
IDEA_GEN_SUPPORT_FILTER_ENABLED=true       # Enable support ticket filtering
```

**Disabling filters:**

```bash
# Disable support ticket filtering if your project uses "question" for valid issues
IDEA_GEN_SUPPORT_FILTER_ENABLED=false

# Disable all filtering (not recommended)
IDEA_GEN_NOISE_FILTER_ENABLED=false
IDEA_GEN_SUPPORT_FILTER_ENABLED=false
```

**Important Caveats:**

- **Over-filtering**: Legitimate feature requests phrased as questions may be flagged
  - Example: "How can we improve authentication?" might be flagged
  - Mitigation: Disable support filtering or review flagged issues manually
  
- **Label repurposing**: Projects that use "question" for valid work items should disable support filtering

- **Language limitations**: Keyword matching is English-centric and may not work for non-English repositories

- **Deterministic only**: All filtering is rule-based without LLM inference for consistency and explainability

**What happens to filtered issues:**

Filtered issues are NOT removed from the data. They are:
1. Included in `data/owner_repo_issues.json` with `is_noise: true`
2. Tagged with a `noise_reason` field explaining why they were flagged
3. Can be skipped in later stages using the `--skip-noise` flag
4. Still available for manual review if needed

**Monitoring filtered issues:**

```bash
# Check how many issues were flagged
jq '[.[] | select(.is_noise == true)] | length' data/owner_repo_issues.json

# View reasons for filtering
jq '[.[] | select(.is_noise == true) | {number, title, reason: .noise_reason}]' \
  data/owner_repo_issues.json

# Review a specific flagged issue
jq '.[] | select(.number == 42)' data/owner_repo_issues.json
```

### Stage 3: Summarize

**Purpose:** Generate AI-powered summaries of each normalized issue.

**Command:**
```bash
idea-generator summarize --github-repo owner/repo
```

**What it does:**
- ✓ Loads normalized issues from data directory
- ✓ Processes each issue sequentially through the LLM
- ✓ Generates structured summaries with quantitative metrics
- ✓ Caches results to avoid redundant API calls
- ✓ Saves summarized issues to output directory

**Available options:**
```bash
# Basic usage
idea-generator summarize --github-repo facebook/react

# Use different model
idea-generator summarize \
  --github-repo owner/repo \
  --model-innovator llama3.2:3b

# Skip cached summaries (regenerate all)
idea-generator summarize \
  --github-repo owner/repo \
  --skip-cache

# Skip noise-flagged issues
idea-generator summarize \
  --github-repo owner/repo \
  --skip-noise

# Custom directories
idea-generator summarize \
  --github-repo owner/repo \
  --data-dir /custom/data \
  --output-dir /custom/output
```

**Prerequisites:**
- Ollama server must be running (`ollama serve`)
- Model must be pulled (`ollama pull llama3.2:latest`)
- Normalized issues must exist (run `ingest` first)

**Output:** `output/owner_repo_summaries.json` containing AI-generated summaries

**Summary structure:**
```json
[
  {
    "issue_id": 123456789,
    "source_number": 42,
    "title": "Add dark mode support",
    "summary": "Users request dark mode to reduce eye strain. Discussion suggests using CSS variables for theming. Strong community support with 12 upvotes.",
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

**Metric definitions:**
- **Novelty** (0.0-1.0): How innovative or unique the idea is
- **Feasibility** (0.0-1.0): How practical to implement given typical constraints
- **Desirability** (0.0-1.0): How valuable to users and stakeholders
- **Attention** (0.0-1.0): Community engagement level (reactions, comments)

**Performance considerations:**
- **Sequential processing**: Issues processed one at a time to avoid context overflow
- **Processing time**: ~1-2 seconds per issue with 3-8B models
- **Caching**: Successful summaries cached by issue ID for resumption after failures
- **Token budget**: Each issue limited to ~4000 tokens (configurable)

**Expected output:**
```
Summarizing issues from facebook/react...
Loaded 127 normalized issues

Processing issues through LLM...
  [1/127] Issue #28450... ✓ (1.2s)
  [2/127] Issue #28448... ✓ (1.4s)
  [3/127] Issue #28447... ⚠ Retrying... ✓ (2.1s)
  ...
  [127/127] Issue #28001... ✓ (1.3s)

Summary:
  Successful: 125
  Retried: 2
  Failed: 0
  Total time: 3m 24s
  Average: 1.6s per issue

Saved summaries to: output/facebook_react_summaries.json
```

### Stage 4: Group

**Purpose:** Cluster similar issues together and merge duplicates.

**Command:**
```bash
idea-generator group --github-repo owner/repo
```

**What it does:**
- ✓ Loads summarized issues from output directory
- ✓ Groups summaries in batches through the LLM
- ✓ Merges duplicate or highly similar issues
- ✓ Splits multi-topic issues when appropriate
- ✓ Preserves unique issues as singleton clusters
- ✓ Aggregates metrics deterministically (averages)
- ✓ Saves idea clusters to output directory

**Available options:**
```bash
# Basic usage
idea-generator group --github-repo facebook/react

# Skip noise-flagged summaries
idea-generator group \
  --github-repo owner/repo \
  --skip-noise

# Custom batch sizes
idea-generator group \
  --github-repo owner/repo \
  --max-batch-size 15 \
  --max-batch-chars 40000

# Custom Ollama configuration
idea-generator group \
  --github-repo owner/repo \
  --ollama-host http://192.168.1.100 \
  --ollama-port 11434
```

**Prerequisites:**
- Ollama server must be running
- Summarized issues must exist (run `summarize` first)

**Output:** `output/owner_repo_clusters.json` containing idea clusters

**Cluster structure:**
```json
[
  {
    "cluster_id": "ui-ux-001",
    "representative_title": "Theme customization and dark mode",
    "summary": "Multiple users request dark mode and theme switching capabilities for visual customization and accessibility.",
    "topic_area": "UI/UX",
    "member_issue_ids": [42, 89, 103],
    "novelty": 0.35,
    "feasibility": 0.75,
    "desirability": 0.88,
    "attention": 0.65
  }
]
```

**Batching strategy:**
- Issues grouped into batches to respect LLM context limits
- Default: 20 summaries or 50,000 characters per batch (whichever is reached first)
- Deterministic ordering ensures consistent results across runs

**Expected output:**
```
Grouping summarized issues from facebook/react...
Loaded 125 summaries

Processing batches through LLM...
  Batch 1/7 (20 summaries)... ✓ (8.3s)
  Batch 2/7 (20 summaries)... ✓ (7.9s)
  Batch 3/7 (20 summaries)... ✓ (8.1s)
  ...
  Batch 7/7 (5 summaries)... ✓ (3.2s)

Post-processing clusters...
  Validating issue coverage... ✓
  Resolving overlaps... ✓
  Aggregating metrics... ✓

Summary:
  Input summaries: 125
  Output clusters: 48
  Merge ratio: 2.6:1
  Singleton clusters: 31
  Multi-issue clusters: 17
  Total time: 58s

Saved clusters to: output/facebook_react_clusters.json
```

### Stage 5: Run (Full Pipeline)

**Purpose:** Execute the complete end-to-end pipeline.

**Command:**
```bash
idea-generator run --github-repo owner/repo
```

**What it does:**
1. **Ingest** issues from GitHub (or reuse cached data)
2. **Summarize** issues with LLM (or reuse cached summaries)
3. **Group** summaries into clusters (or reuse cached clusters)
4. **Rank** clusters by composite score
5. **Generate** JSON and Markdown reports

**Available options:**
```bash
# Basic usage
idea-generator run --github-repo facebook/react

# Force regeneration (ignore cache)
idea-generator run \
  --github-repo owner/repo \
  --force

# Custom top N ideas in report
idea-generator run \
  --github-repo owner/repo \
  --top-ideas 15

# Skip Markdown report (JSON only)
idea-generator run \
  --github-repo owner/repo \
  --skip-markdown

# With authentication (token in .env recommended)
idea-generator run \
  --github-repo myorg/private-repo
```

**Output files:**
- `output/reports/ideas.json` - Complete dataset with all clusters and metrics
- `output/reports/top-ideas.md` - Human-readable report with top N ranked ideas

**Ranking algorithm:**

Ideas are ranked using a weighted composite score:
```
composite_score = (novelty × 0.25) + (feasibility × 0.25) + 
                  (desirability × 0.30) + (attention × 0.20)
```

Default weights (customizable via environment variables):
- **Novelty**: 0.25
- **Feasibility**: 0.25
- **Desirability**: 0.30
- **Attention**: 0.20

Tie-breaking (deterministic):
1. Composite score (descending)
2. Desirability (descending)
3. Feasibility (descending)
4. Title (alphabetically ascending)

**Expected output:**
```
Running full pipeline for facebook/react...

Stage 1/5: Ingest
  Checking cache... Found existing data
  ✓ Loaded 127 issues from cache

Stage 2/5: Summarize
  Checking cache... Found 98 cached summaries
  Processing remaining 29 issues...
  [1/29] Issue #28350... ✓
  ...
  [29/29] Issue #28120... ✓
  ✓ 127 summaries ready

Stage 3/5: Group
  Processing 127 summaries in batches...
  ✓ Generated 48 clusters

Stage 4/5: Rank
  Calculating composite scores...
  Applying tie-breaking rules...
  ✓ Ranked 48 ideas

Stage 5/5: Generate Reports
  Writing JSON report...
  ✓ output/reports/ideas.json
  
  Writing Markdown report (top 10 ideas)...
  ✓ output/reports/top-ideas.md

Pipeline complete!
  Total time: 4m 23s
  Top idea: "Performance optimization for large lists" (score: 0.87)
```

## Command Reference

**Note on CLI Help:** Due to a known issue with Typer 0.15.1, the `--help` flag may not render correctly on some terminals. This is a cosmetic display issue that does not affect command functionality. All commands work correctly regardless of help rendering. The command reference below provides complete documentation as an alternative.

### Global Options

These options apply to all commands:

```bash
--help                Show help message and exit
```

### setup

Set up the idea-generator environment for first-time use.

**Synopsis:**
```bash
idea-generator setup [OPTIONS]
```

**Options:**
```
--github-repo, -r TEXT        GitHub repository (format: owner/repo)
--github-token, -t TEXT       GitHub API token
--ollama-host TEXT            Ollama server host (default: http://localhost)
--ollama-port INTEGER         Ollama server port (default: 11434)
--model-innovator TEXT        Model for innovator persona (default: llama3.2:latest)
--model-critic TEXT           Model for critic persona (default: llama3.2:latest)
--output-dir, -o PATH         Output directory (default: ./output)
--data-dir, -d PATH           Data directory (default: ./data)
--persona-dir, -p PATH        Persona directory (default: ./personas)
--skip-pull                   Skip pulling models
--offline                     Skip all network operations
```

**Examples:**
```bash
# Basic setup with defaults
idea-generator setup

# Setup with specific models
idea-generator setup --model-innovator llama3.2:3b

# Setup for offline use (models must be pre-installed)
idea-generator setup --offline --skip-pull

# Setup with custom Ollama server
idea-generator setup --ollama-host http://192.168.1.100
```

### ingest

Fetch and normalize issues from a GitHub repository.

**Synopsis:**
```bash
idea-generator ingest --github-repo OWNER/REPO [OPTIONS]
```

**Required:**
```
--github-repo, -r TEXT        GitHub repository (format: owner/repo)
```

**Options:**
```
--github-token, -t TEXT       GitHub API token
--data-dir, -d PATH           Data directory (default: ./data)
--issue-limit INTEGER         Maximum issues to ingest (most recent first)
```

**Examples:**
```bash
# Ingest from public repository
idea-generator ingest --github-repo facebook/react

# Limit to most recent 100 issues (useful for large repos)
idea-generator ingest \
  --github-repo tensorflow/tensorflow \
  --issue-limit 100

# Ingest from private repository (token in .env recommended)
idea-generator ingest \
  --github-repo myorg/private-repo

# Custom data directory
idea-generator ingest \
  --github-repo owner/repo \
  --data-dir /mnt/data/github
```

**Issue Limiting:**

For large repositories with thousands of open issues:
- Use `--issue-limit` to cap the number of issues ingested
- Issues are sorted by `updated_at` (most recent first) before limiting
- This focuses analysis on active issues rather than stale ones
- Recommended limits: 100-200 for repos with >1000 open issues
- Can also be set via `IDEA_GEN_GITHUB_ISSUE_LIMIT` environment variable

### summarize

Generate AI-powered summaries of normalized issues.

**Synopsis:**
```bash
idea-generator summarize --github-repo OWNER/REPO [OPTIONS]
```

**Required:**
```
--github-repo, -r TEXT        GitHub repository (format: owner/repo)
```

**Options:**
```
--data-dir, -d PATH           Data directory (default: ./data)
--output-dir, -o PATH         Output directory (default: ./output)
--ollama-host TEXT            Ollama server host (default: http://localhost)
--ollama-port INTEGER         Ollama server port (default: 11434)
--model-innovator TEXT        Model for summarization (default: llama3.2:latest)
--skip-cache                  Bypass cache and regenerate all summaries
--skip-noise                  Skip issues flagged as noise
```

**Examples:**
```bash
# Basic summarization
idea-generator summarize --github-repo facebook/react

# Use smaller/faster model
idea-generator summarize \
  --github-repo owner/repo \
  --model-innovator llama3.2:3b

# Regenerate all summaries
idea-generator summarize \
  --github-repo owner/repo \
  --skip-cache

# Skip noise issues
idea-generator summarize \
  --github-repo owner/repo \
  --skip-noise
```

### group

Cluster similar issues and merge duplicates.

**Synopsis:**
```bash
idea-generator group --github-repo OWNER/REPO [OPTIONS]
```

**Required:**
```
--github-repo, -r TEXT        GitHub repository (format: owner/repo)
```

**Options:**
```
--output-dir, -o PATH         Output directory (default: ./output)
--ollama-host TEXT            Ollama server host (default: http://localhost)
--ollama-port INTEGER         Ollama server port (default: 11434)
--model-innovator TEXT        Model for grouping (default: llama3.2:latest)
--skip-noise                  Skip summaries flagged as noise
--max-batch-size INTEGER      Maximum summaries per batch (default: 20)
--max-batch-chars INTEGER     Maximum characters per batch (default: 50000)
```

**Examples:**
```bash
# Basic grouping
idea-generator group --github-repo facebook/react

# Custom batch sizes
idea-generator group \
  --github-repo owner/repo \
  --max-batch-size 15 \
  --max-batch-chars 40000

# Skip noise
idea-generator group \
  --github-repo owner/repo \
  --skip-noise
```

### run

Execute the complete end-to-end pipeline.

**Synopsis:**
```bash
idea-generator run --github-repo OWNER/REPO [OPTIONS]
```

**Required:**
```
--github-repo, -r TEXT        GitHub repository (format: owner/repo)
```

**Options:**
```
--github-token, -t TEXT       GitHub API token
--output-dir, -o PATH         Output directory (default: ./output)
--data-dir, -d PATH           Data directory (default: ./data)
--ollama-host TEXT            Ollama server host (default: http://localhost)
--ollama-port INTEGER         Ollama server port (default: 11434)
--model-innovator TEXT        Model for LLM operations (default: llama3.2:latest)
--issue-limit INTEGER         Maximum issues to ingest (most recent first)
--force                       Regenerate all artifacts, skip cached data
--skip-json                   Skip JSON report generation
--skip-markdown               Skip Markdown report generation
--top-ideas INTEGER           Number of top ideas in Markdown report (default: 10)
```

**Examples:**
```bash
# Full pipeline with defaults
idea-generator run --github-repo facebook/react

# For large repositories, limit to most recent 100 issues
idea-generator run \
  --github-repo tensorflow/tensorflow \
  --issue-limit 100

# Force complete regeneration
idea-generator run --github-repo owner/repo --force

# Generate only JSON report
idea-generator run --github-repo owner/repo --skip-markdown

# Custom top N ideas
idea-generator run --github-repo owner/repo --top-ideas 20

# With authentication for private repo (token in .env recommended)
idea-generator run \
  --github-repo myorg/private-repo
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Ollama Not Found

**Error:**
```
Ollama binary not found in PATH
```

**Cause:** Ollama is not installed or not in system PATH.

**Solution:**
1. Install Ollama from [ollama.ai/download](https://ollama.ai/download)
2. Verify installation: `ollama --version`
3. If installed but not in PATH:
   ```bash
   # Find Ollama binary
   which ollama
   
   # Add to PATH (Linux/macOS)
   export PATH=$PATH:/path/to/ollama
   
   # Make permanent by adding to ~/.bashrc or ~/.zshrc
   echo 'export PATH=$PATH:/path/to/ollama' >> ~/.bashrc
   ```

#### 2. Ollama Server Not Running

**Error:**
```
Unable to connect to Ollama server at http://localhost:11434
Connection refused
```

**Cause:** Ollama server is not running.

**Solution:**
1. Start Ollama server in a separate terminal:
   ```bash
   ollama serve
   ```
2. Keep it running while using idea-generator
3. For background operation:
   ```bash
   # Linux/macOS
   nohup ollama serve > /tmp/ollama.log 2>&1 &
   
   # Or use systemd/launchd for auto-start
   ```

#### 3. Model Not Found

**Error:**
```
Model 'llama3.2:latest' not found
```

**Cause:** Required model has not been downloaded.

**Solution:**
```bash
# Pull the model
ollama pull llama3.2:latest

# Verify it's available
ollama list | grep llama3.2

# Re-run setup
idea-generator setup --skip-pull
```

#### 4. Model Download Fails

**Error:**
```
Error pulling model: connection timeout
```

**Causes:**
- Slow or unstable internet connection
- Firewall blocking Ollama
- Ollama service issues

**Solutions:**

**For slow connections:**
```bash
# Try smaller model first
ollama pull llama3.2:3b

# Manually retry
ollama pull llama3.2:latest
```

**For air-gapped/offline environments:**
1. On a machine with internet:
   ```bash
   ollama pull llama3.2:latest
   ollama list  # Note the model name and tag
   ```
2. Export the model:
   ```bash
   # Find Ollama's model directory
   # Linux: ~/.ollama/models
   # macOS: ~/.ollama/models
   
   # Copy entire models directory to USB/network drive
   cp -r ~/.ollama/models /path/to/transfer/
   ```
3. On the offline machine:
   ```bash
   # Copy models to Ollama directory
   cp -r /path/to/transfer/models ~/.ollama/
   
   # Verify
   ollama list
   ```

#### 5. GitHub API Rate Limit

**Error:**
```
GitHub API rate limit exceeded
Rate limit: 60 requests per hour
Reset at: 2025-12-05 15:30:00 UTC
```

**Cause:** Making too many requests without authentication.

**Solution:**

**Immediate:**
- Wait for rate limit reset
- Use a GitHub token for 5000 requests/hour

**Long-term:**
1. Create a GitHub Personal Access Token (see [Configuration](#github-personal-access-token-setup))
2. Add to `.env`:
   ```bash
   IDEA_GEN_GITHUB_TOKEN=<your_token_here>
   ```
3. Verify increased limit:
   ```bash
   curl -H "Authorization: token <your_token_here>" \
     https://api.github.com/rate_limit
   ```

#### 6. Insufficient GitHub Token Permissions

**Error:**
```
Error: Repository 'myorg/private-repo' not found or not accessible
HTTP 404: Not Found
```

**Cause:** Token lacks required permissions.

**Solution:**
1. Check token scopes at [github.com/settings/tokens](https://github.com/settings/tokens)
2. For private repositories, ensure token has `repo` scope
3. For public repositories, `public_repo` scope is sufficient
4. Regenerate token with correct scopes if needed

#### 7. Out of Memory (LLM Processing)

**Error:**
```
Ollama error: failed to allocate memory
Killed
```

**Cause:** Insufficient RAM/VRAM for the selected model.

**Solutions:**

**Use a smaller model:**
```bash
# Instead of 8B
IDEA_GEN_MODEL_INNOVATOR=llama3.2:3b

# Or even smaller
IDEA_GEN_MODEL_INNOVATOR=llama3.2:1b
```

**Reduce batch sizes:**
```bash
# In .env
IDEA_GEN_GROUPING_MAX_BATCH_SIZE=10
IDEA_GEN_GROUPING_MAX_BATCH_CHARS=30000
```

**Close other applications:**
- Free up RAM by closing browsers, IDEs, etc.
- Monitor memory usage: `htop` or `top`

#### 8. Permission Denied Creating Directories

**Error:**
```
PermissionError: [Errno 13] Permission denied: './output'
```

**Cause:** Insufficient permissions to create directories.

**Solutions:**

**Check directory permissions:**
```bash
ls -la ./
```

**Use custom directories:**
```bash
idea-generator setup \
  --output-dir ~/my-output \
  --data-dir ~/my-data
```

**Fix permissions:**
```bash
# Make parent directory writable
chmod u+w .

# Or run with appropriate permissions
sudo chown -R $USER:$USER .
```

#### 9. Slow Processing Speed

**Symptom:** Summarization or grouping takes very long.

**Causes:**
- Large model on slow hardware
- High CPU/GPU load from other processes
- Large batch sizes

**Solutions:**

**Use faster model:**
```bash
IDEA_GEN_MODEL_INNOVATOR=llama3.2:3b
```

**Reduce batch sizes:**
```bash
IDEA_GEN_GROUPING_MAX_BATCH_SIZE=10
```

**Close background applications:**
- Free up CPU/GPU resources
- Monitor with `htop` or Activity Monitor

**Use GPU acceleration:**
- Ensure Ollama is using GPU if available
- Check: `nvidia-smi` (NVIDIA) or `rocm-smi` (AMD)

#### 10. Invalid JSON from LLM

**Error:**
```
Error parsing LLM response: Expecting value at line 1 column 1
```

**Cause:** LLM returned malformed JSON or non-JSON text.

**Solution:**
- This is usually transient; retries are automatic (up to 3 times)
- If persistent:
  ```bash
  # Try different model
  IDEA_GEN_MODEL_INNOVATOR=llama3.1:8b
  
  # Regenerate summaries
  idea-generator summarize --github-repo owner/repo --skip-cache
  ```

#### 11. Stale Cache Issues

**Symptom:** Old results appearing despite repository changes.

**Cause:** Cached data not invalidated.

**Solution:**

**Force regeneration:**
```bash
# For specific stage
idea-generator summarize --github-repo owner/repo --skip-cache

# For entire pipeline
idea-generator run --github-repo owner/repo --force
```

**Manual cache clearing:**
```bash
# Clear all caches
rm -rf data/cache/
rm -rf output/summarization_cache/

# Clear specific repository data
rm data/owner_repo_*.json
rm output/owner_repo_*.json
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs:** Most commands provide detailed error messages
2. **Verify configuration:** Review `.env` file and ensure all paths are correct
3. **Test components individually:** Run `setup`, `ingest`, `summarize`, `group` separately
4. **Check GitHub repository:** Review [issues](https://github.com/AgentFoundryExamples/idea-generator/issues)
5. **Report bugs:** Open a new issue with:
   - Full error message
   - Command that failed
   - OS and Python version
   - Ollama version
   - Model being used

## Advanced Topics

### Using Custom Modelfiles

The idea-generator includes Ollama Modelfiles that bundle system prompts with tuned generation parameters. These modelfiles provide more consistent and deterministic behavior than using base models with separate prompts.

#### Building Custom Modelfiles

The project includes two specialized modelfiles:
- `summarizer.Modelfile`: For analyzing and summarizing GitHub issues
- `grouping.Modelfile`: For clustering similar issues into idea groups

**Build the models:**
```bash
# From the project root directory
ollama create idea-generator-summarizer -f idea_generator/llm/modelfiles/summarizer.Modelfile
ollama create idea-generator-grouping -f idea_generator/llm/modelfiles/grouping.Modelfile

# Verify they're available
ollama list | grep idea-generator
```

**Configure to use them:**
```bash
# In your .env file
IDEA_GEN_MODEL_SUMMARIZING=idea-generator-summarizer
IDEA_GEN_MODEL_GROUPING=idea-generator-grouping
```

Or via CLI:
```bash
idea-generator run \
  --github-repo owner/repo \
  --model-summarizing idea-generator-summarizer \
  --model-grouping idea-generator-grouping
```

#### Modelfile Benefits

1. **Consistency**: System prompts and parameters are locked in, preventing drift
2. **Performance**: Tuned parameters (low temperature, restricted sampling) improve output quality
3. **Portability**: Models can be shared and versioned as single units
4. **Simplicity**: No need to manage separate prompt files at runtime

#### Tuned Parameters

**Summarizer Model:**
- `temperature: 0.3` - Low temperature for focused, deterministic summaries
- `top_k: 20` - Conservative token sampling
- `num_ctx: 4096` - Context window optimized for issue text

**Grouping Model:**
- `temperature: 0.2` - Very low temperature for deterministic clustering
- `top_k: 10` - Strict token sampling for structured output
- `num_ctx: 8192` - Larger context for batch processing

#### Customizing Modelfiles

To use a different base model or adjust parameters:

```bash
# Edit the modelfile
nano idea_generator/llm/modelfiles/summarizer.Modelfile

# Change the base model
FROM llama3.2:8b  # Use 8B model instead of 3B

# Adjust parameters
PARAMETER temperature 0.4  # Slightly higher temperature

# Rebuild
ollama create idea-generator-summarizer -f idea_generator/llm/modelfiles/summarizer.Modelfile
```

#### Updating Models

When you update a modelfile, you must rebuild the model:

```bash
# Edit the modelfile
nano idea_generator/llm/modelfiles/grouping.Modelfile

# Rebuild (overwrites existing)
ollama create idea-generator-grouping -f idea_generator/llm/modelfiles/grouping.Modelfile

# Verify changes
ollama show idea-generator-grouping
```

**Important**: Stale models will continue to use old prompts/parameters until rebuilt.

#### Fallback Behavior

The CLI gracefully handles missing models:
- If custom model names are configured but don't exist: Error with instructions to build them
- If no custom models configured: Uses `llama3.2:latest` with separate prompt files
- If Ollama is unreachable: Clear error with troubleshooting steps

See `idea_generator/llm/modelfiles/README.md` for detailed documentation.

### Customizing Ranking Weights

The default ranking weights may not fit all use cases. Customize them based on your priorities:

**Example 1: Prioritize quick wins (high feasibility + desirability)**
```bash
# In .env
IDEA_GEN_RANKING_WEIGHT_NOVELTY=0.10
IDEA_GEN_RANKING_WEIGHT_FEASIBILITY=0.40
IDEA_GEN_RANKING_WEIGHT_DESIRABILITY=0.40
IDEA_GEN_RANKING_WEIGHT_ATTENTION=0.10
```

**Example 2: Prioritize innovation (high novelty + community interest)**
```bash
# In .env
IDEA_GEN_RANKING_WEIGHT_NOVELTY=0.40
IDEA_GEN_RANKING_WEIGHT_FEASIBILITY=0.15
IDEA_GEN_RANKING_WEIGHT_DESIRABILITY=0.25
IDEA_GEN_RANKING_WEIGHT_ATTENTION=0.20
```

**Example 3: Prioritize user needs (high desirability + attention)**
```bash
# In .env
IDEA_GEN_RANKING_WEIGHT_NOVELTY=0.15
IDEA_GEN_RANKING_WEIGHT_FEASIBILITY=0.20
IDEA_GEN_RANKING_WEIGHT_DESIRABILITY=0.40
IDEA_GEN_RANKING_WEIGHT_ATTENTION=0.25
```

**Important:** Weights must sum to 1.0 (within ±0.01 tolerance).

### Working with Large Repositories

For repositories with hundreds or thousands of issues:

**1. Increase timeouts:**
```bash
IDEA_GEN_LLM_TIMEOUT=180.0
IDEA_GEN_GITHUB_MAX_RETRIES=5
```

**2. Use noise filtering:**
```bash
idea-generator summarize --github-repo owner/repo --skip-noise
idea-generator group --github-repo owner/repo --skip-noise
```

**3. Process in stages:**
```bash
# Stage 1: Ingest (fast)
idea-generator ingest --github-repo owner/repo

# Stage 2: Summarize (slow - run overnight if needed)
idea-generator summarize --github-repo owner/repo

# Stage 3: Group (moderate)
idea-generator group --github-repo owner/repo

# Stage 4: Generate reports (fast)
idea-generator run --github-repo owner/repo --skip-json
```

**4. Monitor progress:**
```bash
# Run in background with logging
nohup idea-generator summarize --github-repo owner/repo > summarize.log 2>&1 &

# Monitor progress
tail -f summarize.log
```

### Offline / Air-Gapped Environments

To use idea-generator without internet access:

**1. Pre-download models on a connected machine:**
```bash
ollama pull llama3.2:latest
ollama list  # Verify download
```

**2. Transfer Ollama models:**
```bash
# Source machine (with internet)
cd ~/.ollama
tar -czf ollama-models.tar.gz models/

# Transfer ollama-models.tar.gz to target machine

# Target machine (offline)
mkdir -p ~/.ollama
cd ~/.ollama
tar -xzf /path/to/ollama-models.tar.gz
```

**3. Pre-ingest GitHub data on connected machine:**
```bash
# Connected machine
idea-generator ingest --github-repo owner/repo
tar -czf github-data.tar.gz data/

# Transfer to offline machine
cd /path/to/idea-generator
tar -xzf /path/to/github-data.tar.gz
```

**4. Run offline:**
```bash
# Skip network operations
idea-generator setup --offline --skip-pull

# Process locally
idea-generator summarize --github-repo owner/repo
idea-generator group --github-repo owner/repo
```

### Using Custom Ollama Server

If running Ollama on a different machine:

**1. Start Ollama with network binding:**
```bash
# On server machine
export OLLAMA_HOST="0.0.0.0:11434"
ollama serve
```

**2. Configure firewall:**
```bash
# Allow port 11434
sudo ufw allow 11434/tcp  # Ubuntu/Debian
sudo firewall-cmd --add-port=11434/tcp  # RHEL/CentOS
```

**3. Point idea-generator to remote server:**
```bash
# In .env
IDEA_GEN_OLLAMA_HOST=http://192.168.1.100
IDEA_GEN_OLLAMA_PORT=11434

# Or via CLI
idea-generator setup --ollama-host http://192.168.1.100
```

**4. Verify connectivity:**
```bash
curl http://192.168.1.100:11434/api/version
```

### Performance Tuning

**Optimize for speed (sacrifice some quality):**
```bash
# Fast model
IDEA_GEN_MODEL_INNOVATOR=llama3.2:3b

# Smaller batches (less waiting per batch)
IDEA_GEN_GROUPING_MAX_BATCH_SIZE=10

# Higher truncation limits (less text to process)
IDEA_GEN_MAX_TEXT_LENGTH=4000
IDEA_GEN_SUMMARIZATION_MAX_TOKENS=2000
```

**Optimize for quality (slower):**
```bash
# Better model
IDEA_GEN_MODEL_INNOVATOR=llama3.2:70b

# Larger batches (better context)
IDEA_GEN_GROUPING_MAX_BATCH_SIZE=30

# More text preserved
IDEA_GEN_MAX_TEXT_LENGTH=12000
IDEA_GEN_SUMMARIZATION_MAX_TOKENS=6000
```

**Optimize for limited hardware:**
```bash
# Smallest viable model
IDEA_GEN_MODEL_INNOVATOR=llama3.2:1b

# Very small batches
IDEA_GEN_GROUPING_MAX_BATCH_SIZE=5
IDEA_GEN_GROUPING_MAX_BATCH_CHARS=20000

# Aggressive truncation
IDEA_GEN_MAX_TEXT_LENGTH=4000
```

### Automating with Scripts

**Example: Daily report generation**
```bash
#!/bin/bash
# daily-report.sh

REPO="myorg/myrepo"
DATE=$(date +%Y-%m-%d)
REPORT_DIR="reports/$DATE"

# Setup environment
source .venv/bin/activate

# Note: Token should be in .env file, not exported in scripts
# IDEA_GEN_GITHUB_TOKEN is read from .env automatically

# Run pipeline
idea-generator run \
  --github-repo "$REPO" \
  --force \
  --top-ideas 20 \
  --output-dir "$REPORT_DIR"

# Archive results
tar -czf "reports/archive/report-$DATE.tar.gz" "$REPORT_DIR"

echo "Report generated: $REPORT_DIR/reports/top-ideas.md"
```

**Schedule with cron:**
```bash
# Edit crontab
crontab -e

# Add daily run at 2 AM (ensure script runs in correct directory)
0 2 * * * cd /path/to/idea-generator && /path/to/idea-generator/daily-report.sh >> /var/log/idea-generator.log 2>&1
```

### CI/CD Integration

**Example: GitHub Actions workflow**
```yaml
name: Generate Ideas Weekly

on:
  schedule:
    - cron: '0 0 * * 0'  # Every Sunday at midnight
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Ollama
        run: |
          curl -fsSL https://ollama.ai/install.sh | sh
          ollama serve &
          sleep 5
      
      - name: Install idea-generator
        run: |
          pip install -e .
      
      - name: Setup
        run: |
          idea-generator setup --model-innovator llama3.2:3b
      
      - name: Generate Report
        env:
          IDEA_GEN_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          idea-generator run --github-repo ${{ github.repository }} --top-ideas 20
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: idea-report
          path: output/reports/
```

## Conclusion

This guide covered the complete workflow for using idea-generator. For additional help:

- **README.md**: Quick reference and architecture overview
- **CHANGELOG.md**: Version history and breaking changes
- **GitHub Issues**: Report bugs or request features
- **Source Code**: Explore `idea_generator/` for implementation details

Happy idea generating! 🚀
