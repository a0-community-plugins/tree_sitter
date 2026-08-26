---
name: structural-coding
description: Use Tree-sitter repository intelligence to investigate, change, and verify source code with bounded context.
---

# Structural Coding

Use this workflow for non-trivial code changes when the `tree_sitter` tool is available.

1. Call `tree_sitter:context` with the task and, when known, the primary symbol. This lazily refreshes the project index and returns the most relevant definitions, imports, references, and bounded snippets.
2. Use `tree_sitter:search` for exact definitions and `tree_sitter:references` before changing a public or shared symbol. Treat references as structural candidates, not type-resolved proof.
3. Use ordinary text search and file reading for comments, strings, generated code, configuration, and semantics Tree-sitter cannot infer.
4. Make the smallest coherent edit with the normal editing tools.
5. Call `tree_sitter:diagnostics` for every changed source file. A clean syntax result does not replace the project compiler, type checker, linter, or tests.
6. Run the repository's focused verification commands.

Use `tree_sitter:query` only when a grammar-specific S-expression query is more precise than the built-in operations. Query node names vary by grammar; inspect a file first when unsure.

Do not index secrets or roots broader than the active project. Repository indexes contain symbol metadata and are stored locally under the plugin's data directory.
