from app.proxy.streaming import aggregate_openai_stream, ensure_stream_usage, parse_sse_data_line


def test_ensure_stream_usage_adds_include_usage() -> None:
    body = {"model": "gpt-test", "stream": True}

    assert ensure_stream_usage(body)["stream_options"] == {"include_usage": True}


def test_parse_and_aggregate_stream_chunks() -> None:
    first = parse_sse_data_line(
        b'data: {"id":"abc","model":"gpt-test","choices":[{"delta":{"content":"hi"}}]}\n'
    )
    second = parse_sse_data_line(
        b'data: {"id":"abc","model":"gpt-test","choices":[],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}\n'
    )

    aggregated = aggregate_openai_stream([first, second])

    assert aggregated["choices"][0]["message"]["content"] == "hi"
    assert aggregated["usage"]["total_tokens"] == 3

