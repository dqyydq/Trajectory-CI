from types import SimpleNamespace

from eval.checks.builtin import max_steps, response_contains, tool_called


def test_tool_called_finds_openai_tool_call_name() -> None:
    trajectory = SimpleNamespace(
        spans=[
            SimpleNamespace(
                response_body={
                    "choices": [
                        {"message": {"tool_calls": [{"function": {"name": "classify_video"}}]}}
                    ]
                }
            )
        ]
    )

    assert tool_called(trajectory, "classify_video").passed is True


def test_max_steps_counts_spans() -> None:
    trajectory = SimpleNamespace(spans=[object(), object()])

    assert max_steps(trajectory, 2).passed is True
    assert max_steps(trajectory, 1).passed is False


def test_response_contains_searches_response_content() -> None:
    trajectory = SimpleNamespace(
        spans=[SimpleNamespace(response_body={"choices": [{"message": {"content": "分类完成"}}]})]
    )

    assert response_contains(trajectory, "分类完成").passed is True