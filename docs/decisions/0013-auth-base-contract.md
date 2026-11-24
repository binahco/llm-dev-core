# Contrato mínimo — `auth-base`

- **Fecha:** 2026-11-23
- **Estado:** aceptada
- **Origen:** el calendario C1–C18 (§5): `auth-base` (C14) es la capa de acceso de los
  servicios del core. El ADR-5 la dejó fuera a propósito ("Auth llega con `auth-base`,
  sem 25") y cuatro consumidores lo dejaron escrito en sus limitaciones: `eval-api`,
  `llm-gateway`, `evidence-api` y `prompt-hub` sirven HTTP sin saber quién llama.
- **Implementada en:** semana 25 (`packages/auth-base` v0.1.0, dentro de `llm-dev-core`
  v1.5.0; primer consumidor: `key-gate`)

Un servicio sin autenticación no tiene clientes: tiene invitados. Cualquiera que alcance
el puerto puede gastar el presupuesto de `POST /llm`, y el límite de ritmo —cuando lo
hay— es el mismo para todos, así que un solo invitado agota al resto. Lo que falta no es
un sistema de login: es responder dos preguntas antes de cada ruta, y fallar cerrado.

## 1. API conceptual

```python
from auth_base import KeyStore, register_auth, require

store = KeyStore(clock=my_clock, audit=eventos.append)   # reloj inyectable (D4)
issued = store.issue("fleet-bot", scopes=["llm:complete"], ttl_seconds=None)
issued.key            # "<key_id>.<secreto>": el secreto aparece aquí, una sola vez
store.authenticate(presented)        # -> Principal | None
store.authorize(principal, scope)    # pertenencia exacta al conjunto de permisos
store.revoke(key_id)                 # se quita sin borrarla
store.export()                       # registros sin secreto: lo que el consumidor persiste

register_auth(app)                   # AuthError -> el error uniforme de web-api-base
@app.post("/llm", dependencies=[Depends(require(store, "llm:complete"))])
def llm(req): ...                    # un evento de auditoría por intento
```

| Condición | Código | `error` | Razón fina (solo auditoría) |
|---|---|---|---|
| Sin credencial, mal formada, desconocida, con secreto incorrecto, revocada o vencida | 401 | `no_autenticado` | `ausente`, `malformada`, `desconocida`, `secreto_incorrecto`, `revocada`, `vencida` |
| Clave válida sin el permiso de la ruta | 403 | `sin_permiso` | — |

## 2. Reglas

- **Falla cerrado.** Lo que no está en el store no entra, y un store vacío no deja entrar
  a nadie: no existe el modo "abierto por defecto".
- **El secreto se muestra una vez y no se guarda.** `issue` devuelve `<key_id>.<secreto>`;
  el store guarda `sha256(secreto)` y compara con `hmac.compare_digest`. Alcanza porque
  la clave son 256 bits aleatorios (`secrets`): no hay entropía baja que proteger. Ante
  un id desconocido se calcula y se compara igual — mismo trabajo, misma respuesta.
- **Permisos exactos.** `authorize` es pertenencia a un conjunto: sin comodines (`*` se
  rechaza al emitir), sin herencia, y una clave sin permisos no se emite. Una clave por
  uso, con solo el permiso que necesita (§3.1: permisos mínimos, nada de alcance
  excesivo para demos).
- **Al que llama no se le dice por qué; a la auditoría sí.** Fuera hay dos errores. El
  `AuthEvent` trae la razón fina, el cliente y el `key_id` — que es público — y nunca el
  secreto. El estado de una clave (revocada, vencida) se revela al operador solo después
  de un secreto correcto.
- **La hoja no cambia.** `KeyStore` es stdlib + pydantic con reloj inyectable
  (`AuthClock`), como `bot-base` y `agent-loop`, y no conoce HTTP. `register_auth` y
  `require` son el puente a una app de `web-api-base`, que no se toca: la forma del error
  se importa (`ErrorBody`), no se copia, y un 401 siempre pide `WWW-Authenticate: Bearer`.

## 3. Qué NO contrata este documento

- **Contraseñas de personas.** Una huella rápida sirve para secretos aleatorios de 256
  bits, no para "gato123": eso pide una KDF lenta con sal, y no es este módulo.
- **OAuth, JWT firmados, sesiones de navegador, cookies, refresh tokens, MFA y
  recuperación de cuenta.** Aquí el servicio emite la clave y el cliente la presenta.
- **Directorio de usuarios y roles.** Un cliente es un string; sus permisos viven en la
  clave que usa.
- **Ritmo por cliente:** se compone con `cache-ratelimit` (un `RateLimiter` por
  `Principal.client`), como hace `key-gate`.
- **Persistencia, transporte (TLS) y detección de intrusión.** El consumidor guarda
  `export()` donde quiera; HTTPS es del despliegue; un patrón de rechazos se narra, no se
  bloquea solo.

## 4. Criterio de aceptación del contrato (semana 25)

- [x] `issue` devuelve el secreto una vez; el store y su `export()` solo guardan la huella.
- [x] Falla cerrado ante credencial ausente, mal formada, desconocida, incorrecta,
      revocada y vencida — con reloj inyectable para el vencimiento.
- [x] `authorize` por pertenencia exacta; una clave sin permisos o con comodín no se emite.
- [x] Un `AuthEvent` por intento, con la razón fina y sin el secreto.
- [x] `register_auth`/`require` sobre una app de `web-api-base`: 401 con
      `WWW-Authenticate`, 403 sin él, cuerpo de error uniforme, `/health` sigue pública.
- [x] Primer consumidor real: `key-gate` (sem. 25) — el gateway `POST /llm` de
      `llm-gateway` con acceso por clave, ritmo por cliente y registro de accesos.
