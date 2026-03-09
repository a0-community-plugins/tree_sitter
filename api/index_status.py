from __future__ import annotations

from helpers.api import ApiHandler, Request, Response

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class IndexStatus(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("ctxid", "")
        context = self.use_context(ctxid) if ctxid else None

        try:
            root_path, project_name = plugin_service.resolve_root_path(
                input.get("root_path"),
                context=context if context else None,
            )
            status = plugin_service.get_index_status(
                root_path,
                project_name=project_name,
            )
            return {
                "ok": status is not None,
                "status": status,
                "root_path": root_path,
            }
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError) as exc:
            return Response(str(exc), 400)
