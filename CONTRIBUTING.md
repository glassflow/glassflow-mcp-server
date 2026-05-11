# Contributing

Thanks for your interest in contributing to the GlassFlow MCP Server!

## Development setup

```bash
# Clone the repo
git clone https://github.com/glassflow/glassflow-mcp-server.git
cd glassflow-mcp-server

# Create a virtual environment and install dev dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v

# Run linter
ruff check src/ tests/
ruff format --check src/ tests/
```

## Making changes

1. **Fork** the repo and create a branch from `main`
2. **Write tests** for any new tools or behavior changes
3. **Run the full test suite** before submitting: `pytest -v`
4. **Lint your code**: `ruff check src/ tests/ && ruff format src/ tests/`
5. **Open a pull request** with a clear description of what you changed and why

## Adding a new tool

1. Add the tool function in `src/glassflow_mcp/tools/pipeline.py` (CRUD) or `src/glassflow_mcp/tools/diagnostics.py` (observability)
2. Register it in the appropriate `register_*_tools()` function
3. Write a clear docstring — it's used by AI agents to decide when to call the tool
4. Add tests in `tests/test_pipeline_tools.py` or `tests/test_diagnostics_tools.py`
5. Update the tool table in `README.md`

## Tool description guidelines

Tool descriptions are read by AI agents, not humans. Follow these rules:

- **First sentence**: what the tool does (verb + noun)
- **When to use**: guide the agent on when this tool is appropriate
- **Args**: describe each parameter clearly
- Keep to 3-5 sentences — agents may not read longer descriptions

## Code style

- Python 3.11+
- Formatted with [ruff](https://docs.astral.sh/ruff/)
- Line length: 100 characters
- All files use `from __future__ import annotations`

## Releasing

Releases are automated via GitHub Actions. To create a release:

1. Update `version` in `pyproject.toml`
2. Commit: `git commit -m "chore: bump version to X.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`

The CI workflow will build and publish to PyPI and ghcr.io automatically.
