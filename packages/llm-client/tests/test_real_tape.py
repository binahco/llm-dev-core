import json
from pathlib import Path

import pytest
from llm_client import CompletionRequest, LlmClient, ReplayProvider
from llm_client.provider import ProviderRequest

CASSETTES = Path(__file__).parent / "cassettes"


def _real_tape() -> Path | None:
    matches = sorted(CASSETTES.glob("complete-*.jsonl")) if CASSETTES.is_dir() else []
    return matches[0] if matches else None


@pytest.mark.skipif(_real_tape() is None, reason="tape real no grabada (record_tape_opencode.py)")
def test_real_tape_replays_without_key() -> None:
    tape = _real_tape()
    entry = json.loads(tape.read_text().splitlines()[0])
    request = ProviderRequest(model=entry["model"], messages=entry["request"])

    replay = ReplayProvider(CASSETTES, record=False)
    response = replay.complete(request)

    assert response.model == entry["model"]
    assert response.text.strip()


@pytest.mark.skipif(_real_tape() is None, reason="tape real no grabada (record_tape_opencode.py)")
def test_real_tape_replays_through_client_without_key() -> None:
    tape = _real_tape()
    entry = json.loads(tape.read_text().splitlines()[0])
    replay = ReplayProvider(CASSETTES, record=False)

    def renderer(_prompt_id: str, _version: str, _variables: dict) -> list[dict]:
        return entry["request"]

    client = LlmClient(replay, consumer_repo="commit-cli", model_aliases={"fast": entry["model"]}, renderer=renderer)
    result = client.complete(
        CompletionRequest(
            prompt_id="commit-message-generator",
            prompt_version="0.1.0",
            variables={},
            model_alias="fast",
        )
    )

    assert result.raw_text.strip()
    assert result.provider == "replay"
    assert result.validation.ok