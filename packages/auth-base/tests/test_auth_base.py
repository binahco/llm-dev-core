"""Tests de auth-base: falla cerrado, huella sin secreto, reloj inyectado, 401/403 (D4)."""

from __future__ import annotations

import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from llm_client import LlmClient
from llm_client.provider import ProviderRequest, ProviderResponse
from web_api_base import create_app

from auth_base import (
    NO_AUTENTICADO,
    SIN_PERMISO,
    AuthError,
    AuthEvent,
    KeyStore,
    Principal,
    register_auth,
    require,
    verifier_of,
)
from auth_base.models import AUSENTE, DESCONOCIDA, MALFORMADA, REVOCADA, SECRETO_INCORRECTO, VENCIDA


class FakeClock:
    def __init__(self, now: float = 1_700_000_000.0) -> None:
        self._now = now

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class StubProvider:
    name = "stub"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(text="{}", model=request.model)

    def stream(self, request: ProviderRequest) -> list[str]:
        return ["{}"]


def _torcida(key: str) -> str:
    return key[:-1] + ("A" if key[-1] != "A" else "B")


def test_issue_devuelve_el_secreto_una_vez_y_guarda_su_huella() -> None:
    clock = FakeClock()
    store = KeyStore(clock=clock)
    issued = store.issue("fleet-bot", scopes=["llm:complete"], ttl_seconds=60)
    key_id, secret = issued.key.split(".")
    assert (issued.key_id, len(key_id), len(secret)) == (key_id, 12, 43)
    record = store.get(key_id)
    assert record.verifier == verifier_of(secret)
    assert (issued.expires_at, record.created_at) == (clock.now() + 60, clock.now())
    exportado = json.dumps(store.export())
    assert secret not in exportado and issued.key not in exportado


def test_autentica_redondo_y_dice_quien_llama_y_que_puede() -> None:
    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["llm:complete", "prompts:read"])
    principal = store.authenticate(issued.key)
    assert (principal.client, principal.key_id) == ("fleet-bot", issued.key_id)
    assert sorted(principal.scopes) == ["llm:complete", "prompts:read"]
    assert store.authorize(principal, "llm:complete")
    assert not store.authorize(principal, "keys:admin")


def test_falla_cerrado_ante_todo_lo_que_no_es_una_clave_viva() -> None:
    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["llm:complete"])
    _, secret = issued.key.split(".")
    for presentada in (None, "", "basura", f"000000000000.{secret}", secret, f"{issued.key}.", _torcida(issued.key), "a" * 201):
        assert store.authenticate(presentada) is None
    assert KeyStore().authenticate(issued.key) is None  # un store vacío no deja entrar a nadie


def test_revocada_y_vencida_no_entran_con_reloj_inyectado() -> None:
    clock = FakeClock()
    store = KeyStore(clock=clock)
    fija = store.issue("ci-scribe", scopes=["llm:complete"])
    temporal = store.issue("demo", scopes=["llm:complete"], ttl_seconds=60)
    assert store.authenticate(temporal.key) is not None
    clock.advance(59)
    assert store.authenticate(temporal.key) is not None
    clock.advance(1)
    assert store.authenticate(temporal.key) is None  # vence a los 60 s exactos
    assert store.authenticate(fija.key) is not None  # la que no vence, no vence
    assert store.revoke(fija.key_id) and store.authenticate(fija.key) is None
    assert store.revoke("000000000000") is False
    assert store.revoke(fija.key_id) is False  # ya estaba revocada: no cambia nada
    assert store.get(fija.key_id).revoked  # se quita sin borrarla


def test_una_clave_sin_permisos_o_con_comodin_no_se_emite() -> None:
    store = KeyStore()
    with pytest.raises(ValueError, match="sin permisos"):
        store.issue("x", scopes=[])
    for permiso in ("*", "llm:*", "llm complete"):
        with pytest.raises(ValueError, match="comodines"):
            store.issue("x", scopes=[permiso])
    with pytest.raises(ValueError, match="cliente"):
        store.issue("  ", scopes=["llm:complete"])
    with pytest.raises(ValueError, match="ttl_seconds"):
        store.issue("x", scopes=["llm:complete"], ttl_seconds=0)
    assert store.list() == []


def test_la_auditoria_sabe_por_que_y_nunca_lleva_el_secreto() -> None:
    clock = FakeClock()
    events: list[AuthEvent] = []
    store = KeyStore(clock=clock, audit=events.append)
    issued = store.issue("fleet-bot", scopes=["llm:complete"])
    temporal = store.issue("demo", scopes=["llm:complete"], ttl_seconds=60)
    secret = issued.key.split(".")[1]
    t0 = clock.now()

    for presentada in (None, "basura", f"abcdefabcdef.{secret}", _torcida(issued.key)):
        with pytest.raises(AuthError) as fallo:
            store.check(presentada, "llm:complete")
        assert (fallo.value.status_code, fallo.value.error, fallo.value.detail) == (401, NO_AUTENTICADO, "credencial ausente o inválida")
    with pytest.raises(AuthError) as fallo:
        store.check(issued.key, "keys:admin")
    assert (fallo.value.status_code, fallo.value.error, fallo.value.detail) == (403, SIN_PERMISO, "la clave no tiene el permiso 'keys:admin'")

    store.revoke(issued.key_id)
    with pytest.raises(AuthError):
        store.check(issued.key, "llm:complete")
    clock.advance(60)
    with pytest.raises(AuthError):
        store.check(temporal.key, "llm:complete")
    otra = store.issue("otro", scopes=["llm:complete"])
    assert store.check(otra.key, "llm:complete").client == "otro"

    assert [e.reason for e in events] == [AUSENTE, MALFORMADA, DESCONOCIDA, SECRETO_INCORRECTO, "", REVOCADA, VENCIDA, ""]
    assert [e.outcome for e in events] == ["no_autenticado"] * 4 + ["sin_permiso", "no_autenticado", "no_autenticado", "ok"]
    assert events[-1].scope == "llm:complete" and events[-1].key_id == otra.key_id
    assert events[2].key_id == "abcdefabcdef" and events[2].client is None  # del id que no existe se sabe el id, no el cliente
    assert [e.at for e in events] == [t0] * 6 + [t0 + 60] * 2  # cada intento lleva la hora en que ocurrió
    assert secret not in json.dumps([e.model_dump() for e in events])


def test_export_y_load_conservan_las_claves_y_su_estado() -> None:
    clock = FakeClock()
    store = KeyStore(clock=clock)
    viva = store.issue("fleet-bot", scopes=["llm:complete"])
    muerta = store.issue("viejo", scopes=["llm:complete"])
    temporal = store.issue("demo", scopes=["llm:complete"], ttl_seconds=30)
    store.revoke(muerta.key_id)
    cargado = KeyStore.load(store.export(), clock=clock)
    assert [r.key_id for r in cargado.list()] == sorted([viva.key_id, muerta.key_id, temporal.key_id])
    assert cargado.authenticate(viva.key) is not None
    assert cargado.authenticate(muerta.key) is None
    clock.advance(30)
    assert cargado.authenticate(temporal.key) is None


def test_la_huella_es_determinista() -> None:
    assert verifier_of("secreto") == verifier_of("secreto")
    assert len(verifier_of("secreto")) == 64 and verifier_of("secreto") != verifier_of("secreto ")


# --------------------------------------------------------------------------
# el puente HTTP, sobre una app real de web-api-base
# --------------------------------------------------------------------------
# `leer`/`escribir`: no se llaman `/docs`, que es la ruta que FastAPI reserva para su Swagger UI.
def _app(store: KeyStore) -> FastAPI:
    app = create_app("svc", "0.1.0", client=LlmClient(StubProvider()), enable_llm_endpoint=False)
    register_auth(app)
    leer = require(store, "docs:read")
    escribir = require(store, "docs:write")

    @app.get("/leer", dependencies=[Depends(leer)])
    async def leer_docs() -> dict:
        return {"ok": True}

    @app.post("/escribir", dependencies=[Depends(escribir)])
    async def escribir_docs() -> dict:
        return {"ok": True}

    @app.get("/quien")
    async def quien(principal: Principal = Depends(leer)) -> dict:
        return {"client": principal.client, "key_id": principal.key_id}

    return app


def _bearer(issued) -> dict:
    return {"Authorization": f"Bearer {issued.key}"}


def test_http_sin_clave_es_401_pide_bearer_y_la_salud_sigue_publica() -> None:
    client = TestClient(_app(KeyStore()))
    resp = client.get("/leer")
    # El manejador de `Exception` de web-api-base no se traga esto como 500: gana el de `AuthError`.
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert resp.json() == {"error": "no_autenticado", "detail": "credencial ausente o inválida", "code": 401}
    assert client.get("/health").status_code == 200


def test_http_clave_invalida_o_esquema_equivocado_sigue_siendo_401() -> None:
    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["docs:read"])
    client = TestClient(_app(store))
    for cabecera in ("Basic abc", "Bearer", "Bearer 000000000000.nada", f"bearer {_torcida(issued.key)}"):
        assert client.get("/leer", headers={"Authorization": cabecera}).status_code == 401


def test_http_con_clave_valida_pasa_y_dice_quien() -> None:
    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["docs:read"])
    client = TestClient(_app(store))
    assert client.get("/leer", headers=_bearer(issued)).status_code == 200
    assert client.get("/quien", headers={"Authorization": f"bearer {issued.key}"}).json() == {"client": "fleet-bot", "key_id": issued.key_id}


def test_http_clave_sin_permiso_es_403_no_401() -> None:
    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["docs:read"])
    resp = TestClient(_app(store)).post("/escribir", headers=_bearer(issued))
    assert resp.status_code == 403
    assert resp.json() == {"error": "sin_permiso", "detail": "la clave no tiene el permiso 'docs:write'", "code": 403}
    assert "www-authenticate" not in resp.headers


def test_http_revocar_deja_fuera_a_la_clave() -> None:
    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["docs:read"])
    client = TestClient(_app(store))
    assert client.get("/leer", headers=_bearer(issued)).status_code == 200
    store.revoke(issued.key_id)
    assert client.get("/leer", headers=_bearer(issued)).status_code == 401
