# AGENTS.md

## Project Overview
- **Name**: `buffa`
- **Purpose**: Token‑budget‑aware Model Context Protocol (MCP) that lets large local codebases be searched by LLMs under strict token limits.
- **Key concepts**: incremental indexing, hybrid semantic/keyword retrieval, NVIDIA NIM embeddings/reranking, deterministic packing with a token‑budget contract.
- **Primary language**: Python ≥ 3.11
- **Core dependencies**: `pydantic`, `tiktoken`
- **Dev dependencies**: `pytest`
- **Package layout**:
  - `src/buffa/` – library code (config, indexing, retrieval, MCP server, shared utils)
  - `tests/` – unit and integration tests
  - `openspec/` – OpenSpec change workflow (plans, specs, change directories)

## Setup Commands
- **Bootstrap the development environment** (installs runtime + dev extras and runs the verification gate):
  ```bash
  python scripts/bootstrap.py
  ```
- **Verify the bootstrap** (runs scaffold, import, environment‑contract and smoke‑test checks):
  ```bash
  python scripts/verify_bootstrap.py
  ```
- **Install only runtime dependencies** (if you do not need dev tools):
  ```bash
  pip install -e .
  ```
- **Install development extras** (includes `pytest` and any future linting tools):
  ```bash
  pip install -e .[dev]
  ```
- **Environment variables** (required at runtime):
  - `NVIDIA_API_KEY` – **required** for any NIM request.
  - `BUFFA_NIM_BASE_URL` – optional, defaults to `https://integrate.api.nvidia.com/v1`.
  - `BUFFA_CONFIG_PATH` – optional, defaults to `.buffa.json`.

## Development Workflow
- **Work on the library** – add or modify code under `src/buffa/`.
- **Run the verification gate** after any change to ensure scaffold, imports and environment contract are still valid:
  ```bash
  python scripts/verify_bootstrap.py
  ```
- **Iterative indexing** – the watcher (`watch.enabled` in the config) will automatically re‑index changed files when the library is running. No manual command is required for normal development.
- **OpenSpec changes** – create a new change under `openspec/changes/<name>/` and follow the OpenSpec stabilisation flow (`openspec apply`, `openspec archive`). See the `openspec/` directory for details.

## Testing Instructions
- **Run the full test suite** (unit + integration) with the standard pytest configuration defined in `pyproject.toml`:
  ```bash
  pytest -q
  ```
- **Run only unit tests**:
  ```bash
  pytest tests/unit -q
  ```
- **Run only integration tests**:
  ```bash
  pytest tests/integration -q
  ```
- **Run a single test file or test function** (use the `-k` pattern):
  ```bash
  pytest -k "test_token_budget" -q
  ```
- **Coverage** – the project aims for ≥ 80 % line coverage. Generate a coverage report with:
  ```bash
  pytest --cov=src --cov-report=term-missing
  ```
- **Test locations**:
  - Unit tests: `tests/unit/`
  - Integration tests: `tests/integration/`

## Code Style Guidelines
- **Type safety** – all public functions and methods must have explicit type hints; `any` is prohibited.
- **Formatting** – use `black` (if added later) or follow PEP 8 spacing and line‑length ≤ 100 chars.
- **Linting** – `ruff` is ignored by the repo (`.ruff_cache/` is in `.gitignore`), but any added linter should be run via:
  ```bash
  ruff check src tests
  ```
- **Import style** – absolute imports from the package root (`from buffa.config import runtime`) are preferred.
- **File organization** – keep the layer boundaries defined in the AGENTS.md sections (e.g., `config/` for environment contracts only, `indexing/` for chunking and vector store logic, etc.).

## Build and Deployment
- **Installable package** – the repository is a standard Python package. After bootstrap you can install it editable (`pip install -e .`) or build a wheel:
  ```bash
  python -m build
  ```
- **OpenSpec workflow** – for any production change:
  1. Create a change directory under `openspec/changes/<change-name>/`.
  2. Add a `PLAN.md` (see `PLAN.md` for the `buffa-retrieval-packer` example) and any spec files.
  3. Run `openspec apply` to generate artifacts.
  4. When approved, run `openspec archive` to move the change to `openspec/changes/archive/`.
- **CI/CD** – currently the repo does not contain a GitHub Actions workflow, but the standard steps are:
  1. Install Python and run `pip install -e .[dev]`.
  2. Execute `pytest`.
  3. Optionally run a static‑analysis step (ruff/black) and a coverage check.

## Optional Sections
### Security Considerations
- **Secrets management** – `NVIDIA_API_KEY` must never be committed. Use environment variables or a secure secret store.
- **Runtime contract** – `buffa.config.runtime.load_runtime_settings` validates required env vars and raises `StartupDiagnosticError` if missing.
- **Network calls** – all NIM requests use the OpenAI‑compatible client; ensure TLS verification is enabled.

### OpenSpec / Change Management
- The `openspec/` directory contains the specification and change artifacts. Agents should be aware of the **plan** for the `buffa-retrieval-packer` change (`openspec/changes/buffa-retrieval-packer/PLAN.md`).
- Use the OpenSpec tooling (`openspec apply`, `openspec archive`) to manage incremental changes without directly committing to `main`.

### Pull Request Guidelines
1. **Title format** – `[module] Short description`
   - Example: `[indexing] Add token‑budget aware packer`
2. **Required checks before PR**:
   - Run `python scripts/verify_bootstrap.py`
   - Run the full test suite (`pytest -q`).
   - Ensure coverage ≥ 80 % for new/modified code.
3. **Review process** – at least one senior developer must approve; CI must pass.
4. **Commit messages** – follow Conventional Commits (e.g., `feat(indexing): add chunk compression`).

### Debugging & Troubleshooting
- **Common failure** – missing `NVIDIA_API_KEY`:
  ```bash
  export NVIDIA_API_KEY=your-key
  python scripts/verify_bootstrap.py
  ```
- **Watcher not re‑indexing** – ensure `index.watch.enabled` is true in the runtime config and that the process has write permission to `.buffa/db`.
- **Vector store errors** – check that the configured DB path (`index.db_path`) exists and is writable.
- **Test harness failures** – run a single failing test to view the traceback; use `pytest -vv` for verbose output.

---
*This file is intended for AI coding agents. Human‑focused documentation lives in `README.md`. Keep this file up‑to‑date as the project evolves.*
