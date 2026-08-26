from __future__ import annotations

from helpers.api import ApiHandler, Request, Response

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class Search(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("ctxid", "")
        context = self.use_context(ctxid) if ctxid else None
        try:
            root_path, project_name = plugin_service.resolve_root_path(
                input.get("root_path"), context=context,
            )
            query = str(input.get("query") or "").strip()
            if not query:
                return Response("Missing query", 400)
            return plugin_service.search_symbols(
                root_path, query=query, project_name=project_name,
                limit=max(1, min(int(input.get("limit", 50)), 200)),
            )
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError) as exc:
            return Response(str(exc), 400)
