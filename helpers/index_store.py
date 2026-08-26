from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterator


SCHEMA_VERSION = 2


class ProjectIndexStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def fingerprints(self, project_key: str) -> dict[str, tuple[int, int]]:
        with self._connection(project_key) as connection:
            return {
                str(row["path"]): (int(row["mtime_ns"]), int(row["size_bytes"]))
                for row in connection.execute("SELECT path, mtime_ns, size_bytes FROM files")
            }

    def replace_files(
        self,
        project_key: str,
        root_path: str,
        records: list[dict[str, Any]],
        present_paths: set[str],
        *,
        errors: list[dict[str, str]],
        truncated: bool,
    ) -> dict[str, Any]:
        with self._connection(project_key) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for record in records:
                self._replace_file(connection, record)
            if present_paths:
                placeholders = ",".join("?" for _ in present_paths)
                connection.execute(
                    f"DELETE FROM files WHERE path NOT IN ({placeholders})",
                    tuple(sorted(present_paths)),
                )
            else:
                connection.execute("DELETE FROM files")
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "root_path": root_path,
                "indexed_at": time.time(),
                "truncated": bool(truncated),
                "errors": errors[:100],
            }
            for key, value in metadata.items():
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                    (key, json.dumps(value)),
                )
            connection.commit()
        return self.manifest(project_key) or {}

    def manifest(self, project_key: str) -> dict[str, Any] | None:
        database = self._database_path(project_key)
        if not database.is_file():
            return None
        with self._connection(project_key) as connection:
            metadata = {
                str(row["key"]): json.loads(str(row["value"]))
                for row in connection.execute("SELECT key, value FROM metadata")
            }
            counts = connection.execute(
                """
                SELECT
                    COUNT(*) AS file_count,
                    COALESCE(SUM(definition_count), 0) AS definition_count,
                    COALESCE(SUM(symbol_count), 0) AS symbol_count,
                    COALESCE(SUM(diagnostic_count), 0) AS diagnostic_count
                FROM files
                """
            ).fetchone()
            languages = {
                str(row["language"]): int(row["count"])
                for row in connection.execute(
                    "SELECT language, COUNT(*) AS count FROM files GROUP BY language ORDER BY language"
                )
            }
        return {
            "project_key": project_key,
            **metadata,
            "file_count": int(counts["file_count"]),
            "definition_count": int(counts["definition_count"]),
            "symbol_count": int(counts["symbol_count"]),
            "diagnostic_count": int(counts["diagnostic_count"]),
            "languages": languages,
            "database_path": str(database),
        }

    def search_definitions(self, project_key: str, query: str, limit: int = 50) -> list[dict[str, Any]]:
        needle = query.strip()
        if not needle:
            return []
        with self._connection(project_key) as connection:
            rows = connection.execute(
                """
                SELECT d.*, f.language
                FROM definitions d JOIN files f ON f.path = d.path
                WHERE d.name = ? COLLATE NOCASE
                   OR d.qualname = ? COLLATE NOCASE
                   OR d.name LIKE ? COLLATE NOCASE
                   OR d.qualname LIKE ? COLLATE NOCASE
                ORDER BY
                    CASE WHEN d.name = ? COLLATE NOCASE THEN 0
                         WHEN d.qualname = ? COLLATE NOCASE THEN 1 ELSE 2 END,
                    d.path, d.start_line
                LIMIT ?
                """,
                (needle, needle, f"{needle}%", f"%{needle}%", needle, needle, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def references(self, project_key: str, symbol: str, limit: int = 200) -> dict[str, Any]:
        with self._connection(project_key) as connection:
            definitions = connection.execute(
                """SELECT d.*, f.language FROM definitions d JOIN files f ON f.path=d.path
                   WHERE d.name = ? COLLATE NOCASE ORDER BY d.path, d.start_line LIMIT ?""",
                (symbol, int(limit)),
            ).fetchall()
            occurrences = connection.execute(
                """SELECT o.*, f.language FROM occurrences o JOIN files f ON f.path=o.path
                   WHERE o.name = ? COLLATE NOCASE ORDER BY o.path, o.start_line LIMIT ?""",
                (symbol, int(limit)),
            ).fetchall()
        definition_keys = {
            (str(row["path"]), int(row["start_line"]), str(row["kind"]).lower(), str(row["name"]).lower())
            for row in definitions
        }
        refs = [
            dict(row) for row in occurrences
            if (
                str(row["path"]), int(row["start_line"]),
                str(row["kind"]).lower(), str(row["name"]).lower(),
            ) not in definition_keys
        ]
        return {"symbol": symbol, "definitions": [dict(row) for row in definitions], "references": refs}

    def imports_for_paths(self, project_key: str, paths: list[str], limit: int = 100) -> list[dict[str, Any]]:
        if not paths:
            return []
        placeholders = ",".join("?" for _ in paths)
        with self._connection(project_key) as connection:
            rows = connection.execute(
                f"SELECT * FROM imports WHERE path IN ({placeholders}) ORDER BY path, start_line LIMIT ?",
                (*paths, int(limit)),
            ).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            try:
                item["items"] = json.loads(str(item.get("items") or "[]"))
            except ValueError:
                item["items"] = []
        return result

    def diagnostics(self, project_key: str, paths: list[str] | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._connection(project_key) as connection:
            if paths:
                placeholders = ",".join("?" for _ in paths)
                rows = connection.execute(
                    f"SELECT * FROM diagnostics WHERE path IN ({placeholders}) ORDER BY path, start_line LIMIT ?",
                    (*paths, int(limit)),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM diagnostics ORDER BY path, start_line LIMIT ?", (int(limit),)
                ).fetchall()
        return [dict(row) for row in rows]

    def _replace_file(self, connection: sqlite3.Connection, record: dict[str, Any]) -> None:
        path = str(record["path"])
        connection.execute("DELETE FROM files WHERE path = ?", (path,))
        connection.execute(
            """
            INSERT INTO files(
                path, language, mtime_ns, size_bytes, source_hash,
                definition_count, symbol_count, diagnostic_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path, record["language"], int(record["mtime_ns"]), int(record["size_bytes"]),
                record["source_hash"], len(record.get("definitions", [])),
                len(record.get("symbols", [])), len(record.get("diagnostics", [])),
            ),
        )
        for definition in record.get("definitions", []):
            connection.execute(
                """INSERT INTO definitions(path, name, qualname, kind, start_line, end_line, start_col, end_col)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    path, definition.get("name", ""), definition.get("qualname", ""),
                    definition.get("kind", "other"), int(definition.get("start_line", 1)),
                    int(definition.get("end_line", 1)), int(definition.get("start_col", 1)),
                    int(definition.get("end_col", 1)),
                ),
            )
        for symbol in record.get("symbols", []):
            name = str(symbol.get("name") or "")
            if not name:
                continue
            connection.execute(
                """INSERT INTO occurrences(path, name, kind, start_line, end_line, start_col, end_col)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    path, name, str(symbol.get("kind") or symbol.get("node_type") or "identifier"),
                    int(symbol.get("start_line", 1)), int(symbol.get("end_line", 1)),
                    int(symbol.get("start_col", 1)), int(symbol.get("end_col", 1)),
                ),
            )
        for imported in record.get("imports", []):
            connection.execute(
                "INSERT INTO imports(path, source, items, alias, start_line) VALUES (?, ?, ?, ?, ?)",
                (
                    path, str(imported.get("source") or ""), json.dumps(imported.get("items") or []),
                    imported.get("alias"), int(imported.get("start_line", 1)),
                ),
            )
        for diagnostic in record.get("diagnostics", []):
            connection.execute(
                """INSERT INTO diagnostics(path, message, severity, start_line, end_line, start_col, end_col)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    path, str(diagnostic.get("message") or "syntax error"),
                    str(diagnostic.get("severity") or "error"), int(diagnostic.get("start_line", 1)),
                    int(diagnostic.get("end_line", 1)), int(diagnostic.get("start_col", 1)),
                    int(diagnostic.get("end_col", 1)),
                ),
            )

    @contextmanager
    def _connection(self, project_key: str) -> Iterator[sqlite3.Connection]:
        database = self._database_path(project_key)
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(_SCHEMA)
        try:
            yield connection
        finally:
            connection.close()

    def _database_path(self, project_key: str) -> Path:
        safe_key = "".join(char for char in project_key if char.isalnum() or char in {"-", "_"})
        if not safe_key:
            raise ValueError("Invalid project index key")
        return self.base_dir / f"{safe_key}.sqlite3"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files(
    path TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    source_hash TEXT NOT NULL,
    definition_count INTEGER NOT NULL,
    symbol_count INTEGER NOT NULL,
    diagnostic_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS definitions(
    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    name TEXT NOT NULL,
    qualname TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_col INTEGER NOT NULL,
    end_col INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS definitions_name_idx ON definitions(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS definitions_qualname_idx ON definitions(qualname COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS occurrences(
    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_col INTEGER NOT NULL,
    end_col INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS occurrences_name_idx ON occurrences(name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS imports(
    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    source TEXT NOT NULL,
    items TEXT NOT NULL,
    alias TEXT,
    start_line INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS diagnostics(
    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_col INTEGER NOT NULL,
    end_col INTEGER NOT NULL
);
"""
