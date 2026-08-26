"""Agent Zero lifecycle hooks for configuration and framework-runtime setup."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from usr.plugins.tree_sitter.helpers.config import normalize_config


PLUGIN_ROOT = Path(__file__).resolve().parent
REQUIREMENTS = PLUGIN_ROOT / "requirements.txt"
INSTALL_TIMEOUT_SECONDS = 300
_INSTALL_LOCK = threading.Lock()
_REQUIREMENT_PATTERN = re.compile(
    r"^tree-sitter-language-pack==(?P<version>[A-Za-z0-9_.+-]+)$"
)


def get_plugin_config(default: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
    """Normalize framework-resolved configuration at the plugin boundary."""
    return normalize_config(default)


def save_plugin_config(settings: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
    """Normalize settings before Agent Zero persists them."""
    return normalize_config(settings)


def dependency_status() -> dict[str, Any]:
    """Report framework-runtime readiness without installing or downloading anything."""
    expected = _expected_version()
    installed = _installed_version("tree-sitter-language-pack")
    pack_present = importlib.util.find_spec("tree_sitter_language_pack") is not None
    binding_present = importlib.util.find_spec("tree_sitter") is not None
    missing_api: list[str] = []
    if pack_present:
        try:
            package = importlib.import_module("tree_sitter_language_pack")
            missing_api = [
                name for name in ("process", "get_parser", "get_language", "get_tags_query")
                if not callable(getattr(package, name, None))
            ]
        except Exception as exc:
            missing_api = [f"import_error:{type(exc).__name__}"]
    ready = bool(
        expected
        and installed == expected
        and pack_present
        and binding_present
        and not missing_api
    )
    return {
        "ready": ready,
        "expected_version": expected,
        "installed_version": installed,
        "language_pack_present": pack_present,
        "tree_sitter_binding_present": binding_present,
        "missing_api": missing_api,
        "requirements": str(REQUIREMENTS),
        "python": sys.executable,
    }


def runtime_report() -> dict[str, Any]:
    """Combine package compatibility with the parser runtime's live status."""
    from usr.plugins.tree_sitter.helpers.runtime_support import runtime_status

    runtime = runtime_status()
    dependency = dependency_status()
    return {
        **runtime,
        "ready": bool(runtime.get("ready") and dependency["ready"]),
        "runtime_ready": bool(runtime.get("ready")),
        "dependency": dependency,
    }


def install() -> dict[str, Any]:
    """Provision and validate native parsers in Agent Zero's framework runtime."""
    with _INSTALL_LOCK:
        before = dependency_status()
        if before["ready"]:
            parser_matrix = _verify_parser_runtime()
            return {
                "ok": True,
                "execution_performed": False,
                "parser_matrix": parser_matrix,
                **before,
            }

        command = _install_command()
        result = subprocess.run(
            command,
            cwd=PLUGIN_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=INSTALL_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "dependency installer failed").strip()
            raise RuntimeError(
                f"Tree-sitter dependency installation failed with exit code "
                f"{result.returncode}: {detail[-2_000:]}"
            )

        importlib.invalidate_caches()
        after = dependency_status()
        if not after["ready"]:
            raise RuntimeError(f"Tree-sitter runtime is incomplete after installation: {after}")
        parser_matrix = _verify_parser_runtime()
        return {
            "ok": True,
            "execution_performed": True,
            "installer": "uv" if Path(command[0]).name == "uv" else "pip",
            "parser_matrix": parser_matrix,
            **after,
        }


def pre_update() -> dict[str, Any]:
    """Observe readiness before Git update; post-update install uses the new requirements."""
    return {
        "ok": True,
        "execution_performed": False,
        "phase": "pre_update",
        "dependency_status": dependency_status(),
    }


def uninstall() -> dict[str, Any]:
    """Leave shared Python packages intact; Agent Zero removes plugin-owned data with the plugin."""
    return {
        "ok": True,
        "execution_performed": False,
        "shared_dependency_retained": True,
    }


def _expected_version() -> str:
    if not REQUIREMENTS.is_file():
        raise RuntimeError(f"Tree-sitter requirements file not found: {REQUIREMENTS}")
    matches = []
    for raw_line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _REQUIREMENT_PATTERN.fullmatch(line)
        if match:
            matches.append(match.group("version"))
        else:
            raise RuntimeError(f"Unsupported Tree-sitter requirement: {line}")
    if len(matches) != 1:
        raise RuntimeError("requirements.txt must contain one exact tree-sitter-language-pack pin")
    return matches[0]


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _install_command() -> list[str]:
    _expected_version()
    if uv := shutil.which("uv"):
        return [uv, "pip", "install", "--python", sys.executable, "-r", str(REQUIREMENTS)]
    return [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]


def _verify_parser_runtime() -> dict[str, Any]:
    from usr.plugins.tree_sitter.helpers.parser_matrix import verify_parser_matrix

    return verify_parser_matrix()
