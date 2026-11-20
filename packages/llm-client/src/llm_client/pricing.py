from __future__ import annotations

from decimal import Decimal

MODEL_PRICES_USD_PER_1K: dict[str, tuple[float, float]] = {
    "big-pickle": (0.0, 0.0),
}

DEFAULT_ALIASES: dict[str, str] = {"fast": "big-pickle"}


def resolve_model(model_alias: str, aliases: dict[str, str] | None = None) -> str:
    table = DEFAULT_ALIASES if aliases is None else aliases
    return table.get(model_alias, model_alias)


def price_key(model: str) -> str:
    """Clave de la tabla de precios para un nombre de modelo.

    Los proveedores nombran el modelo con el prefijo de la casa (`opencode/big-pickle`)
    mientras que la tabla lo keya sin prefijo (`big-pickle`). Buscar el nombre tal cual
    fallaba y devolvía 0, que es indistinguible de "el modelo es gratis": por eso se
    prueba también el último segmento del `provider/model`.
    """
    if model in MODEL_PRICES_USD_PER_1K:
        return model
    tail = model.rsplit("/", 1)[-1]
    return tail if tail in MODEL_PRICES_USD_PER_1K else model


def model_price_known(model: str) -> bool:
    """Si el modelo tiene precio en la tabla. Distingue "gratis" de "desconocido".

    `cost_usd` devuelve 0 en ambos casos, así que un modelo que se agregue al cliente
    sin pricedarse aparece como gratis y el cap de costo no dispara. Quien reporte
    costos debe consultar esto primero.
    """
    return model in MODEL_PRICES_USD_PER_1K or model.rsplit("/", 1)[-1] in MODEL_PRICES_USD_PER_1K


def cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> Decimal:
    if input_tokens is None or output_tokens is None:
        return Decimal("0")
    in_price, out_price = MODEL_PRICES_USD_PER_1K.get(price_key(model), (0.0, 0.0))
    value = input_tokens / 1000 * in_price + output_tokens / 1000 * out_price
    return Decimal(str(round(value, 6)))