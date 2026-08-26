from __future__ import annotations

from helpers.api import ApiHandler, Request

from usr.plugins.tree_sitter import hooks


class RuntimeStatus(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        return hooks.runtime_report()
