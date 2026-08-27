from __future__ import annotations

import asyncio
from types import SimpleNamespace

from usr.plugins.tree_sitter.extensions.python.message_loop_prompts_after._54_tree_sitter_context import (
    EXTRA_KEY,
    IncludeTreeSitterContext,
)
from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class _Message:
    def output_text(self):
        return "Refactor the parser registry"


class _Log:
    def __init__(self):
        self.entries = []

    def log(self, **entry):
        self.entries.append(entry)


class _Agent:
    def __init__(self):
        self.context = SimpleNamespace(log=_Log())

    def read_prompt(self, _name, **values):
        return values["tree_sitter_context"]


def _loop_data(iteration):
    return SimpleNamespace(
        iteration=iteration,
        user_message=_Message(),
        extras_persistent={},
    )


def test_first_model_call_receives_automatic_project_context(monkeypatch):
    agent = _Agent()
    loop_data = _loop_data(0)
    calls = []
    monkeypatch.setattr(
        plugin_service,
        "get_config",
        lambda agent=None: {"auto_context_enabled": True},
    )
    monkeypatch.setattr(
        plugin_service,
        "resolve_root_path",
        lambda context=None: ("/project", "Project"),
    )

    def context_for_task(root_path, **kwargs):
        calls.append((root_path, kwargs))
        return {
            "root_path": root_path,
            "definitions": [{"name": "ParserRegistry"}],
            "imports": [],
            "references": None,
            "index": {"file_count": 12},
            "truncated": False,
            "context_chars": 120,
        }

    monkeypatch.setattr(plugin_service, "context_for_task", context_for_task)

    asyncio.run(IncludeTreeSitterContext(agent=agent).execute(loop_data=loop_data))

    assert calls[0][0] == "/project"
    assert calls[0][1]["task"] == "Refactor the parser registry"
    assert '"ParserRegistry"' in loop_data.extras_persistent[EXTRA_KEY]
    assert agent.context.log.entries == []


def test_automatic_context_can_be_disabled(monkeypatch):
    agent = _Agent()
    loop_data = _loop_data(0)
    monkeypatch.setattr(
        plugin_service,
        "get_config",
        lambda agent=None: {"auto_context_enabled": False},
    )
    monkeypatch.setattr(
        plugin_service,
        "context_for_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    asyncio.run(IncludeTreeSitterContext(agent=agent).execute(loop_data=loop_data))

    assert EXTRA_KEY not in loop_data.extras_persistent


def test_later_model_iterations_reuse_the_first_context(monkeypatch):
    agent = _Agent()
    loop_data = _loop_data(1)
    loop_data.extras_persistent[EXTRA_KEY] = "existing context"
    monkeypatch.setattr(
        plugin_service,
        "context_for_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not rerun")),
    )

    asyncio.run(IncludeTreeSitterContext(agent=agent).execute(loop_data=loop_data))

    assert loop_data.extras_persistent[EXTRA_KEY] == "existing context"


def test_no_active_project_is_a_quiet_noop(monkeypatch):
    agent = _Agent()
    loop_data = _loop_data(0)
    monkeypatch.setattr(
        plugin_service,
        "get_config",
        lambda agent=None: {"auto_context_enabled": True},
    )
    monkeypatch.setattr(
        plugin_service,
        "resolve_root_path",
        lambda context=None: (_ for _ in ()).throw(
            TreeSitterRuntimeError("activate a project")
        ),
    )

    asyncio.run(IncludeTreeSitterContext(agent=agent).execute(loop_data=loop_data))

    assert EXTRA_KEY not in loop_data.extras_persistent
    assert agent.context.log.entries == []
