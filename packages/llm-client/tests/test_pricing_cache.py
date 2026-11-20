from decimal import Decimal

from llm_client import CompletionRequest, LlmClient, ResponseCache, TokenUsage, ValidationResult
from llm_client.pricing import cost_usd, model_price_known, price_key, resolve_model
from llm_client.span import Span

from .conftest import FakeProvider


def test_resolve_model_alias() -> None:
    assert resolve_model("fast") == "big-pickle"
    assert resolve_model("unknown-model") == "unknown-model"
    assert resolve_model("fast", {"fast": "otra-maquina"}) == "otra-maquina"


def test_cost_usd_free_model_is_zero() -> None:
    assert cost_usd("big-pickle", 1000, 500) == Decimal("0")
    assert cost_usd("no-existe", 1000, 500) == Decimal("0")


def test_price_key_strips_provider_prefix() -> None:
    """Los proveedores nombran `opencode/big-pickle`; la tabla keya `big-pickle`."""
    assert price_key("opencode/big-pickle") == "big-pickle"
    assert price_key("big-pickle") == "big-pickle"
    assert price_key("marca/modelo-que-no-esta") == "marca/modelo-que-no-esta"


def test_model_price_known_distingue_gratis_de_desconocido() -> None:
    """`cost_usd` da 0 para los dos casos; esto es lo que los separa.

    Sin esta separación, un modelo de pago agregado al cliente sin pricedarse
    reporta $0 y el cap de costo nunca dispara.
    """
    assert model_price_known("big-pickle") is True
    assert model_price_known("opencode/big-pickle") is True
    assert model_price_known("modelo-de-pago-sin-preciar") is False


def test_cost_usd_without_usage_is_zero() -> None:
    assert cost_usd("big-pickle", None, None) == Decimal("0")


def test_cache_in_memory() -> None:
    cache = ResponseCache()
    request = CompletionRequest(prompt_id="p", model_alias="fast", variables={"a": 1})
    result = LlmClient(FakeProvider()).complete(request)
    cache.put("k", result)
    assert cache.get("k").span_id == result.span_id


def test_cache_file_persistence(tmp_path) -> None:
    path = tmp_path / "cache.jsonl"
    cache = ResponseCache(path)
    request = CompletionRequest(prompt_id="p", model_alias="fast", variables={"a": 1})
    result = LlmClient(FakeProvider()).complete(request)
    cache.put("k", result)

    reloaded = ResponseCache(path)
    assert reloaded.get("k") is not None
    assert reloaded.get("k").span_id == result.span_id


def test_span_as_jsonl() -> None:
    span = Span(
        consumer_repo="commit-cli",
        prompt_id="p",
        prompt_version="0.1.0",
        model_alias="fast",
        model="big-pickle",
        provider="fake",
    )
    assert '"span_id":' in span.as_jsonl()
    assert '"consumer_repo":"commit-cli"' in span.as_jsonl()