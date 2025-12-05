# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 23
- **Intra-repo dependencies**: 18
- **External stdlib dependencies**: 17
- **External third-party dependencies**: 10

## External Dependencies

### Standard Library / Core Modules

Total: 17 unique modules

- `datetime.UTC`
- `datetime.datetime`
- `json`
- `logging`
- `os`
- `pathlib.Path`
- `re`
- `shutil`
- `subprocess`
- `tempfile`
- `tempfile.TemporaryDirectory`
- `time`
- `typing.Annotated`
- `typing.Any`
- `unittest.mock.MagicMock`
- `unittest.mock.Mock`
- `unittest.mock.patch`

### Third-Party Packages

Total: 10 unique packages

- `httpx`
- `pydantic.BaseModel`
- `pydantic.Field`
- `pydantic.ValidationError`
- `pydantic.field_validator`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- `typer`
- `typer.testing.CliRunner`

## Most Depended Upon Files (Intra-Repo)

- `idea_generator/models.py` (4 dependents)
- `idea_generator/llm/client.py` (3 dependents)
- `idea_generator/cli.py` (2 dependents)
- `idea_generator/setup.py` (2 dependents)
- `idea_generator/config.py` (2 dependents)
- `idea_generator/github_client.py` (2 dependents)
- `idea_generator/cleaning.py` (1 dependents)
- `idea_generator/pipelines/grouping.py` (1 dependents)
- `idea_generator/pipelines/summarize.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `tests/test_grouping_pipeline.py` (3 dependencies)
- `tests/test_summarize_pipeline.py` (3 dependencies)
- `tests/test_cleaning.py` (2 dependencies)
- `tests/test_cli.py` (2 dependencies)
- `tests/test_integration.py` (2 dependencies)
- `tests/test_setup.py` (2 dependencies)
- `tests/test_config.py` (1 dependencies)
- `tests/test_github_client.py` (1 dependencies)
- `tests/test_llm_client.py` (1 dependencies)
- `tests/test_models.py` (1 dependencies)
