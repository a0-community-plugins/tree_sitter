# Tree-sitter Code Intelligence for Agent Zero

Tree-sitter gives Agent Zero a structural view of a repository before it edits code and a fast syntax check after it edits code. Version 1.1 makes that project intelligence automatic for active-project tasks while retaining focused tools and a manual inspector for deeper work.

## What it adds

- bounded task context assembled from definitions, imports, references, and source snippets
- automatic structural context before the first model call for each active-project task
- incremental SQLite indexes that reuse unchanged files and honor Git ignore rules
- repository-wide definition search and syntax-aware identifier references
- file structure, imports, exports, diagnostics, metrics, and LLM-oriented chunks
- arbitrary Tree-sitter queries plus bundled `tags`, `locals`, `highlights`, `injections`, `folds`, and `indents` queries
- project path boundaries, file/count/timeout limits, and local-only index storage
- an Agent Zero skill that guides the agent through context, edit, diagnostics, and project verification
- a Code Intelligence workbench in Plugin Settings

The parser layer uses `tree-sitter-language-pack==1.15.8`, which currently exposes hundreds of grammars through one Python API and downloads individual parser artifacts on first use. The exact available and cached language counts are reported by `tree_sitter:status` and the settings UI.

## Coding workflow

When an Agent Zero project is active, the plugin incrementally refreshes its local index and adds bounded structural context before the first model call. That context remains available through the task loop without rebuilding on every model iteration. The behavior is enabled by default and can be disabled in Plugin Settings.

For deeper investigation or explicit verification, Agent Zero can:

1. call `tree_sitter:context` with the coding task and optional primary symbol;
2. inspect exact definitions and repository-wide structural references;
3. edit with Agent Zero's normal text editing tools;
4. call `tree_sitter:diagnostics` on changed files;
5. run the repository's compiler, linter, and focused tests.

Tree-sitter is intentionally not presented as a compiler or language server. Structural references can contain same-named identifiers from unrelated scopes, and clean syntax does not prove type correctness or behavior.

## Tool methods

| Method | Purpose |
| --- | --- |
| `context` | Incrementally refresh the index and assemble bounded task context. |
| `search` | Find definitions by name or qualified name. |
| `references` | Find parsed occurrences across indexed files. |
| `inspect` | Return full structural intelligence for one file. |
| `diagnostics` | Parse one or more changed files and report syntax errors. |
| `scope` | Find the smallest enclosing definition at a line and column. |
| `query` | Execute custom or bundled grammar queries. |
| `index` | Incrementally refresh or force rebuild the project index. |
| `status` | Report framework runtime and active project index readiness. |
| `languages` | List the installed pack's supported language names. |

The earlier `symbols`, `chunks`, `lookup`, and `overview` method names remain as compatibility aliases.

## Agent Zero integration

Install the plugin from its Git repository through Plugin Hub. The explicit install/update action runs `hooks.py`, which installs the exact dependency in the Agent Zero **framework runtime**. The agent execution runtime is not used for plugin hooks or backend tools.

There is deliberately no `initialize.py`, `execute.py`, or dependency-install API. Lifecycle ownership is centralized in `hooks.py`:

- `install()` installs the new revision's exact requirement, loads 28 representative native parsers, and fails the plugin installation if detection or parsing is unhealthy;
- `pre_update()` records readiness without installing the old revision's requirement;
- the Plugin Hub invokes `install()` again after pulling the update;
- `uninstall()` leaves the shared framework package intact while Agent Zero removes plugin-owned files and indexes.

The `message_loop_prompts_after` extension is the always-on integration point. On the first loop iteration it resolves the active project, incrementally refreshes only changed files, and adds a bounded, data-delimited structural snapshot to the prompt. Concurrent agents share a per-project index lock so they do not rebuild the same SQLite index simultaneously. Missing-project state is a quiet no-op; indexing failures are reported as framework warnings and never prevent the agent from continuing. The Code Intelligence Inspector is intentionally a manual diagnostic surface, not the primary activation path.

Settings are project- and agent-profile-aware. Relative file paths resolve against the active Agent Zero project. By default, file inspection cannot escape that project root; the setting can be changed when an operator deliberately needs cross-project inspection.

Indexes live in `data/indexes/` under the installed plugin and are ignored by Git. They contain paths, symbols, spans, imports, diagnostics, and source fingerprints—not full source files. Context snippets are read from the repository only when requested.

## Query assets

Textual-based applications commonly keep language-specific `.scm` highlight queries as separate runtime assets, cache language objects, and compile a query once for reuse. The OpenMed bundle supplied for comparison follows the asset pattern under `textual/tree-sitter/highlights/`. This plugin follows the same separation with the language pack's bundled query catalog and a bounded compiled-query cache instead of copying a small fixed set, while still allowing a raw S-expression query for grammar-specific investigations.

Example:

```json
{
  "thoughts": ["I need every definition tag in this Python file."],
  "headline": "Querying structural tags",
  "tool_name": "tree_sitter",
  "tool_args": {
    "method": "query",
    "path": "helpers/plugins.py",
    "query_kind": "tags"
  }
}
```

## Development verification

From the Agent Zero repository root:

```bash
python -m pytest usr/plugins/tree_sitter/tests
python -m compileall -q usr/plugins/tree_sitter
node --check usr/plugins/tree_sitter/webui/tree-sitter-inspector-store.js
```

The default suite uses a fake structural runtime where isolation is useful, so it does not download parser artifacts. Plugin installation automatically runs the native matrix with Agent Zero's framework Python. The same matrix can be invoked independently to verify canonical aliases, path detection, parser loading, and error-free syntax trees for 28 representative languages, including distinct C#, Zsh, TypeScript, and TSX parsers:

```bash
TREE_SITTER_REAL_RUNTIME=1 python -m pytest \
  usr/plugins/tree_sitter/tests/test_real_runtime_parsers.py -q
```

Run that command with the exact Dockerized Agent Zero framework Python intended for use. The matrix deliberately fails when the pinned language pack has not been provisioned; it never substitutes fake parsers.

## Sources

- [Tree-sitter documentation](https://tree-sitter.github.io/tree-sitter/)
- [Tree-sitter query syntax](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html)
- [Tree-sitter parser catalog](https://github.com/tree-sitter/tree-sitter/wiki/List-of-parsers)
- [tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack)
