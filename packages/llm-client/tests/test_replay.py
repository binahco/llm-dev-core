from llm_client import CompletionRequest, LlmClient, ReplayProvider, TokenUsage
from llm_client.provider import ProviderRequest

from .conftest import FakeProvider


def _request() -> CompletionRequest:
    return CompletionRequest(
        prompt_id="commit-message-generator",
        prompt_version="0.1.0",
        variables={"diff": "add foo"},
        model_alias="fast",
    )


def renderer(_prompt_id: str, _version: str, variables: dict) -> list[dict]:
    return [{"role": "user", "content": f"diff: {variables['diff']}"}]


def test_replay_complete_records_and_replays_without_key(tmp_path) -> None:
    inner = FakeProvider(text="feat: add foo", usage=TokenUsage(input_tokens=12, output_tokens=6))
    recorder = ReplayProvider(tmp_path, record=True, inner=inner)
    request = ProviderRequest(model="big-pickle", messages=renderer("p", "0.1.0", {"diff": "add foo"}))
    recorded = recorder.complete(request)
    assert inner.complete_calls == 1

    replay = ReplayProvider(tmp_path, record=False)
    replayed = replay.complete(request)
    assert replayed.text == recorded.text == "feat: add foo"
    assert replayed.usage.input_tokens == 12

    client = LlmClient(replay, consumer_repo="commit-cli", renderer=renderer)
    result = client.complete(_request())
    assert result.raw_text == "feat: add foo"
    assert result.provider == "replay"
    assert result.validation.ok is True
    assert result.span_id


def test_replay_stream_records_and_replays_chunks(tmp_path) -> None:
    inner = FakeProvider(stream_chunks=["feat: ", "add foo"])
    recorder = ReplayProvider(tmp_path, record=True, inner=inner)
    request = ProviderRequest(model="big-pickle", messages=renderer("p", "0.1.0", {"diff": "add foo"}))
    chunks = recorder.stream(request)
    assert "".join(chunks) == "feat: add foo"

    replay = ReplayProvider(tmp_path, record=False)
    replayed = replay.stream(request)
    assert replayed == ["feat: ", "add foo"]

    client = LlmClient(replay, consumer_repo="commit-cli", renderer=renderer)
    result = client.stream(_request())
    assert result.raw_text == "feat: add foo"