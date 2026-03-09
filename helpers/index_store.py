from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


class ProjectIndexStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def save_index(
        self,
        project_key: str,
        root_path: str,
        file_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project_dir = self._project_dir(project_key)
        project_dir.mkdir(parents=True, exist_ok=True)

        symbol_records = [
            symbol
            for file_record in file_records
            for symbol in file_record.get("symbols", [])
        ]
        chunk_records = [
            chunk
            for file_record in file_records
            for chunk in file_record.get("chunks", [])
        ]

        language_counts = Counter(
            file_record.get("language", "unknown")
            for file_record in file_records
        )
        manifest = {
            "project_key": project_key,
            "root_path": root_path,
            "file_count": len(file_records),
            "symbol_count": len(symbol_records),
            "chunk_count": len(chunk_records),
            "languages": dict(sorted(language_counts.items())),
        }

        self._write_json(project_dir / "manifest.json", manifest)
        self._write_json(project_dir / "files.json", file_records)
        self._write_json(project_dir / "symbols.json", symbol_records)
        self._write_json(project_dir / "chunks.json", chunk_records)
        return manifest

    def load_manifest(self, project_key: str) -> dict[str, Any] | None:
        manifest_file = self._project_dir(project_key) / "manifest.json"
        if not manifest_file.exists():
            return None
        return json.loads(manifest_file.read_text(encoding="utf-8"))

    def load_files(self, project_key: str) -> list[dict[str, Any]]:
        files_file = self._project_dir(project_key) / "files.json"
        if not files_file.exists():
            return []
        return json.loads(files_file.read_text(encoding="utf-8"))

    def lookup_symbol(self, project_key: str, name: str) -> list[dict[str, Any]]:
        symbols_file = self._project_dir(project_key) / "symbols.json"
        if not symbols_file.exists():
            return []
        symbols = json.loads(symbols_file.read_text(encoding="utf-8"))
        exact = [symbol for symbol in symbols if symbol.get("name") == name]
        if exact:
            return exact
        lowered = name.lower()
        return [
            symbol
            for symbol in symbols
            if str(symbol.get("name", "")).lower() == lowered
        ]

    def _project_dir(self, project_key: str) -> Path:
        return self.base_dir / project_key

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
