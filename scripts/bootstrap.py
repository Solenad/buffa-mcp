from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    run([sys.executable, "-m", "pip", "install", "-U", "pip"])
    run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])
    run([sys.executable, "scripts/verify_bootstrap.py"])
    print("Bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
