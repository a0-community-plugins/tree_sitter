from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import time
import types

import pytest


files_stub = types.ModuleType("helpers.files")
files_stub.get_abs_path = lambda path: str(Path.cwd() / path)
plugins_stub = types.ModuleType("helpers.plugins")
projects_stub = types.ModuleType("helpers.projects")
sys.modules.setdefault("helpers.files", files_stub)
sys.modules.setdefault("helpers.plugins", plugins_stub)
sys.modules.setdefault("helpers.projects", projects_stub)

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.config import normalize_config


def _analysis(source: str, language: str, **_kwargs) -> dict:
    name = "beta" if "beta" in source else "alpha"
    return {
        "language": language,
        "definitions": [{
            "name": name, "qualname": name, "kind": "Function",
            "start_line": 1, "end_line": 1, "start_col": 5, "end_col": 10,
        }],
        "symbols": [{
            "name": name, "kind": "Function",
            "start_line": 1, "end_line": 1, "start_col": 5, "end_col": 10,
        }],
        "imports": [], "diagnostics": [], "chunks": [], "metrics": {},
    }


@pytest.fixture
def service(tmp_path, monkeypatch):
    config = normalize_config({"index_max_files": 100, "auto_refresh_index": False})
    monkeypatch.setattr(plugin_service, "INDEX_ROOT", tmp_path / "indexes")
    monkeypatch.setattr(plugin_service, "get_config", lambda agent=None: config)
    monkeypatch.setattr(plugin_service.runtime_support, "detect_language", lambda path, source=None: "python" if Path(path).suffix == ".py" else None)
    monkeypatch.setattr(plugin_service.runtime_support, "analyze_source", _analysis)
    return tmp_path / "repo"


def test_build_index_reuses_unchanged_files_and_refreshes_changes(service):
    service.mkdir()
    source = service / "sample.py"
    source.write_text("def alpha(): pass\n", encoding="utf-8")

    first = plugin_service.build_index(str(service))
    second = plugin_service.build_index(str(service))
    source.write_text("def beta(): pass\n", encoding="utf-8")
    third = plugin_service.build_index(str(service))

    assert first["changed_files"] == 1
    assert second["changed_files"] == 0
    assert second["unchanged_files"] == 1
    assert third["changed_files"] == 1
    assert plugin_service.search_symbols(str(service), query="beta")["matches"][0]["name"] == "beta"


def test_concurrent_builds_serialize_per_project(service, monkeypatch):
    service.mkdir()
    (service / "sample.py").write_text("def alpha(): pass\n", encoding="utf-8")
    calls = 0
    calls_lock = threading.Lock()

    def slow_analysis(source, language, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return _analysis(source, language, **kwargs)

    monkeypatch.setattr(plugin_service.runtime_support, "analyze_source", slow_analysis)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: plugin_service.build_index(str(service)), range(2)))

    assert calls == 1
    assert sorted(result["changed_files"] for result in results) == [0, 1]


def test_context_returns_bounded_definition_snippets(service):
    service.mkdir()
    (service / "sample.py").write_text("def alpha(): pass\n", encoding="utf-8")
    plugin_service.build_index(str(service))

    result = plugin_service.context_for_task(str(service), task="change alpha behavior")

    assert result["definitions"][0]["name"] == "alpha"
    assert "def alpha" in result["definitions"][0]["text"]


def test_resolve_file_path_rejects_escape(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("pass\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside"):
        plugin_service.resolve_file_path(str(outside), root_path=str(root), allow_outside=False)
