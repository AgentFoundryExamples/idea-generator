# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 8
- **Intra-repo dependencies**: 5
- **External stdlib dependencies**: 9
- **External third-party dependencies**: 9

## External Dependencies

### Standard Library / Core Modules

Total: 9 unique modules

- `json`
- `os`
- `pathlib.Path`
- `shutil`
- `subprocess`
- `tempfile`
- `typing.Annotated`
- `unittest.mock.MagicMock`
- `unittest.mock.patch`

### Third-Party Packages

Total: 9 unique packages

- `httpx`
- `pydantic.Field`
- `pydantic.ValidationError`
- `pydantic.field_validator`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- `typer`
- `typer.testing.CliRunner`

## Most Depended Upon Files (Intra-Repo)

- `idea_generator/setup.py` (2 dependents)
- `idea_generator/config.py` (2 dependents)
- `idea_generator/cli.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `tests/test_cli.py` (2 dependencies)
- `tests/test_setup.py` (2 dependencies)
- `tests/test_config.py` (1 dependencies)
