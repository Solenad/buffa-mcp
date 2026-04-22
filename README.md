# buffa-mcp

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-lightgrey)](https://github.com/Rohann/buffa-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 
![GitHub last commit](https://img.shields.io/github/last-commit/Solenad/buffa-mcp)
![visitors](https://visitor-badge.laobi.icu/badge?page_id=Solenad.buffa-mcp.id)

## Project Name and Description

**Buff**a **M**odel **C**ontext **P**rotocol (MCP) – a token‑budget‑aware retrieval engine that enables large local codebases to be searched by LLMs under strict token limits. It provides:

- Incremental indexing of source files using language‑aware cAST chunking (Tree‑Sitter when available) and line‑based fallback.
- Hybrid semantic + keyword retrieval backed by NVIDIA NIM embeddings and reranking.
- Deterministic packing of retrieved chunks into a configurable token budget, with automatic compression (strip comments, docstrings, truncate) when needed.
- A small, test‑driven Python package (`buffa`) that can be run as an MCP server or embedded in other tools.

---

## Technology Stack

| Layer | Technology / Library | Version (as of this repo) |
|------|----------------------|---------------------------|
| Language | **Python** | ≥ 3.11 |
| Core deps | `pydantic` | 2.8.2 (pinned)<br>`tiktoken` | 0.8.0 |
| HTTP client | `httpx` | (implicit via NIM client) |
| Parsing / Chunking | Optional **Tree‑Sitter** (via `tree_sitter` and language bindings) |
| Testing | `pytest` | 8.2.0 (dev extra) |
| Build / Packaging | `setuptools`, `wheel` |
| Optional linting/formatting | `ruff` (ignored by repo), `black` (recommended) |

---

## Project Architecture

```
client (CLI scripts) ──► runtime config loader ──► NIM clients (embedding, reranking, health)
          │                                             │
          ▼                                             ▼
   indexing engine ──► cAST chunker (Tree‑Sitter) ──► fallback chunker
          │                                             │
          ▼                                             ▼
   vector store (e.g. Qdrant / Chroma) ◄─► batch processor (embedding)
          │
          ▼
   retrieval pipeline ──► query embedding ──► hybrid search (semantic + keyword)
          │                               │
          ▼                               ▼
   reranker (NIM) ──► token‑budget packer ──► optional compression cascade
          │
          ▼
   MCP server (stdio transport) – exposes `search_codebase` & `index_status`
```

*High‑level flow* (see `PLAN.md` for full details):
1. **Ingestion** – source files → cAST chunker → `SourceChunk` objects → embeddings → vector DB.
2. **Retrieval** – query → query embedding → hybrid similarity → NIM reranker → token‑budget contract → packed context payload.
3. **Watch mode** – `index.watch.enabled` triggers incremental re‑indexing on file changes.

---

## Getting Started

### Prerequisites
- Python 3.11 or newer.
- An NVIDIA API key (`NVIDIA_API_KEY`) for any NIM calls.
- Optional: `tree_sitter` and language bindings for richer chunking.

### Installation & Bootstrap
```bash
# Clone the repo (if you haven't already)
git clone https://github.com/Rohann/buffa-mcp.git
cd buffa-mcp

# Install runtime + development extras and run the sanity‑check script
python scripts/bootstrap.py
```
The bootstrap script:
1. Upgrades `pip`.
2. Installs the package in editable mode with dev extras (`pytest`).
3. Runs `scripts/verify_bootstrap.py` to validate scaffold, imports, env contract, and test harness.

### Verify the Setup
```bash
python scripts/verify_bootstrap.py
```
You should see `Bootstrap verification passed.`

### Configuration
Create a `.buffa.json` (or rely on defaults). A minimal example:
```json
{
  "nim": {
    "api_key": "${NVIDIA_API_KEY}"
  },
  "index": {
    "include": ["./src"]
  }
}
```
Environment variable expansion (`${VAR}`) is supported – missing secrets cause a `StartupDiagnosticError`.

---

## Project Structure
```
buffa-mcp/
├─ src/                # Library code (buffa package)
│   ├─ buffa/
│   │   ├─ config/          # Pydantic config models & loader
│   │   ├─ indexing/        # Chunkers, batch processor, watchers
│   │   ├─ nim/             # NIM client wrappers (embedding, reranking, health)
│   │   ├─ mcp/             # MCP transport interface (stdio)
│   │   ├─ retrieval/       # Retrieval entry‑points
│   │   └─ shared/          # Models, error hierarchy, utilities
│   └─ __init__.py
├─ tests/               # Unit & integration tests
│   ├─ unit/
│   └─ integration/
├─ openspec/           # OpenSpec change workflow (plans, specs, change dirs)
├─ scripts/             # Bootstrap & verification helpers
├─ pyproject.toml      # Build metadata & dependencies
├─ README.md            # (this file)
└─ AGENTS.md           # Agent‑focused documentation
```

---

## Key Features
- **Token‑budget contract** – deterministic packing with per‑model overrides and a configurable reserve (see `src/buffa/config/models.py`).
- **Incremental indexing** – file‑watcher automatically re‑indexes changed files (`index.watch.enabled`).
- **Language‑aware chunking** – cAST parsing via Tree‑Sitter for Python, JS/TS, Go, Rust, Java, C/C++, with graceful fallback to line‑based chunking.
- **Hybrid retrieval** – combines semantic similarity (vector DB) with keyword weighting (`search.hybrid.enabled`).
- **NIM integration** – typed clients for embeddings, reranking, health checks, and optional generation.
- **Structured error handling** – `NIMError` categories (transport, auth, timeout, response shape) allow retry policies.
- **OpenSpec change management** – all production changes live under `openspec/changes/` with `openspec apply`/`archive` workflow.

---

## Development Workflow
1. **Bootstrap** (once) – `python scripts/bootstrap.py`.
2. **Make changes** under `src/buffa/`.
3. **Run verification** – `python scripts/verify_bootstrap.py` (checks scaffold, imports, env contract, and runs the test suite).
4. **Run the test suite** – `pytest -q` (full), or target subfolders (`pytest tests/unit -q`).
5. **Check coverage** – `pytest --cov=src --cov-report=term-missing` (project aims for ≥ 80 %).
6. **OpenSpec changes** – create a directory `openspec/changes/<name>/`, add a `PLAN.md` and any spec files, then run:
   ```bash
   openspec apply   # generate artifacts
   # ... review, test, etc.
   openspec archive # move to archive when approved
   ```
7. **Commit** – follow Conventional Commits (`feat(indexing): …`, `fix(config): …`).
8. **Pull request** – title format `[module] Short description`; CI (if added) must pass; at least one senior reviewer required.

---

## Coding Standards
- **Explicit type hints** everywhere; `any` is prohibited.
- **PEP 8** line length ≤ 100 chars.
- **Absolute imports** from the package root (`from buffa.config import runtime`).
- **Logging** – use the standard library `logging` module; modules expose a `logger = logging.getLogger(__name__)`.
- **Error hierarchy** – custom errors inherit from `BuffaError` (found in `src/buffa/shared/errors.py`).
- **No business logic in controllers** (this repo is not a web service, but the same principle applies: keep I/O separate from pure functions).
- **Optional linting** – `ruff check src tests` or `black` for formatting.

---

## Testing
- **Framework** – `pytest` (dev extra). All tests live under `tests/`.
- **Running tests**:
  ```bash
  pytest -q                 # all tests
  pytest tests/unit -q      # unit tests only
  pytest tests/integration -q  # integration tests only
  ```
- **Coverage** – aim for ≥ 80 % line coverage:
  ```bash
  pytest --cov=src --cov-report=term-missing
  ```
- **Test organization** – unit tests check individual modules (e.g., config loader, NIM client error handling); integration tests verify end‑to‑end indexing & retrieval pipelines.

---

## Contributing
1. **Fork** the repository and create a feature branch.
2. **Follow the development workflow** above.
3. **Write tests** for any new functionality; keep coverage high.
4. **Run the bootstrap verification** before pushing.
5. **Create an OpenSpec change** if the modification is a public‑facing feature (recommended for major additions).
6. **Submit a PR** adhering to the title format `[module] Short description` and ensure all checks pass.
7. **Reference code exemplars** – look at existing implementations in `src/buffa/` (e.g., `chunker.py`, `embedding.py`, `reranking.py`) for style and patterns.

---

## License
This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

*For AI‑focused documentation, see `AGENTS.md` in the repository root.*
