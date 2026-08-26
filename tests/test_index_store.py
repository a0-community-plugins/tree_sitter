from usr.plugins.tree_sitter.helpers.index_store import ProjectIndexStore


def _record(path: str, name: str) -> dict:
    return {
        "path": path,
        "language": "python",
        "mtime_ns": 10,
        "size_bytes": 20,
        "source_hash": "abc",
        "definitions": [{
            "name": name, "qualname": name, "kind": "Function",
            "start_line": 1, "end_line": 2, "start_col": 1, "end_col": 8,
        }],
        "symbols": [
            {"name": name, "kind": "Function", "start_line": 1, "end_line": 1, "start_col": 5, "end_col": 8},
            {"name": name, "kind": "Variable", "start_line": 4, "end_line": 4, "start_col": 1, "end_col": 4},
        ],
        "imports": [{"source": "pathlib", "items": ["Path"], "start_line": 1}],
        "diagnostics": [],
    }


def test_store_supports_manifest_search_and_references(tmp_path):
    store = ProjectIndexStore(tmp_path)
    manifest = store.replace_files(
        "project", str(tmp_path), [_record("a.py", "alpha")], {"a.py"},
        errors=[], truncated=False,
    )

    assert manifest["file_count"] == 1
    assert manifest["definition_count"] == 1
    assert store.fingerprints("project") == {"a.py": (10, 20)}
    assert store.search_definitions("project", "alp")[0]["qualname"] == "alpha"
    references = store.references("project", "alpha")
    assert len(references["definitions"]) == 1
    assert len(references["references"]) == 1


def test_store_removes_files_missing_from_refresh(tmp_path):
    store = ProjectIndexStore(tmp_path)
    store.replace_files(
        "project", str(tmp_path), [_record("a.py", "alpha"), _record("b.py", "beta")],
        {"a.py", "b.py"}, errors=[], truncated=False,
    )
    manifest = store.replace_files(
        "project", str(tmp_path), [], {"a.py"}, errors=[], truncated=False,
    )

    assert manifest["file_count"] == 1
    assert store.search_definitions("project", "beta") == []
