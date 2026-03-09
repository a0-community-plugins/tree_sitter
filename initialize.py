from __future__ import annotations

import subprocess
import sys


def main() -> int:
    package = "tree-sitter-language-pack"
    print(f"Installing {package}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        check=False,
    )
    if result.returncode == 0:
        print("Tree-sitter runtime installed successfully.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
