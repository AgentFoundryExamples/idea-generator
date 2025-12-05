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
2. Generate a new token (classic) with `repo` scope
3. Copy the token and add it to your `.env` file

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

### Step 2: Ingest Repository Data (Coming Soon)

```bash
idea-generator ingest --github-repo owner/repo
```

### Step 3: Generate Ideas (Coming Soon)

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
│   └── setup.py             # Setup workflow and Ollama integration
├── tests/                   # Test suite
│   ├── test_config.py       # Configuration tests
│   ├── test_setup.py        # Setup workflow tests
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
