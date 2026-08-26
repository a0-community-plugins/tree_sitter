from __future__ import annotations

from typing import Any


DEFAULTS: dict[str, Any] = {
    "max_file_bytes": 1_000_000,
    "max_chunk_chars": 4_000,
    "max_query_matches": 100,
    "parse_timeout_ms": 3_000,
    "index_hidden_files": False,
    "index_include_untracked": True,
    "index_max_files": 5_000,
    "index_snippet_chars": 800,
    "context_max_chars": 16_000,
    "context_max_results": 16,
    "auto_refresh_index": True,
    "allow_outside_project": False,
}


def normalize_config(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    return {
        "max_file_bytes": _bounded_int(raw, "max_file_bytes", 10_000, 20_000_000),
        "max_chunk_chars": _bounded_int(raw, "max_chunk_chars", 500, 50_000),
        "max_query_matches": _bounded_int(raw, "max_query_matches", 1, 2_000),
        "parse_timeout_ms": _bounded_int(raw, "parse_timeout_ms", 100, 30_000),
        "index_hidden_files": _as_bool(raw.get("index_hidden_files"), False),
        "index_include_untracked": _as_bool(raw.get("index_include_untracked"), True),
        "index_max_files": _bounded_int(raw, "index_max_files", 1, 100_000),
        "index_snippet_chars": _bounded_int(raw, "index_snippet_chars", 100, 10_000),
        "context_max_chars": _bounded_int(raw, "context_max_chars", 1_000, 100_000),
        "context_max_results": _bounded_int(raw, "context_max_results", 1, 200),
        "auto_refresh_index": _as_bool(raw.get("auto_refresh_index"), True),
        "allow_outside_project": _as_bool(raw.get("allow_outside_project"), False),
    }


def _bounded_int(raw: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw.get(key, DEFAULTS[key]))
    except (TypeError, ValueError):
        value = int(DEFAULTS[key])
    return max(minimum, min(value, maximum))


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)
