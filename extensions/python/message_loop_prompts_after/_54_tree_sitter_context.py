from __future__ import annotations

import asyncio
import json

from helpers.extension import Extension

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


EXTRA_KEY = "tree_sitter_context"


class IncludeTreeSitterContext(Extension):
    """Add bounded structural context before the first model call for a project task."""

    async def execute(self, loop_data=None, **_kwargs):
        if not self.agent or loop_data is None or loop_data.iteration != 0:
            return

        config = plugin_service.get_config(agent=self.agent)
        if not config["auto_context_enabled"]:
            loop_data.extras_persistent.pop(EXTRA_KEY, None)
            return

        task = loop_data.user_message.output_text() if loop_data.user_message else ""
        task = str(task or "").strip()
        if not task:
            loop_data.extras_persistent.pop(EXTRA_KEY, None)
            return

        try:
            root_path, project_name = plugin_service.resolve_root_path(
                context=self.agent.context
            )
        except TreeSitterRuntimeError:
            loop_data.extras_persistent.pop(EXTRA_KEY, None)
            return

        try:
            context = await asyncio.to_thread(
                plugin_service.context_for_task,
                root_path,
                task=task,
                agent=self.agent,
                project_name=project_name,
            )
        except Exception as exc:
            loop_data.extras_persistent.pop(EXTRA_KEY, None)
            self.agent.context.log.log(
                type="warning",
                heading="Tree-sitter automatic context unavailable",
                content=str(exc),
            )
            return

        payload = {
            "root_path": context.get("root_path"),
            "definitions": context.get("definitions", []),
            "imports": context.get("imports", []),
            "references": context.get("references"),
            "index": context.get("index"),
            "truncated": context.get("truncated", False),
            "context_chars": context.get("context_chars", 0),
        }
        loop_data.extras_persistent[EXTRA_KEY] = self.agent.read_prompt(
            "agent.extras.tree_sitter_context.md",
            tree_sitter_context=json.dumps(payload, ensure_ascii=False, default=str),
        )
