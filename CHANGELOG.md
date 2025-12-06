# Changelog

All notable changes to the idea-generator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-05

### Added

#### Core Features
- **CLI Tool**: Comprehensive command-line interface with five main commands:
  - `setup`: Environment preparation, model pulling, and directory creation
  - `ingest`: GitHub issue fetching and normalization
  - `summarize`: AI-powered issue summarization with quantitative metrics
  - `group`: Intelligent clustering and deduplication of issues
  - `run`: End-to-end pipeline orchestration with report generation

#### GitHub Integration
- **Issue Ingestion**: Fetch open issues from any public or private GitHub repository
- **Pagination Support**: Automatic handling of large repositories with paginated API requests
- **Rate Limit Management**: Exponential backoff and retry logic for API rate limits
- **Token Authentication**: Support for GitHub Personal Access Tokens with configurable scopes
- **Caching System**: Raw API response caching for offline re-use and debugging
- **Comment Threading**: Retrieval and normalization of issue comment threads
- **Deleted User Handling**: Graceful handling of issues/comments from deleted accounts

#### Data Processing
- **Markdown Cleaning**: Intelligent removal of markdown syntax while preserving content
  - Code blocks, inline code, images, links, headers, lists, blockquotes
  - HTML comments and excessive whitespace
- **Comment Deduplication**: Case-insensitive detection of duplicate comments
- **Noise Filtering**: Automatic detection of low-quality issues:
  - Spam labels (spam, invalid, wontfix, duplicate)
  - Bot authors (dependabot, renovate, github-actions)
  - Single-word titles and empty bodies
  - Common spam patterns
- **Text Truncation**: Deterministic truncation to fit within LLM context windows
  - Issue body gets priority (minimum 50% of limit)
  - Comments included in chronological order until limit reached
  - Metadata tracking (original length, truncation status)

#### LLM Integration
- **Ollama Client**: HTTP client wrapper for local Ollama server communication
- **Model Management**: Support for multiple models and personas
  - Innovator persona for creative idea generation
  - Critic persona for evaluation (infrastructure ready, not yet used)
- **Persona System**: Configurable system prompts stored in version control
  - Summarizer: Individual issue analysis with metrics
  - Grouper: Cluster detection and deduplication
- **Context Management**: Intelligent batching to prevent context overflow
- **Retry Logic**: Automatic retry with exponential backoff for failed LLM requests
- **Response Validation**: JSON schema validation with fallback parsing

#### Summarization Pipeline
- **Sequential Processing**: One issue at a time to prevent context overflow
- **Quantitative Metrics**: Four-dimensional scoring system (0.0-1.0 scale):
  - **Novelty**: How innovative or unique the idea is
  - **Feasibility**: How practical to implement
  - **Desirability**: How valuable to users/stakeholders
  - **Attention**: Community engagement level
- **Topic Classification**: Automatic categorization (performance, security, UI/UX, bug, feature, etc.)
- **Result Caching**: Individual summary caching by issue ID for resumption after failures
- **Progress Tracking**: Real-time logging of processing status

#### Grouping Pipeline
- **Batch Processing**: Process multiple summaries simultaneously within context limits
- **Intelligent Clustering**: LLM-powered detection of similar issues
- **Duplicate Merging**: Combine issues addressing the same core problem
- **Multi-Topic Splitting**: Separate issues that combine multiple distinct concerns
- **Singleton Preservation**: Keep unique issues as individual clusters
- **Metric Aggregation**: Deterministic averaging of quantitative metrics
- **Validation System**: Post-processing validation of cluster assignments
  - Issue ID existence checking
  - Overlap detection and resolution
  - Coverage verification (all issues assigned to exactly one cluster)

#### Ranking System
- **Composite Scoring**: Weighted combination of four metrics
  - Default weights: Novelty (0.25), Feasibility (0.25), Desirability (0.30), Attention (0.20)
  - Customizable via environment variables
  - Runtime validation (weights must sum to 1.0 ±0.01)
- **Deterministic Tie-Breaking**: Multi-level sorting for consistent ordering
  1. Composite score (descending)
  2. Desirability (descending)
  3. Feasibility (descending)
  4. Title (alphabetically ascending)

#### Report Generation
- **JSON Report**: Machine-readable complete dataset
  - All clusters with normalized metrics
  - Composite scores and rankings
  - Source issue URLs for traceability
  - Noise indicators
- **Markdown Report**: Human-readable summary
  - Top N ranked ideas (configurable, default: 10)
  - Metric breakdowns with visual indicators
  - Priority tags (🔥 Critical, ⭐ High, ✅ Medium, 💡 Low)
  - Links to source GitHub issues
  - Summary statistics

#### Configuration System
- **Environment Variables**: 30+ configurable parameters
- **.env File Support**: Python-dotenv integration for easy configuration
- **CLI Overrides**: Command-line arguments override environment variables
- **Sensible Defaults**: Works out-of-the-box with minimal configuration
- **Validation**: Runtime validation of critical parameters (token presence, weight sums, etc.)

#### Documentation
- **README.md**: Comprehensive quick-start guide with:
  - Installation instructions for all platforms
  - Prerequisites and system requirements
  - Configuration examples
  - Usage examples for all commands
  - Troubleshooting common issues
  - Project structure overview
  - Development guidelines
- **docs/USAGE.md**: Detailed usage guide with:
  - Step-by-step setup instructions
  - Complete environment variable reference table
  - GitHub token scope requirements and creation guide
  - Ollama model selection and configuration
  - Full command reference with examples
  - Comprehensive troubleshooting section
  - Advanced topics (offline use, custom servers, performance tuning)
  - CI/CD integration examples
- **.env.example**: Annotated configuration template with:
  - All available environment variables
  - Default values and descriptions
  - Token scope requirements
  - Configuration categories

### Technical Details

#### Dependencies
- **Core**: Python 3.11+, typer 0.15.1, pydantic 2.10.3, httpx 0.28.1
- **Configuration**: python-dotenv 1.0.1, pydantic-settings 2.6.1
- **Data**: pyyaml 6.0.2
- **Development**: pytest 8.3.4, black 24.10.0, ruff 0.8.4, mypy 1.13.0

#### Testing
- **225+ Unit Tests**: Comprehensive test coverage across all modules
- **Test Categories**:
  - Data cleaning and normalization
  - Configuration management
  - Model validation
  - Setup workflow
  - Scoring and ranking
  - Report generation
  - GitHub API client
  - LLM client
  - Pipeline orchestration
  - CLI integration
- **Testing Tools**: pytest, pytest-cov, pytest-mock
- **Coverage Target**: 70%+ code coverage

#### Code Quality
- **Formatting**: Black with 100-character line length
- **Linting**: Ruff with strict error checking
- **Type Checking**: MyPy with strict mode for all modules
- **License Headers**: Apache 2.0 license headers in all source files

#### Performance Characteristics
- **Ingestion**: ~1-2 seconds per 100 issues (depends on API latency)
- **Summarization**: ~1-2 seconds per issue with 3-8B models (sequential)
- **Grouping**: ~5-10 seconds per batch of 20 issues
- **Ranking**: <1 second for typical repositories
- **Caching**: Near-instant when reusing cached results

#### Resource Requirements
- **RAM**: 4GB minimum for 1B models, 8GB for 3B, 16GB+ for 8B+
- **Disk**: 10GB+ for model storage
- **CPU**: Multi-core recommended for Ollama (1 core minimum)
- **GPU**: Optional but significantly improves LLM inference speed
- **Network**: Required for initial setup, optional for subsequent runs with caching

### Model Requirements

#### Recommended Models
- **Default**: `llama3.2:latest` (8B parameters, ~5GB download)
- **Fast/Light**: `llama3.2:3b` (~2GB download)
- **Minimal**: `llama3.2:1b` (~1GB download)
- **High-Quality**: `llama3.2:70b` (~40GB download, requires 64GB+ RAM)

#### Model Compatibility
- Works with any Ollama-compatible model
- Tested with Llama 3.1 and 3.2 series
- Persona prompts optimized for instruction-tuned models
- JSON output parsing works best with recent models (2024+)

### Configuration Changes

#### Environment Variables Added
All 30+ environment variables documented in `.env.example` with:
- Variable name and format
- Default value
- Description of purpose
- Required vs optional status
- Token scope requirements (for GitHub variables)

#### Default Behavior
- No breaking changes in this initial release
- All features opt-in via environment variables
- Sensible defaults for all parameters
- Graceful degradation when optional dependencies missing

### Manual Steps for Updates

#### First-Time Setup
1. **Install Python 3.11+**: Required before package installation
2. **Install Ollama**: Download from [ollama.ai/download](https://ollama.ai/download)
3. **Start Ollama Server**: Run `ollama serve` in a separate terminal
4. **Clone Repository**: `git clone https://github.com/AgentFoundryExamples/idea-generator.git`
5. **Create Virtual Environment**: `python -m venv .venv && source .venv/bin/activate`
6. **Install Package**: `pip install -e ".[dev]"` for development or `pip install -e .` for production
7. **Configure Environment**: Copy `.env.example` to `.env` and customize
8. **Run Setup**: `idea-generator setup` to pull models and create directories
9. **Create GitHub Token** (optional): For private repos or higher rate limits
10. **Verify Installation**: `idea-generator --help` should show command list

#### Updating Persona Prompts
Persona prompts are stored in `idea_generator/llm/prompts/`:
- `summarizer.txt`: Prompt for individual issue summarization
- `grouper.txt`: Prompt for issue clustering and deduplication

To modify behavior:
1. Edit the relevant prompt file
2. Test with a small repository
3. Commit changes to version control
4. Re-run affected pipeline stages with `--skip-cache` or `--force`

No need to re-pull models or re-run setup when changing prompts.

#### Adjusting Ranking Weights
To change how ideas are ranked:
1. Edit `.env` and modify `IDEA_GEN_RANKING_WEIGHT_*` variables
2. Ensure weights sum to 1.0 (±0.01 tolerance)
3. Re-run ranking: `idea-generator run --github-repo owner/repo`
4. No need to regenerate summaries or clusters

#### Changing Models
To switch to a different Ollama model:
1. Pull the new model: `ollama pull model:tag`
2. Update `.env`: `IDEA_GEN_MODEL_INNOVATOR=model:tag`
3. Re-run affected stages with `--skip-cache` or `--force`
4. Old summaries will be regenerated with the new model

### Known Limitations

#### Current Scope
- **Read-Only**: Tool does not create or modify GitHub issues
- **Open Issues Only**: Closed issues are not ingested (can be extended)
- **Sequential Summarization**: Issues processed one at a time (by design for small models)
- **English Language**: Prompts optimized for English (works with other languages but not tested)
- **Critic Persona Unused**: Infrastructure present but not integrated into pipeline yet

#### Platform Support
- **Windows**: Requires WSL2 for Ollama (native Windows support pending)
- **ARM64**: Ollama and Python support ARM64 but less tested
- **GPU**: Optional; CPU-only mode works but slower

#### API Limitations
- **GitHub Rate Limits**: 60/hour without token, 5000/hour with token
- **Large Repositories**: Very large repos (1000+ issues) may take hours to process
- **Ollama Server**: Must be running locally or remotely; no embedded mode

#### Known Issues
- **CLI Help Rendering**: Typer 0.15.1 has a known issue with `--help` rendering on some terminals. The actual commands work correctly. This is a cosmetic issue that will be resolved in a future typer update.

### Security Considerations

#### Token Handling
- GitHub tokens stored in `.env` (never committed to git)
- `.gitignore` includes `.env` to prevent accidental commits
- Tokens passed via environment variables (not CLI arguments in logs)
- No token validation beyond API calls

#### Data Privacy
- All data processed locally (no external API calls except GitHub and Ollama)
- Cached data stored unencrypted in `data/` and `output/`
- Consider `.gitignore` for sensitive cached data

#### Ollama Security
- Ollama server listens on localhost by default (safe)
- Network binding (`0.0.0.0`) requires firewall configuration
- No authentication on Ollama API (trust local network)

### Upgrade Notes

This is the initial release (v0.1.0). Future releases will document:
- Breaking changes requiring manual intervention
- Deprecated features with migration paths
- New features and their configuration
- Performance improvements and optimizations

### Future Roadmap

Planned features for future releases:
- **Critic Persona Integration**: Two-stage validation of ideas
- **Closed Issue Analysis**: Analyze resolved issues for patterns
- **Multi-Repository Analysis**: Compare ideas across multiple repos
- **Interactive Mode**: TUI for exploring and filtering ideas
- **Custom Personas**: User-defined persona prompts
- **Export Formats**: PDF, HTML, CSV report generation
- **GitHub Issue Creation**: Auto-create issues from top ideas
- **Incremental Updates**: Process only new/changed issues
- **Multilingual Support**: Prompts and docs in multiple languages
- **Web UI**: Browser-based interface for non-CLI users

### Contributors

- John Brosnihan - Initial development
- Agent Foundry - Project sponsor and framework

### License

This project is licensed under the Apache License 2.0. See LICENSE file for details.

---

## Release Process

### Version Numbering

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes requiring manual intervention
- **MINOR**: New features, backward-compatible
- **PATCH**: Bug fixes, backward-compatible

### Release Checklist

For maintainers preparing a release:

1. **Update Version**:
   - Bump version in `pyproject.toml`
   - Add new section to this CHANGELOG
   - Update version references in docs

2. **Test**:
   - Run full test suite: `pytest`
   - Test on multiple platforms if possible
   - Verify examples in documentation

3. **Documentation**:
   - Update README.md with any new features
   - Add migration notes if breaking changes
   - Update CLI help text if needed

4. **Tag Release**:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```

5. **Publish**:
   - Create GitHub release with changelog excerpt
   - Include installation instructions
   - Attach any relevant artifacts

### Deprecation Policy

- Features will be deprecated with at least one minor version notice
- Deprecated features will include migration instructions
- Removal will occur in the next major version
- Breaking changes will be highlighted in CHANGELOG

---

For questions or feedback about this release, please open an issue on the [GitHub repository](https://github.com/AgentFoundryExamples/idea-generator/issues).
