from helpers.extension import Extension


class TreeSitterPrompt(Extension):
    async def execute(self, system_prompt: list[str] | None = None, **kwargs):
        if system_prompt is None:
            return
        system_prompt.append(self.agent.read_prompt("agent.system.tool.tree_sitter.md"))
