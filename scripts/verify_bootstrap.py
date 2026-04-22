from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SCAFFOLD = [
    ROOT / "pyproject.toml",
    ROOT / "src" / "buffa" / "__init__.py",
    ROOT / "src" / "buffa" / "config" / "runtime.py",
    ROOT / "src" / "buffa" / "indexing" / "__init__.py",
    ROOT / "src" / "buffa" / "retrieval" / "__init__.py",
    ROOT / "src" / "buffa" / "mcp" / "__init__.py",
    ROOT / "src" / "buffa" / "shared" / "errors.py",
    ROOT / "tests" / "unit" / "test_runtime_settings.py",
    ROOT / "tests" / "integration" / "test_imports.py",
]

MODULES = [
    "buffa",
    "buffa.config.runtime",
    "buffa.indexing",
    "buffa.retrieval",
    "buffa.mcp",
    "buffa.shared.errors",
]


def verify_scaffold() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_SCAFFOLD if not path.exists()]
    if missing:
        raise RuntimeError(
            "Missing required scaffold files:\n- " + "\n- ".join(missing)
        )


def verify_imports() -> None:
    src_path = str(ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    failed: list[str] = []
    for module in MODULES:
        try:
            importlib.import_module(module)
        except Exception as exc:  # pragma: no cover
            failed.append(f"{module}: {exc}")

    if failed:
        raise RuntimeError("Module import check failed:\n- " + "\n- ".join(failed))


def verify_env_contract() -> None:
    from buffa.config.runtime import load_runtime_settings
    from buffa.shared.errors import StartupDiagnosticError

    key = "NVIDIA_API_KEY"
    previous = os.environ.get(key)

    try:
        if key in os.environ:
            del os.environ[key]
        try:
            load_runtime_settings()
        except StartupDiagnosticError:
            pass
        else:
            raise RuntimeError("Expected missing NVIDIA_API_KEY diagnostic was not raised")

        os.environ[key] = "bootstrap-smoke-token"
        settings = load_runtime_settings()
        if not settings.nim_api_key:
            raise RuntimeError("Resolved runtime settings produced an empty NVIDIA_API_KEY")
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def verify_harness() -> None:
    command = [sys.executable, "-m", "pytest", "tests/unit", "tests/integration", "-q"]
    proc = subprocess.run(command, cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise RuntimeError("Smoke harness failed. Run tests manually for diagnostics.")


def main() -> int:
    verify_scaffold()
    verify_imports()
    verify_env_contract()
    verify_harness()
    print("Bootstrap verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
