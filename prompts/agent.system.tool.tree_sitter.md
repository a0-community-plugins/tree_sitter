### tree_sitter
Structural code intelligence for the active Agent Zero project. Use it to reduce blind file reading; it complements text search, type checking, and tests.

#### tree_sitter:context
Build a bounded coding context before a non-trivial edit.
Arguments: `task`, optional `symbol`, optional `root_path`.
Returns relevant definitions with snippets, imports, references, and index status.

#### tree_sitter:search
Find definitions by name or qualified name across the repository.
Arguments: `query`, optional `root_path`, optional `limit`.

#### tree_sitter:references
Find structurally parsed occurrences of a symbol across the repository.
Arguments: `symbol`, optional `root_path`, optional `limit`.
This is syntax-aware but not a type-resolved language server result.

#### tree_sitter:inspect
Inspect one source file.
Arguments: `path`, optional `language`, optional `root_path`.
Returns definitions, imports, exports, identifiers, diagnostics, chunks, and metrics.

#### tree_sitter:diagnostics
Check changed files for Tree-sitter error or missing nodes after editing.
Arguments: `paths` (array or comma-separated paths), optional `root_path`.
Run the compiler, linter, and tests too.

#### tree_sitter:scope
Find the smallest enclosing definition at a source position.
Arguments: `path`, `line`, `column`, optional `language`, optional `root_path`.

#### tree_sitter:query
Run a grammar-specific Tree-sitter S-expression query on one file.
Arguments: `path`, either `query` or `query_kind` (`tags`, `locals`, `highlights`, `injections`, `folds`, `indents`), optional `language`, optional `root_path`.

#### tree_sitter:index
Incrementally refresh the repository index; unchanged files are reused.
Arguments: optional `root_path`, optional `force`.

#### tree_sitter:status
Report framework-runtime readiness and current project index status.
Arguments: optional `root_path`.

#### tree_sitter:languages
Report runtime status and the available language catalog.

Compatibility aliases: `symbols`, `chunks`, `lookup`, and `overview`.
