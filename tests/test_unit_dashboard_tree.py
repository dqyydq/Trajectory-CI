from dashboard.tree import span_tree_rows


def test_span_tree_rows_supports_nested_spans() -> None:
    records = [
        {"span_id": "root", "parent_span_id": None},
        {"span_id": "child", "parent_span_id": "root"},
        {"span_id": "grandchild", "parent_span_id": "child"},
    ]

    rows = span_tree_rows(records)

    assert [(depth, row["span_id"]) for depth, row in rows] == [
        (0, "root"),
        (1, "child"),
        (2, "grandchild"),
    ]
