from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

RUNTIME_PACKAGE = "tree_sitter_language_pack"
QUERY_PACKAGE = "tree_sitter"

_LANGUAGE_ALIASES = {
    "bash": "bash",
    "c": "c",
    "cc": "cpp",
    "cpp": "cpp",
    "cxx": "cpp",
    "c++": "cpp",
    "css": "css",
    "htm": "html",
    "html": "html",
    "javascript": "javascript",
    "js": "javascript",
    "json": "json",
    "jsonc": "json",
    "jsx": "javascript",
    "markdown": "markdown",
    "md": "markdown",
    "py": "python",
    "python": "python",
    "rs": "rust",
    "rust": "rust",
    "sql": "sql",
    "swift": "swift",
    "ts": "typescript",
    "tsx": "tsx",
    "typescript": "typescript",
    "yaml": "yaml",
    "yml": "yaml",
    "zig": "zig",
}

SUPPORTED_LANGUAGES = sorted(set(_LANGUAGE_ALIASES.values()))


class TreeSitterRuntimeError(RuntimeError):
    pass


def _normalize_language_key(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("."):
        normalized = normalized[1:]
    normalized = normalized.replace(" ", "").replace("-", "").replace("_", "")
    if normalized == "c++":
        return normalized
    return normalized


def canonicalize_language(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _normalize_language_key(value)
    if normalized in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[normalized]
    suffix = Path(value).suffix
    if suffix:
        normalized_suffix = _normalize_language_key(suffix)
        return _LANGUAGE_ALIASES.get(normalized_suffix)
    return None


def detect_language_from_path(path: str | Path) -> str | None:
    file_path = Path(path)
    for suffix in reversed(file_path.suffixes):
        canonical = canonicalize_language(suffix)
        if canonical:
            return canonical
    return canonicalize_language(file_path.name)


def runtime_is_available() -> bool:
    return importlib.util.find_spec(RUNTIME_PACKAGE) is not None


def query_runtime_is_available() -> bool:
    return importlib.util.find_spec(QUERY_PACKAGE) is not None


def require_runtime() -> Any:
    try:
        return importlib.import_module(RUNTIME_PACKAGE)
    except ModuleNotFoundError as exc:
        raise TreeSitterRuntimeError(
            "Tree-sitter support requires the 'tree-sitter-language-pack' package. "
            "Add it to the environment or run the plugin initialize script."
        ) from exc


def require_query_runtime() -> Any:
    try:
        return importlib.import_module(QUERY_PACKAGE)
    except ModuleNotFoundError as exc:
        raise TreeSitterRuntimeError(
            "Tree-sitter query support requires the 'tree-sitter' Python package."
        ) from exc


def get_parser(language: str):
    runtime = require_runtime()
    canonical = canonicalize_language(language)
    if not canonical:
        raise TreeSitterRuntimeError(f"Unsupported Tree-sitter language: {language}")
    return runtime.get_parser(canonical)


def get_language(language: str):
    runtime = require_runtime()
    canonical = canonicalize_language(language)
    if not canonical:
        raise TreeSitterRuntimeError(f"Unsupported Tree-sitter language: {language}")
    return runtime.get_language(canonical)


def parse_source(source: str | bytes, language: str):
    parser = get_parser(language)
    payload = source if isinstance(source, bytes) else source.encode("utf-8")
    return parser.parse(payload)
