from __future__ import annotations

from helpers.api import ApiHandler, Request, Response

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class Reindex(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("ctxid", "")
        context = self.use_context(ctxid) if ctxid else None

        try:
            root_path, project_name = plugin_service.resolve_root_path(
                input.get("root_path"),
                context=context if context else None,
            )
            return plugin_service.build_index(
                root_path,
                agent=context.agent0 if context else None,
                project_name=project_name,
            )
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError) as exc:
            return Response(str(exc), 400)
