from __future__ import annotations

import json
from typing import Any

from helpers.tool import Response, Tool

from usr.plugins.tree_sitter import hooks
from usr.plugins.tree_sitter.helpers import plugin_service, runtime_support
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class TreeSitter(Tool):
    async def execute(self, **kwargs: Any) -> Response:
        try:
            method = _current_method(self, kwargs)
            root_path, project_name = self._root(kwargs.get("root_path"), required=False)
            config = plugin_service.get_config(agent=self.agent)

            if method in {"status", "overview", "languages"}:
                status: dict[str, Any] = {"runtime": hooks.runtime_report()}
                if root_path:
                    status["index"] = plugin_service.get_index_status(root_path, project_name=project_name)
                    status["root_path"] = root_path
                if method == "languages" and status["runtime"]["ready"]:
                    status["languages"] = runtime_support.available_languages()
                return self._ok(status)

            if method in {"inspect", "symbols", "chunks"}:
                result = plugin_service.inspect_file(
                    kwargs.get("path", ""),
                    language=kwargs.get("language"),
                    config=config,
                    root_path=root_path,
                )
                if method == "symbols":
                    result = {key: result[key] for key in ("path", "language", "definitions")}
                elif method == "chunks":
                    result = {key: result[key] for key in ("path", "language", "chunks")}
                return self._ok(result)

            if method == "query":
                result = plugin_service.inspect_file(
                    kwargs.get("path", ""), language=kwargs.get("language"),
                    query=kwargs.get("query", ""), query_kind=kwargs.get("query_kind"),
                    config=config, root_path=root_path,
                )
                return self._ok({
                    "path": result["path"], "language": result["language"],
                    "query_matches": result.get("query_matches", []),
                })

            if method == "scope":
                return self._ok(plugin_service.scope_for_position(
                    kwargs.get("path", ""), line=int(kwargs.get("line", 1)),
                    column=int(kwargs.get("column", 1)), language=kwargs.get("language"),
                    root_path=root_path,
                ))

            if method == "index":
                root_path, project_name = self._root(kwargs.get("root_path"), required=True)
                return self._ok(plugin_service.build_index(
                    root_path, agent=self.agent, project_name=project_name,
                    force=_as_bool(kwargs.get("force", False)),
                ))

            if method in {"search", "lookup"}:
                root_path, project_name = self._root(kwargs.get("root_path"), required=True)
                query = kwargs.get("query") or kwargs.get("symbol") or ""
                self._ensure_index(root_path, project_name)
                return self._ok(plugin_service.search_symbols(
                    root_path, query=query, project_name=project_name,
                    limit=int(kwargs.get("limit", config["context_max_results"])),
                ))

            if method == "references":
                root_path, project_name = self._root(kwargs.get("root_path"), required=True)
                self._ensure_index(root_path, project_name)
                return self._ok(plugin_service.references_for_symbol(
                    root_path, symbol=kwargs.get("symbol", ""), project_name=project_name,
                    limit=int(kwargs.get("limit", 200)),
                ))

            if method == "context":
                root_path, project_name = self._root(kwargs.get("root_path"), required=True)
                return self._ok(plugin_service.context_for_task(
                    root_path, task=kwargs.get("task", ""), symbol=kwargs.get("symbol"),
                    agent=self.agent, project_name=project_name,
                ))

            if method == "diagnostics":
                paths = kwargs.get("paths") or ([kwargs["path"]] if kwargs.get("path") else [])
                if isinstance(paths, str):
                    paths = [item.strip() for item in paths.split(",") if item.strip()]
                if not paths:
                    raise ValueError("path or paths is required")
                return self._ok(plugin_service.diagnostics_for_files(
                    paths, root_path=root_path, agent=self.agent,
                ))

            return Response(message=f"Unknown tree_sitter method: {method or None}", break_loop=False)
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError, OSError) as exc:
            return Response(message=str(exc), break_loop=False)

    def _root(self, explicit: str | None, *, required: bool) -> tuple[str | None, str | None]:
        try:
            return plugin_service.resolve_root_path(explicit, context=self.agent.context)
        except TreeSitterRuntimeError:
            if required:
                raise
            return None, None

    def _ensure_index(self, root_path: str, project_name: str | None) -> None:
        if plugin_service.get_index_status(root_path, project_name=project_name) is None:
            plugin_service.build_index(root_path, agent=self.agent, project_name=project_name)

    @staticmethod
    def _ok(payload: dict[str, Any]) -> Response:
        return Response(message=json.dumps(payload, indent=2, sort_keys=True), break_loop=False)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _current_method(tool: TreeSitter, kwargs: dict[str, Any]) -> str:
    value = (
        kwargs.get("action")
        or kwargs.get("method")
        or tool.args.get("action")
        or tool.args.get("method")
        or tool.method
        or ""
    )
    return str(value).strip().lower().replace("-", "_")
