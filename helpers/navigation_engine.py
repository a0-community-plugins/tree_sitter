from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SYMBOL_KIND_BY_NODE_TYPE = {
    "class_declaration": "class",
    "class_definition": "class",
    "class_specifier": "class",
    "enum_declaration": "enum",
    "enum_specifier": "enum",
    "function_declaration": "function",
    "function_definition": "function",
    "function_item": "function",
    "function_signature_item": "function",
    "impl_item": "impl",
    "interface_declaration": "interface",
    "method_declaration": "function",
    "method_definition": "function",
    "namespace_definition": "namespace",
    "struct_item": "struct",
    "trait_item": "trait",
    "type_alias_declaration": "type",
    "type_definition": "type",
}

IDENTIFIER_NODE_TYPES = {
    "field_identifier",
    "identifier",
    "property_identifier",
    "type_identifier",
}

NAME_FIELD_CANDIDATES = ("name",)
NAME_CHILD_CANDIDATES = (
    "identifier",
    "type_identifier",
    "property_identifier",
    "field_identifier",
)


@dataclass(slots=True)
class SymbolRecord:
    name: str
    kind: str
    path: str
    language: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    node_type: str
    qualname: str
    name_start_line: int | None = None
    name_end_line: int | None = None
    name_start_col: int | None = None
    name_end_col: int | None = None

    @property
    def span(self) -> tuple[tuple[int, int], tuple[int, int]]:
        if None not in (
            self.name_start_line,
            self.name_start_col,
            self.name_end_line,
            self.name_end_col,
        ):
            return (
                (self.name_start_line or self.start_line, self.name_start_col or self.start_col),
                (self.name_end_line or self.end_line, self.name_end_col or self.end_col),
            )
        return (
            (self.start_line, self.start_col),
            (self.end_line, self.end_col),
        )


@dataclass(slots=True)
class ChunkRecord:
    id: str
    path: str
    language: str
    label: str
    text: str
    start_line: int
    end_line: int
    node_type: str


def collect_symbols(
    root_node: Any,
    source_bytes: bytes,
    path: str,
    language: str,
) -> list[SymbolRecord]:
    records: list[SymbolRecord] = []

    def walk(node: Any, containers: list[str]) -> None:
        kind = SYMBOL_KIND_BY_NODE_TYPE.get(getattr(node, "type", ""))
        next_containers = containers
        if kind:
            name_node = _extract_name_node(node)
            name = None
            if name_node is not None:
                name = _slice_source(
                    source_bytes,
                    name_node.start_point,
                    name_node.end_point,
                ).strip()
            if not name:
                name = _extract_node_name(node, source_bytes)
            if name:
                start_line, start_col = _point_to_line_col(node.start_point)
                end_line, end_col = _point_to_line_col(node.end_point)
                qualname = ".".join([*containers, name]) if containers else name
                name_start_line = None
                name_start_col = None
                name_end_line = None
                name_end_col = None
                if name_node is not None:
                    name_start_line, name_start_col = _point_to_line_col(name_node.start_point)
                    name_end_line, name_end_col = _point_to_line_col(name_node.end_point)
                records.append(
                    SymbolRecord(
                        name=name,
                        kind=kind,
                        path=path,
                        language=language,
                        start_line=start_line,
                        end_line=end_line,
                        start_col=start_col,
                        end_col=end_col,
                        node_type=node.type,
                        qualname=qualname,
                        name_start_line=name_start_line,
                        name_start_col=name_start_col,
                        name_end_line=name_end_line,
                        name_end_col=name_end_col,
                    )
                )
                next_containers = [*containers, name]

        for child in _named_children(node):
            walk(child, next_containers)

    walk(root_node, [])
    return records


def collect_references(
    root_node: Any,
    source_bytes: bytes,
    path: str,
    language: str,
    symbol_name: str,
    exclude_ranges: list[tuple[tuple[int, int], tuple[int, int]]] | None = None,
) -> list[dict[str, Any]]:
    exclude_ranges = exclude_ranges or []
    results: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        node_type = getattr(node, "type", "")
        if node_type in IDENTIFIER_NODE_TYPES:
            text = _slice_source(source_bytes, node.start_point, node.end_point)
            start_line, start_col = _point_to_line_col(node.start_point)
            end_line, end_col = _point_to_line_col(node.end_point)
            span = ((start_line, start_col), (end_line, end_col))
            if text == symbol_name and span not in exclude_ranges:
                results.append(
                    {
                        "path": path,
                        "language": language,
                        "node_type": node_type,
                        "text": text,
                        "start_line": start_line,
                        "end_line": end_line,
                        "start_col": start_col,
                        "end_col": end_col,
                    }
                )

        for child in _named_children(node):
            walk(child)

    walk(root_node)
    return results


def build_syntax_chunks(
    root_node: Any,
    source_text: str,
    path: str,
    language: str,
    max_chars: int = 1600,
) -> list[ChunkRecord]:
    source_bytes = source_text.encode("utf-8")
    symbols = collect_symbols(root_node, source_bytes, path, language)
    chunks: list[ChunkRecord] = []

    for symbol in symbols:
        text = _slice_source(
            source_bytes,
            (symbol.start_line - 1, symbol.start_col - 1),
            (symbol.end_line - 1, symbol.end_col - 1),
        )
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n..."
        chunks.append(
            ChunkRecord(
                id=f"{path}:{symbol.start_line}-{symbol.end_line}:{symbol.qualname}",
                path=path,
                language=language,
                label=symbol.qualname,
                text=text,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                node_type=symbol.node_type,
            )
        )

    if chunks:
        return chunks

    lines = source_text.splitlines()
    return [
        ChunkRecord(
            id=f"{path}:1-{max(len(lines), 1)}:file",
            path=path,
            language=language,
            label=path,
            text=source_text[:max_chars] if max_chars > 0 else source_text,
            start_line=1,
            end_line=max(len(lines), 1),
            node_type=getattr(root_node, "type", "root"),
        )
    ]


def resolve_scope(
    root_node: Any,
    source_bytes: bytes,
    path: str,
    language: str,
    line: int,
    column: int,
) -> dict[str, Any] | None:
    symbols = collect_symbols(root_node, source_bytes, path, language)
    best_match: SymbolRecord | None = None

    for symbol in symbols:
        starts_before = (symbol.start_line, symbol.start_col) <= (line, column)
        ends_after = (symbol.end_line, symbol.end_col) >= (line, column)
        if not (starts_before and ends_after):
            continue
        if best_match is None:
            best_match = symbol
            continue
        best_span = (best_match.end_line - best_match.start_line, best_match.end_col - best_match.start_col)
        current_span = (symbol.end_line - symbol.start_line, symbol.end_col - symbol.start_col)
        if current_span <= best_span:
            best_match = symbol

    if best_match is None:
        return None

    return {
        "path": best_match.path,
        "language": best_match.language,
        "name": best_match.name,
        "qualname": best_match.qualname,
        "kind": best_match.kind,
        "start_line": best_match.start_line,
        "end_line": best_match.end_line,
        "start_col": best_match.start_col,
        "end_col": best_match.end_col,
    }


def serialize_tree(
    node: Any,
    source_bytes: bytes,
    depth_limit: int = 3,
    _depth: int = 0,
) -> dict[str, Any]:
    start_line, start_col = _point_to_line_col(node.start_point)
    end_line, end_col = _point_to_line_col(node.end_point)
    payload = {
        "type": getattr(node, "type", "unknown"),
        "start_line": start_line,
        "end_line": end_line,
        "start_col": start_col,
        "end_col": end_col,
        "text": _slice_source(source_bytes, node.start_point, node.end_point)[:200],
    }
    if _depth >= depth_limit:
        payload["children"] = []
        return payload
    payload["children"] = [
        serialize_tree(child, source_bytes, depth_limit=depth_limit, _depth=_depth + 1)
        for child in _named_children(node)
    ]
    return payload


def _named_children(node: Any) -> list[Any]:
    named_children = getattr(node, "named_children", None)
    if named_children is not None:
        return list(named_children)
    children = getattr(node, "children", [])
    return [child for child in children if getattr(child, "is_named", True)]


def _extract_node_name(node: Any, source_bytes: bytes) -> str | None:
    child = _extract_name_node(node)
    if child is not None:
        text = _slice_source(source_bytes, child.start_point, child.end_point).strip()
        if text:
            return text

    for child in _named_children(node):
        if getattr(child, "type", "") in NAME_CHILD_CANDIDATES:
            text = _slice_source(source_bytes, child.start_point, child.end_point).strip()
            if text:
                return text
    return None


def _extract_name_node(node: Any) -> Any | None:
    for field_name in NAME_FIELD_CANDIDATES:
        if hasattr(node, "child_by_field_name"):
            child = node.child_by_field_name(field_name)
            if child is not None:
                return child
    return None


def _point_to_line_col(point: tuple[int, int]) -> tuple[int, int]:
    return point[0] + 1, point[1] + 1


def _slice_source(
    source_bytes: bytes,
    start_point: tuple[int, int],
    end_point: tuple[int, int],
) -> str:
    lines = source_bytes.decode("utf-8").splitlines(keepends=True)
    start_row, start_col = start_point
    end_row, end_col = end_point

    if not lines:
        return ""

    start_row = max(0, min(start_row, len(lines) - 1))
    end_row = max(0, min(end_row, len(lines) - 1))

    if start_row == end_row:
        return lines[start_row][start_col:end_col]

    parts = [lines[start_row][start_col:]]
    for row in range(start_row + 1, end_row):
        parts.append(lines[row])
    parts.append(lines[end_row][:end_col])
    return "".join(parts)
