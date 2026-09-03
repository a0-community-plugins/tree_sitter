import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers.extract_tools import normalize_tool_request
from helpers.responses_tools import _schema_from_prompt
from usr.plugins.tree_sitter.tools import tree_sitter as module


PROMPT = Path(__file__).parents[1] / "prompts" / "agent.system.tool.tree_sitter.md"


def test_tool_dispatches_framework_normalized_action_when_method_is_none(monkeypatch):
    tool_name, tool_args = normalize_tool_request(
        {
            "tool_name": "tree_sitter",
            "tool_args": {"method": "status"},
        }
    )
    tool = module.TreeSitter(
        agent=SimpleNamespace(context=None),
        name=tool_name,
        method=None,
        args=tool_args,
        message="",
        loop_data=None,
    )
    monkeypatch.setattr(tool, "_root", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(module.plugin_service, "get_config", lambda agent=None: {})
    monkeypatch.setattr(module.hooks, "runtime_report", lambda: {"ready": True})

    response = asyncio.run(tool.execute(**tool_args))

    assert json.loads(response.message) == {"runtime": {"ready": True}}


def test_native_tool_schema_requires_a_supported_action():
    schema = _schema_from_prompt(PROMPT.read_text(encoding="utf-8"))

    assert schema["required"] == ["action"]
    assert set(schema["properties"]["action"]["enum"]) == {
        "chunks",
        "context",
        "diagnostics",
        "index",
        "inspect",
        "languages",
        "lookup",
        "overview",
        "query",
        "references",
        "scope",
        "search",
        "status",
        "symbols",
    }
    assert schema["properties"]["query_kind"]["enum"] == [
        "tags",
        "locals",
        "highlights",
        "injections",
        "folds",
        "indents",
    ]


@pytest.mark.parametrize(
    ("stored_args", "legacy_method", "call_args", "expected"),
    [
        ({}, None, {"action": "status"}, "status"),
        ({}, None, {"method": "languages"}, "languages"),
        ({"action": "overview"}, None, {}, "overview"),
        ({"method": "symbols"}, None, {}, "symbols"),
        ({}, "chunks", {}, "chunks"),
        (
            {"action": "overview", "method": "symbols"},
            "chunks",
            {"action": "status", "method": "languages"},
            "status",
        ),
    ],
)
def test_method_resolution_preserves_compatibility_and_action_precedence(
    stored_args, legacy_method, call_args, expected
):
    tool = module.TreeSitter(
        agent=SimpleNamespace(context=None),
        name="tree_sitter",
        method=legacy_method,
        args=stored_args,
        message="",
        loop_data=None,
    )

    assert module._current_method(tool, call_args) == expected
