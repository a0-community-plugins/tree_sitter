from __future__ import annotations

from helpers.api import ApiHandler, Request, Response

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class Inspect(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        path = input.get("path", "")
        if not path:
            return Response("Missing path", 400)

        ctxid = input.get("ctxid", "")
        context = self.use_context(ctxid) if ctxid else None

        try:
            root_path = input.get("root_path")
            if not root_path and context:
                root_path, _project_name = plugin_service.resolve_root_path(context=context)
            return plugin_service.inspect_file(
                path,
                language=input.get("language"),
                query=input.get("query"),
                query_kind=input.get("query_kind"),
                root_path=root_path,
            )
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError) as exc:
            return Response(str(exc), 400)
