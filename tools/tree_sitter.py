from __future__ import annotations

import json

from helpers.tool import Response, Tool

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class TreeSitter(Tool):
    async def execute(self, **kwargs) -> Response:
        try:
            if self.method == "symbols":
                result = plugin_service.inspect_file(
                    kwargs.get("path", ""),
                    language=kwargs.get("language"),
                    config=plugin_service.get_config(agent=self.agent),
                )
                payload = {
                    "path": result["path"],
                    "language": result["language"],
                    "symbols": result["symbols"],
                }
                return self._ok(payload)

            if self.method == "references":
                result = plugin_service.references_for_symbol(
                    kwargs.get("path", ""),
                    symbol=kwargs.get("symbol", ""),
                    language=kwargs.get("language"),
                    config=plugin_service.get_config(agent=self.agent),
                )
                return self._ok(result)

            if self.method == "chunks":
                result = plugin_service.inspect_file(
                    kwargs.get("path", ""),
                    language=kwargs.get("language"),
                    config=plugin_service.get_config(agent=self.agent),
                )
                payload = {
                    "path": result["path"],
                    "language": result["language"],
                    "chunks": result["chunks"],
                }
                return self._ok(payload)

            if self.method == "scope":
                result = plugin_service.scope_for_position(
                    kwargs.get("path", ""),
                    line=int(kwargs.get("line", 1)),
                    column=int(kwargs.get("column", 1)),
                    language=kwargs.get("language"),
                )
                return self._ok(result)

            if self.method == "query":
                result = plugin_service.inspect_file(
                    kwargs.get("path", ""),
                    language=kwargs.get("language"),
                    query=kwargs.get("query"),
                    config=plugin_service.get_config(agent=self.agent),
                )
                payload = {
                    "path": result["path"],
                    "language": result["language"],
                    "query_matches": result.get("query_matches", []),
                }
                return self._ok(payload)

            if self.method == "index":
                root_path, project_name = plugin_service.resolve_root_path(
                    kwargs.get("root_path"),
                    context=self.agent.context,
                )
                result = plugin_service.build_index(
                    root_path,
                    agent=self.agent,
                    project_name=project_name,
                )
                return self._ok(result)

            if self.method == "lookup":
                root_path, project_name = plugin_service.resolve_root_path(
                    kwargs.get("root_path"),
                    context=self.agent.context,
                )
                result = plugin_service.lookup_symbol(
                    root_path,
                    symbol=kwargs.get("symbol", ""),
                    project_name=project_name,
                )
                return self._ok(result)

            return Response(
                message=f"Unknown tree_sitter method: {self.method}",
                break_loop=False,
            )
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError) as exc:
            return Response(message=str(exc), break_loop=False)

    def _ok(self, payload: dict) -> Response:
        return Response(
            message=json.dumps(payload, indent=2, sort_keys=True),
            break_loop=False,
        )
