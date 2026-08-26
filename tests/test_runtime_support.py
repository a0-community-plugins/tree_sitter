from usr.plugins.tree_sitter.helpers import runtime_support


class _Config:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _Runtime:
    ProcessConfig = _Config

    @staticmethod
    def process(source, config):
        assert config.kwargs["language"] == "python"
        return {
            "language": "python",
            "structure": [{
                "name": "Example", "kind": "Class",
                "span": {"start_line": 0, "end_line": 4, "start_column": 0, "end_column": 1},
                "children": [{
                    "name": "run", "kind": "Method",
                    "span": {"start_line": 1, "end_line": 2, "start_column": 4, "end_column": 8},
                    "children": [],
                }],
            }],
            "imports": [], "exports": [],
            "symbols": [{
                "name": "Example", "kind": "Class",
                "span": {"start_line": 0, "end_line": 0, "start_column": 6, "end_column": 13},
            }],
            "diagnostics": [],
            "chunks": [{"content": source, "start_line": 0, "end_line": 2}],
            "metrics": {"error_count": 0},
        }


class _LanguageRuntime:
    @staticmethod
    def has_language(language):
        return language in {"bash", "csharp", "python", "zsh"}


def test_language_aliases_use_pack_canonical_names(monkeypatch):
    monkeypatch.setattr(runtime_support, "runtime_is_available", lambda: True)
    monkeypatch.setattr(runtime_support, "require_runtime", lambda: _LanguageRuntime())

    assert runtime_support.canonicalize_language("cs") == "csharp"
    assert runtime_support.canonicalize_language("c_sharp") == "csharp"
    assert runtime_support.canonicalize_language("c#") == "csharp"
    assert runtime_support.canonicalize_language("zsh") == "zsh"


def test_analyze_source_normalizes_structure_and_one_based_spans(monkeypatch):
    monkeypatch.setattr(runtime_support, "require_runtime", lambda: _Runtime())
    result = runtime_support.analyze_source(
        "class Example:\n    def run(self): pass\n",
        "python", chunk_max_chars=1000, parse_timeout_ms=1000,
    )

    assert [item["qualname"] for item in result["definitions"]] == ["Example", "Example.run"]
    assert result["definitions"][0]["start_line"] == 1
    assert result["definitions"][1]["start_line"] == 2
    assert result["symbols"][0]["start_col"] == 7
    assert result["chunks"][0]["start_line"] == 1


def test_native_field_serializer_handles_extension_objects_without_dict():
    NativeSpan = type("Span", (), {
        "start_byte": 0, "end_byte": 4, "start_line": 0, "start_column": 1,
        "end_line": 0, "end_column": 5,
    })

    assert runtime_support._to_jsonable(NativeSpan())["end_column"] == 5
