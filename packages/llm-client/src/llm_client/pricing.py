from __future__ import annotations

from decimal import Decimal

MODEL_PRICES_USD_PER_1K: dict[str, tuple[float, float]] = {
    "big-pickle": (0.0, 0.0),
}

DEFAULT_ALIASES: dict[str, str] = {"fast": "big-pickle"}


def resolve_model(model_alias: str, aliases: dict[str, str] | None = None) -> str:
    table = DEFAULT_ALIASES if aliases is None else aliases
    return table.get(model_alias, model_alias)


def cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> Decimal:
    if input_tokens is None or output_tokens is None:
        return Decimal("0")
    in_price, out_price = MODEL_PRICES_USD_PER_1K.get(model, (0.0, 0.0))
    value = input_tokens / 1000 * in_price + output_tokens / 1000 * out_price
    return Decimal(str(round(value, 6)))