from __future__ import annotations

from dataclasses import asdict, is_dataclass
from functools import lru_cache
import importlib
import importlib.metadata
import importlib.util
from pathlib import Path
from typing import Any


RUNTIME_PACKAGE = "tree_sitter_language_pack"
QUERY_PACKAGE = "tree_sitter"

_FALLBACK_ALIASES = {
    "bash": "bash", "sh": "bash",
    "c": "c", "h": "c", "cc": "cpp", "cpp": "cpp", "cxx": "cpp", "hpp": "cpp",
    "cs": "csharp", "c#": "csharp", "c_sharp": "csharp", "css": "css",
    "go": "go", "html": "html", "htm": "html",
    "java": "java", "js": "javascript", "jsx": "javascript", "json": "json",
    "kt": "kotlin", "kts": "kotlin", "lua": "lua", "md": "markdown",
    "php": "php", "py": "python", "rb": "ruby", "rs": "rust", "scala": "scala",
    "sql": "sql", "swift": "swift", "toml": "toml", "ts": "typescript", "tsx": "tsx",
    "xml": "xml", "yaml": "yaml", "yml": "yaml", "zig": "zig", "zsh": "zsh",
}

_NATIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "ProcessResult": ("language", "metrics", "structure", "imports", "exports", "comments", "docstrings", "symbols", "diagnostics", "chunks", "data"),
    "FileMetrics": ("total_lines", "code_lines", "comment_lines", "blank_lines", "total_bytes", "node_count", "error_count", "max_depth"),
    "StructureItem": ("kind", "name", "visibility", "span", "children", "decorators", "doc_comment", "signature", "body_span"),
    "ImportInfo": ("source", "items", "alias", "is_wildcard", "span"),
    "ExportInfo": ("name", "kind", "span"),
    "SymbolInfo": ("name", "kind", "span", "type_annotation", "doc"),
    "Diagnostic": ("message", "severity", "span"),
    "CodeChunk": ("content", "start_byte", "end_byte", "start_line", "end_line", "metadata"),
    "ChunkContext": ("language", "chunk_index", "total_chunks", "node_types", "context_path", "symbols_defined", "comments", "docstrings", "has_error_nodes"),
    "Span": ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column"),
}


class TreeSitterRuntimeError(RuntimeError):
    pass


def runtime_is_available() -> bool:
    return importlib.util.find_spec(RUNTIME_PACKAGE) is not None


def query_runtime_is_available() -> bool:
    return importlib.util.find_spec(QUERY_PACKAGE) is not None


def require_runtime() -> Any:
    try:
        return importlib.import_module(RUNTIME_PACKAGE)
    except ModuleNotFoundError as exc:
        raise TreeSitterRuntimeError(
            "Tree-sitter is not ready in the Agent Zero framework runtime. "
            "Install or update the plugin to provision its pinned dependency."
        ) from exc


def require_query_runtime() -> Any:
    try:
        return importlib.import_module(QUERY_PACKAGE)
    except ModuleNotFoundError as exc:
        raise TreeSitterRuntimeError("The tree-sitter Python binding is unavailable.") from exc


def runtime_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "ready": runtime_is_available() and query_runtime_is_available(),
        "language_pack_version": _package_version("tree-sitter-language-pack"),
        "tree_sitter_version": _package_version("tree-sitter"),
        "available_language_count": 0,
        "downloaded_languages": [],
        "cache_dir": None,
    }
    if not runtime_is_available():
        return status
    try:
        runtime = require_runtime()
        languages = runtime.available_languages() if hasattr(runtime, "available_languages") else []
        status["available_language_count"] = len(languages)
        if hasattr(runtime, "downloaded_languages"):
            status["downloaded_languages"] = list(runtime.downloaded_languages())
        if hasattr(runtime, "cache_dir"):
            status["cache_dir"] = str(runtime.cache_dir())
    except Exception as exc:
        status["ready"] = False
        status["error"] = str(exc)
    return status


def available_languages() -> list[str]:
    runtime = require_runtime()
    if hasattr(runtime, "available_languages"):
        return sorted(set(str(item) for item in runtime.available_languages()))
    return sorted(set(_FALLBACK_ALIASES.values()))


def bundled_query(language: str, kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized not in {"tags", "locals", "highlights", "injections", "folds", "indents"}:
        raise TreeSitterRuntimeError(
            "query_kind must be one of tags, locals, highlights, injections, folds, or indents"
        )
    getter = getattr(require_runtime(), f"get_{normalized}_query", None)
    if getter is None:
        raise TreeSitterRuntimeError(f"The installed language pack does not expose {normalized} queries")
    try:
        query = getter(language)
    except Exception as exc:
        raise TreeSitterRuntimeError(f"Unable to load the {normalized} query for {language}: {exc}") from exc
    if not query:
        raise TreeSitterRuntimeError(f"No bundled {normalized} query is available for {language}")
    return str(query)


def canonicalize_language(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().lower().removeprefix(".")
    candidate = _FALLBACK_ALIASES.get(candidate, candidate.replace("-", "_"))
    if runtime_is_available():
        runtime = require_runtime()
        if hasattr(runtime, "has_language"):
            try:
                return candidate if runtime.has_language(candidate) else None
            except Exception:
                pass
    return candidate if candidate in set(_FALLBACK_ALIASES.values()) else None


def detect_language(path: str | Path, source: str | None = None) -> str | None:
    file_path = Path(path)
    if runtime_is_available():
        runtime = require_runtime()
        for detector, argument in (
            (getattr(runtime, "detect_language_from_path", None), str(file_path)),
            (getattr(runtime, "detect_language", None), str(file_path)),
        ):
            if detector:
                try:
                    if detected := detector(argument):
                        return str(detected)
                except Exception:
                    pass
        if source and hasattr(runtime, "detect_language_from_content"):
            try:
                if detected := runtime.detect_language_from_content(source):
                    return str(detected)
            except Exception:
                pass
    if file_path.name == "Dockerfile":
        return "dockerfile"
    for suffix in reversed(file_path.suffixes):
        if language := canonicalize_language(suffix):
            return language
    return canonicalize_language(file_path.name)


def get_parser(language: str):
    runtime = require_runtime()
    canonical = canonicalize_language(language) or language.strip().lower()
    try:
        return runtime.get_parser(canonical)
    except Exception as exc:
        raise TreeSitterRuntimeError(f"Unable to load Tree-sitter parser for {canonical}: {exc}") from exc


def get_language(language: str):
    runtime = require_runtime()
    canonical = canonicalize_language(language) or language.strip().lower()
    try:
        return runtime.get_language(canonical)
    except Exception as exc:
        raise TreeSitterRuntimeError(f"Unable to load Tree-sitter language {canonical}: {exc}") from exc


def parse_source(source: str | bytes, language: str):
    payload = source if isinstance(source, bytes) else source.encode("utf-8")
    try:
        return get_parser(language).parse(payload)
    except TreeSitterRuntimeError:
        raise
    except Exception as exc:
        raise TreeSitterRuntimeError(f"Tree-sitter parse failed for {language}: {exc}") from exc


def analyze_source(
    source: str,
    language: str,
    *,
    chunk_max_chars: int,
    parse_timeout_ms: int,
) -> dict[str, Any]:
    runtime = require_runtime()
    canonical = canonicalize_language(language) or language
    if not hasattr(runtime, "process") or not hasattr(runtime, "ProcessConfig"):
        return _analyze_low_level(source, canonical, chunk_max_chars)
    try:
        result = runtime.process(
            source,
            runtime.ProcessConfig(
                language=canonical,
                structure=True,
                imports=True,
                exports=True,
                comments=False,
                docstrings=True,
                symbols=True,
                diagnostics=True,
                chunk_max_size=chunk_max_chars,
                max_source_bytes=len(source.encode("utf-8")) + 1,
                parse_timeout_ms=parse_timeout_ms,
            ),
        )
    except Exception as exc:
        raise TreeSitterRuntimeError(f"Tree-sitter analysis failed for {canonical}: {exc}") from exc

    raw = _to_jsonable(result)
    structure = raw.get("structure", []) if isinstance(raw, dict) else []
    return {
        "language": str(raw.get("language") or canonical),
        "definitions": _flatten_structure(structure),
        "imports": _normalize_spans(raw.get("imports", [])),
        "exports": _normalize_spans(raw.get("exports", [])),
        "symbols": _normalize_spans(raw.get("symbols", [])),
        "diagnostics": _normalize_spans(raw.get("diagnostics", [])),
        "chunks": _normalize_chunks(raw.get("chunks", [])),
        "metrics": raw.get("metrics", {}),
    }


def run_query(
    source_bytes: bytes,
    language: str,
    root_node: Any,
    query_source: str,
    limit: int,
    *,
    timeout_ms: int = 3_000,
    max_capture_chars: int = 4_000,
) -> list[dict[str, Any]]:
    query_module = require_query_runtime()
    try:
        query = _compile_query(language, query_source)
        cursor = query_module.QueryCursor(query)
        if hasattr(cursor, "match_limit"):
            cursor.match_limit = max(1_000, limit * 100)
        if hasattr(cursor, "timeout_micros"):
            cursor.timeout_micros = max(1, timeout_ms) * 1_000
        matches = cursor.matches(root_node)
    except Exception as exc:
        raise TreeSitterRuntimeError(f"Invalid Tree-sitter query for {language}: {exc}") from exc
    result: list[dict[str, Any]] = []
    for pattern_index, captures in matches:
        capture_payload: dict[str, list[dict[str, Any]]] = {}
        for name, nodes in captures.items():
            node_list = nodes if isinstance(nodes, list) else [nodes]
            capture_payload[str(name)] = [
                _node_capture(source_bytes, node, max_capture_chars=max_capture_chars)
                for node in node_list
            ]
        result.append({"pattern_index": int(pattern_index), "captures": capture_payload})
        if len(result) >= limit:
            break
    return result


@lru_cache(maxsize=128)
def _compile_query(language: str, query_source: str):
    query_module = require_query_runtime()
    return query_module.Query(get_language(language), query_source)


def _analyze_low_level(source: str, language: str, chunk_max_chars: int) -> dict[str, Any]:
    from .navigation_engine import build_syntax_chunks, collect_references, collect_symbols

    tree = parse_source(source, language)
    source_bytes = source.encode("utf-8")
    definitions = [asdict(item) for item in collect_symbols(tree.root_node, source_bytes, "", language)]
    symbols: list[dict[str, Any]] = []
    for name in sorted({item["name"] for item in definitions}):
        symbols.extend(collect_references(tree.root_node, source_bytes, "", language, name))
    return {
        "language": language,
        "definitions": definitions,
        "imports": [], "exports": [], "symbols": symbols, "diagnostics": [],
        "chunks": [asdict(item) for item in build_syntax_chunks(
            tree.root_node, source, "", language, max_chars=chunk_max_chars
        )],
        "metrics": {},
    }


def _flatten_structure(items: Any, parents: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        children = item.get("children", [])
        if name:
            record = dict(item)
            record.pop("children", None)
            record["kind"] = _enum_text(record.get("kind", "other"))
            record["qualname"] = ".".join((*parents, name))
            record.update(_one_based_span(record.pop("span", None)))
            result.append(record)
            result.extend(_flatten_structure(children, (*parents, name)))
        else:
            result.extend(_flatten_structure(children, parents))
    return result


def _normalize_spans(items: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        record = {key: _enum_text(value) for key, value in item.items() if key != "span"}
        record.update(_one_based_span(item.get("span")))
        result.append(record)
    return result


def _normalize_chunks(items: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        record = {key: _enum_text(value) for key, value in item.items()}
        if "start_line" in record:
            record["start_line"] = int(record["start_line"]) + 1
        if "end_line" in record:
            record["end_line"] = int(record["end_line"]) + 1
        result.append(record)
    return result


def _one_based_span(span: Any) -> dict[str, int]:
    if not isinstance(span, dict):
        return {}
    return {
        "start_line": int(span.get("start_line", 0)) + 1,
        "end_line": int(span.get("end_line", 0)) + 1,
        "start_col": int(span.get("start_column", 0)) + 1,
        "end_col": int(span.get("end_column", 0)) + 1,
        "start_byte": int(span.get("start_byte", 0)),
        "end_byte": int(span.get("end_byte", 0)),
    }


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "value"):
        try:
            return _to_jsonable(value.value)
        except Exception:
            pass
    native_fields = _NATIVE_FIELDS.get(type(value).__name__)
    if native_fields:
        return {
            name: _to_jsonable(getattr(value, name))
            for name in native_fields
            if hasattr(value, name)
        }
    names = getattr(value, "__match_args__", ()) or getattr(value, "__slots__", ())
    if names:
        return {str(name): _to_jsonable(getattr(value, name)) for name in names if hasattr(value, name)}
    if hasattr(value, "__dict__"):
        return {str(key): _to_jsonable(item) for key, item in vars(value).items() if not key.startswith("_")}
    return str(value)


def _enum_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.rsplit(".", 1)[-1] if "." in value and " " not in value else value
    if isinstance(value, dict) and len(value) == 1:
        key, nested = next(iter(value.items()))
        return f"{key}:{nested}"
    return value


def _node_capture(source: bytes, node: Any, *, max_capture_chars: int) -> dict[str, Any]:
    text = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    truncated = len(text) > max_capture_chars
    if truncated:
        text = text[:max_capture_chars].rstrip() + "\n…"
    return {
        "type": str(node.type),
        "text": text,
        "truncated": truncated,
        "start_line": int(node.start_point[0]) + 1,
        "end_line": int(node.end_point[0]) + 1,
        "start_col": int(node.start_point[1]) + 1,
        "end_col": int(node.end_point[1]) + 1,
    }


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None
