"""Representative native-parser validation for plugin installation and testing."""

from __future__ import annotations

from typing import Any

from . import runtime_support


PARSER_MATRIX = (
    ("bash", "matrix.sh", "#!/usr/bin/env bash\nprintf '%s\\n' \"ok\"\n"),
    ("c", "matrix.c", "int main(void) { return 0; }\n"),
    ("cpp", "matrix.cpp", "int main() { return 0; }\n"),
    ("csharp", "matrix.cs", "class Matrix { static int Main() { return 0; } }\n"),
    ("css", "matrix.css", "body { color: #123456; }\n"),
    ("dockerfile", "Dockerfile", "FROM scratch\nLABEL purpose=matrix\n"),
    ("go", "matrix.go", "package main\nfunc main() {}\n"),
    ("html", "matrix.html", "<!doctype html><title>Matrix</title>\n"),
    ("java", "Matrix.java", "class Matrix { public static void main(String[] args) {} }\n"),
    ("javascript", "matrix.js", "export const matrix = () => true;\n"),
    ("json", "matrix.json", '{"matrix": true}\n'),
    ("kotlin", "matrix.kt", "fun main() { println(\"matrix\") }\n"),
    ("lua", "matrix.lua", "local matrix = true\nreturn matrix\n"),
    ("markdown", "matrix.md", "# Matrix\n\nParser smoke test.\n"),
    ("php", "matrix.php", "<?php function matrix(): bool { return true; }\n"),
    ("python", "matrix.py", "def matrix() -> bool:\n    return True\n"),
    ("ruby", "matrix.rb", "def matrix\n  true\nend\n"),
    ("rust", "matrix.rs", "fn main() { println!(\"matrix\"); }\n"),
    ("scala", "Matrix.scala", "object Matrix { def main(args: Array[String]): Unit = () }\n"),
    ("sql", "matrix.sql", "SELECT 1 AS matrix;\n"),
    ("swift", "matrix.swift", "func matrix() -> Bool { true }\n"),
    ("toml", "matrix.toml", "matrix = true\n"),
    ("typescript", "matrix.ts", "export const matrix: boolean = true;\n"),
    ("tsx", "matrix.tsx", "export const Matrix = () => <div>matrix</div>;\n"),
    ("xml", "matrix.xml", "<?xml version=\"1.0\"?><matrix enabled=\"true\"/>\n"),
    ("yaml", "matrix.yaml", "matrix: true\n"),
    ("zig", "matrix.zig", "pub fn main() void {}\n"),
    ("zsh", "matrix.zsh", "#!/usr/bin/env zsh\nprint -r -- matrix\n"),
)


def verify_parser_matrix() -> dict[str, Any]:
    """Load and parse representative grammars, raising on the first mismatch."""
    runtime = runtime_support.require_runtime()
    invalid_aliases = sorted({
        canonical
        for canonical in runtime_support._FALLBACK_ALIASES.values()
        if not runtime.has_language(canonical)
    })
    if invalid_aliases:
        raise runtime_support.TreeSitterRuntimeError(
            f"Parser aliases target unavailable languages: {', '.join(invalid_aliases)}"
        )

    results: list[dict[str, str]] = []
    for language, path, source in PARSER_MATRIX:
        detected = runtime_support.detect_language(path, source)
        if detected != language:
            raise runtime_support.TreeSitterRuntimeError(
                f"Parser detection mismatch for {path}: expected {language}, got {detected}"
            )
        canonical = runtime_support.canonicalize_language(language)
        if canonical != language:
            raise runtime_support.TreeSitterRuntimeError(
                f"Parser canonicalization mismatch for {language}: got {canonical}"
            )
        tree = runtime_support.parse_source(source, language)
        root = tree.root_node
        if root.type == "ERROR" or root.has_error:
            raise runtime_support.TreeSitterRuntimeError(
                f"Native {language} parser produced an error tree for {path}"
            )
        results.append({"language": language, "root_type": str(root.type)})

    return {
        "ok": True,
        "parser_count": len(results),
        "languages": [item["language"] for item in results],
        "roots": results,
    }
