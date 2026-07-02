from __future__ import annotations

from collections import defaultdict
from typing import Any


def span_tree_rows(records: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    by_id = {row["span_id"]: row for row in records}
    for row in records:
        parent = row.get("parent_span_id")
        children[parent if parent in by_id else None].append(row)

    rows: list[tuple[int, dict[str, Any]]] = []

    def visit(parent_id: str | None, depth: int) -> None:
        for child in children[parent_id]:
            rows.append((depth, child))
            visit(child["span_id"], depth + 1)

    visit(None, 0)
    return rows

