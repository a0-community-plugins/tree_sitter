from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

from helpers import files, plugins

from .config import normalize_config
from .index_store import ProjectIndexStore
from . import runtime_support
from .runtime_support import TreeSitterRuntimeError


PLUGIN_NAME = "tree_sitter"
INDEX_ROOT = Path(files.get_abs_path("usr/plugins/tree_sitter/data/indexes"))
_WALK_EXCLUDES = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".venv", "venv", "node_modules",
    "dist", "build", "target", "vendor", "coverage", ".next", ".turbo",
}


def get_config(agent=None) -> dict[str, Any]:
    return normalize_config(plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {})


def inspect_file(
    path: str,
    *,
    language: str | None = None,
    query: str | None = None,
    query_kind: str | None = None,
    config: dict[str, Any] | None = None,
    root_path: str | None = None,
) -> dict[str, Any]:
    cfg = normalize_config(config) if config is not None else get_config()
    file_path = resolve_file_path(path, root_path=root_path, allow_outside=cfg["allow_outside_project"])
    source_bytes = file_path.read_bytes()
    if len(source_bytes) > cfg["max_file_bytes"]:
        raise TreeSitterRuntimeError(
            f"File exceeds max_file_bytes ({cfg['max_file_bytes']}): {file_path}"
        )
    try:
        source = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TreeSitterRuntimeError(f"Source file is not valid UTF-8: {file_path}") from exc
    selected = runtime_support.canonicalize_language(language) if language else None
    selected = selected or runtime_support.detect_language(file_path, source)
    if not selected:
        raise TreeSitterRuntimeError(f"Could not infer a supported language for {file_path.name}")
    analysis = runtime_support.analyze_source(
        source,
        selected,
        chunk_max_chars=cfg["max_chunk_chars"],
        parse_timeout_ms=cfg["parse_timeout_ms"],
    )
    analysis["path"] = str(file_path)
    if query_kind and not query:
        query = runtime_support.bundled_query(selected, query_kind)
    if query:
        tree = runtime_support.parse_source(source_bytes, selected)
        analysis["query_matches"] = runtime_support.run_query(
            source_bytes, selected, tree.root_node, query, cfg["max_query_matches"],
            timeout_ms=cfg["parse_timeout_ms"], max_capture_chars=cfg["max_chunk_chars"],
        )
    return analysis


def build_index(
    root_path: str,
    *,
    agent=None,
    project_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    cfg = get_config(agent=agent)
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Index root not found: {root}")
    key = project_key_for_root(root, project_name=project_name)
    store = ProjectIndexStore(INDEX_ROOT)
    existing = {} if force else store.fingerprints(key)
    candidates, truncated = _source_files(root, cfg)
    present_paths = {str(path.relative_to(root)) for path in candidates}
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    unchanged = 0
    for file_path in candidates:
        relative = str(file_path.relative_to(root))
        try:
            stat = file_path.stat()
            fingerprint = (int(stat.st_mtime_ns), int(stat.st_size))
            if existing.get(relative) == fingerprint:
                unchanged += 1
                continue
            source_bytes = file_path.read_bytes()
            if len(source_bytes) > cfg["max_file_bytes"]:
                continue
            source = source_bytes.decode("utf-8")
            language = runtime_support.detect_language(file_path, source)
            if not language:
                continue
            analysis = runtime_support.analyze_source(
                source,
                language,
                chunk_max_chars=cfg["max_chunk_chars"],
                parse_timeout_ms=cfg["parse_timeout_ms"],
            )
            records.append({
                "path": relative,
                "language": analysis["language"],
                "mtime_ns": fingerprint[0],
                "size_bytes": fingerprint[1],
                "source_hash": hashlib.sha256(source_bytes).hexdigest(),
                "definitions": analysis.get("definitions", []),
                "symbols": analysis.get("symbols", []),
                "imports": analysis.get("imports", []),
                "diagnostics": analysis.get("diagnostics", []),
            })
        except (OSError, UnicodeDecodeError, TreeSitterRuntimeError, ValueError) as exc:
            errors.append({"path": relative, "error": str(exc)})
    manifest = store.replace_files(
        key,
        str(root),
        records,
        present_paths,
        errors=errors,
        truncated=truncated,
    )
    manifest.update({
        "changed_files": len(records),
        "unchanged_files": unchanged,
        "failed_files": len(errors),
        "candidate_files": len(candidates),
    })
    return manifest


def get_index_status(root_path: str, *, project_name: str | None = None) -> dict[str, Any] | None:
    root = Path(root_path).expanduser().resolve()
    return ProjectIndexStore(INDEX_ROOT).manifest(project_key_for_root(root, project_name=project_name))


def search_symbols(
    root_path: str,
    *,
    query: str,
    project_name: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    root = Path(root_path).expanduser().resolve()
    key = project_key_for_root(root, project_name=project_name)
    matches = ProjectIndexStore(INDEX_ROOT).search_definitions(key, query, limit=limit)
    return {"project_key": key, "root_path": str(root), "query": query, "matches": matches}


def references_for_symbol(
    root_path: str,
    *,
    symbol: str,
    project_name: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    if not symbol.strip():
        raise ValueError("symbol is required")
    root = Path(root_path).expanduser().resolve()
    key = project_key_for_root(root, project_name=project_name)
    result = ProjectIndexStore(INDEX_ROOT).references(key, symbol.strip(), limit=limit)
    result.update({"project_key": key, "root_path": str(root)})
    return result


def context_for_task(
    root_path: str,
    *,
    task: str,
    symbol: str | None = None,
    agent=None,
    project_name: str | None = None,
) -> dict[str, Any]:
    cfg = get_config(agent=agent)
    root = Path(root_path).expanduser().resolve()
    if cfg["auto_refresh_index"]:
        build_index(str(root), agent=agent, project_name=project_name)
    key = project_key_for_root(root, project_name=project_name)
    store = ProjectIndexStore(INDEX_ROOT)
    terms = _search_terms(task, symbol)
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for term in terms:
        for match in store.search_definitions(key, term, limit=cfg["context_max_results"]):
            identity = (str(match["path"]), int(match["start_line"]), str(match["qualname"]))
            if identity in seen:
                continue
            seen.add(identity)
            matches.append(match)
            if len(matches) >= cfg["context_max_results"]:
                break
        if len(matches) >= cfg["context_max_results"]:
            break
    snippets: list[dict[str, Any]] = []
    used_chars = 0
    for match in matches:
        snippet = _snippet_for_match(root, match, cfg["index_snippet_chars"])
        if used_chars + len(snippet["text"]) > cfg["context_max_chars"]:
            break
        snippets.append(snippet)
        used_chars += len(snippet["text"])
    paths = sorted({str(item["path"]) for item in snippets})
    references = store.references(key, symbol.strip(), limit=cfg["context_max_results"] * 4) if symbol else None
    return {
        "project_key": key,
        "root_path": str(root),
        "task": task,
        "search_terms": terms,
        "definitions": snippets,
        "imports": store.imports_for_paths(key, paths),
        "references": references,
        "index": store.manifest(key),
        "truncated": len(snippets) < len(matches),
        "context_chars": used_chars,
    }


def diagnostics_for_files(
    paths: Iterable[str],
    *,
    root_path: str | None,
    agent=None,
) -> dict[str, Any]:
    cfg = get_config(agent=agent)
    results: list[dict[str, Any]] = []
    for path in paths:
        inspection = inspect_file(path, config=cfg, root_path=root_path)
        results.append({
            "path": inspection["path"],
            "language": inspection["language"],
            "diagnostics": inspection.get("diagnostics", []),
            "metrics": inspection.get("metrics", {}),
        })
    return {
        "files": results,
        "diagnostic_count": sum(len(item["diagnostics"]) for item in results),
        "clean": all(not item["diagnostics"] for item in results),
    }


def scope_for_position(path: str, *, line: int, column: int, language: str | None = None, root_path: str | None = None) -> dict[str, Any]:
    inspection = inspect_file(path, language=language, root_path=root_path)
    candidates = [
        item for item in inspection.get("definitions", [])
        if (int(item.get("start_line", 1)), int(item.get("start_col", 1))) <= (line, column)
        and (int(item.get("end_line", 1)), int(item.get("end_col", 1))) >= (line, column)
    ]
    candidates.sort(key=lambda item: (int(item["end_line"]) - int(item["start_line"]), int(item["end_col"]) - int(item["start_col"])))
    return {
        "path": inspection["path"], "language": inspection["language"],
        "line": line, "column": column, "scope": candidates[0] if candidates else None,
    }


def resolve_root_path(explicit_root: str | None = None, *, context=None) -> tuple[str, str | None]:
    if explicit_root:
        root = Path(explicit_root).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Repository root not found: {root}")
        return str(root), None
    if context is not None:
        from helpers import projects

        project_name = projects.get_context_project_name(context)
        if project_name:
            return str(Path(projects.get_project_folder(project_name)).resolve()), project_name
    raise TreeSitterRuntimeError("Provide root_path or activate an Agent Zero project.")


def resolve_file_path(path: str, *, root_path: str | None, allow_outside: bool) -> Path:
    if not path.strip():
        raise ValueError("path is required")
    root = Path(root_path).expanduser().resolve() if root_path else None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and root:
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"File not found: {candidate}")
    if root and not allow_outside and not candidate.is_relative_to(root):
        raise ValueError(f"File is outside the active repository root: {candidate}")
    return candidate


def project_key_for_root(root_path: str | Path, *, project_name: str | None = None) -> str:
    if project_name:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "-", project_name).strip("-")
        return f"project-{safe}" if safe else "project"
    resolved = str(Path(root_path).expanduser().resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:20]


def _source_files(root: Path, cfg: dict[str, Any]) -> tuple[list[Path], bool]:
    paths = _git_files(root, include_untracked=cfg["index_include_untracked"])
    if paths is None:
        paths = _walk_files(root, include_hidden=cfg["index_hidden_files"])
    selected: list[Path] = []
    seen: set[Path] = set()
    max_files = cfg["index_max_files"]
    for path in paths:
        if path in seen or not path.is_file() or path.is_symlink():
            continue
        seen.add(path)
        if not cfg["index_hidden_files"] and any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size > cfg["max_file_bytes"]:
            continue
        if not runtime_support.detect_language(path):
            continue
        selected.append(path)
        if len(selected) >= max_files:
            return sorted(selected), True
    return sorted(selected), False


def _git_files(root: Path, *, include_untracked: bool) -> list[Path] | None:
    command = ["git", "-C", str(root), "ls-files", "-z", "--cached"]
    if include_untracked:
        command.extend(["--others", "--exclude-standard"])
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        return None
    return [root / item.decode("utf-8", errors="surrogateescape") for item in result.stdout.split(b"\0") if item]


def _walk_files(root: Path, *, include_hidden: bool) -> list[Path]:
    result: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [
            name for name in dirs
            if name not in _WALK_EXCLUDES and (include_hidden or not name.startswith("."))
        ]
        result.extend(Path(current) / name for name in names if include_hidden or not name.startswith("."))
    return result


def _search_terms(task: str, symbol: str | None) -> list[str]:
    result: list[str] = []
    if symbol and symbol.strip():
        result.append(symbol.strip())
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", task)
    ignored = {"the", "and", "for", "with", "from", "this", "that", "into", "when", "where", "change", "update", "implement", "fix"}
    for token in tokens:
        if token.lower() in ignored or token in result:
            continue
        result.append(token)
    return result[:12]


def _snippet_for_match(root: Path, match: dict[str, Any], max_chars: int) -> dict[str, Any]:
    path = root / str(match["path"])
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(match["start_line"]) - 2)
    end = min(len(lines), int(match["end_line"]) + 2)
    text = "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n…"
    return {
        "path": str(match["path"]), "language": match.get("language"),
        "name": match.get("name"), "qualname": match.get("qualname"), "kind": match.get("kind"),
        "start_line": int(match["start_line"]), "end_line": int(match["end_line"]), "text": text,
    }
