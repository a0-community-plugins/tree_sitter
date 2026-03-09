from __future__ import annotations

from helpers.api import ApiHandler, Request, Response

from usr.plugins.tree_sitter.helpers import plugin_service
from usr.plugins.tree_sitter.helpers.runtime_support import TreeSitterRuntimeError


class Inspect(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        path = input.get("path", "")
        if not path:
            return Response("Missing path", 400)

        try:
            return plugin_service.inspect_file(
                path,
                language=input.get("language"),
                query=input.get("query"),
            )
        except (FileNotFoundError, TreeSitterRuntimeError, ValueError) as exc:
            return Response(str(exc), 400)
