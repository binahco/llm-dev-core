# Contrato mínimo — `secure-base`

- **Fecha:** 2026-09-22
- **Estado:** aceptada
- **Origen:** §3.1 en `ARCHITECTURE.md`
- **Implementada en:** semana 4 (`packages/secure-base` v0.1.0, nacida dentro de `sec-check`)

Este documento es el contrato escrito contra el que se implementa la semana 4. Define la utilidad de
máscara que exige §3.1.1 y el perfil de declaración que alimentará los lints de `ci-pack` (sem. 7).

## 1. API conceptual

```python
detect(text) -> list[Finding]            # hallazgos tipados (sin mutar texto)
redact(text) -> RedactResult             # texto enmascarado + hallazgos
sanitize_for_prompt(text) -> RedactResult  # alias semántico para renderers
assert_redacted(text, profile?) -> list[Finding]  # violaciones de §3.1
```

```python
class Finding(BaseModel):
    type: str        # email | phone | ipv4 | credit_card | aws_access_key | github_token | private_key | bearer | url_userinfo
    match: str       # preview truncado (24 chars) — NUNCA el secreto completo
    offset: int      # offset del primer carácter
    length: int      # para reemplazos deterministas
    line: int        # 1-based
```

## 2. Reglas de la máscara

- **Unidireccional:** el secreto crudo no se conserva en ningún lugar del resultado. No hay operación inversa.
- **Determinista:** misma entrada → misma salida (mismo texto y mismos placeholders).
- **Placeholder:** `[REDACTED:<type>:<n>]`, con `n` por tipo (1-based, en orden de aparición).
- **`Finding.match` es un preview truncado**: suficiente para triaje, insuficiente para re-inyectar el secreto.
- **`detect` es no destructivo**: el scanner se usa antes de decidir qué se envía; `redact` produce la salida
  que sí puede cruzar el límite del prompt.

## 3. Perfil y lints (§3.1.1 → ci-pack)

- `SecurityProfile(data_types: list[str])`: qué tipos declara manejar el consumidor.
- `assert_redacted(text, profile) -> list[Finding]`: si el resultado **no está vacío**, el texto aún contiene
  secretos en claro declarados por el perfil → violación de la regla 1 de §3.1.
- El enforcement operativo (que el build falle si un prompt de producción llega con secretos) se implementa
  en `ci-pack` (sem. 7); `secure-base` es el motor que ese lint usaría.

## 4. Composición con el resto del core

- `secure-base` **no depende de `llm-client`** ni de `schema-validate`: es la hoja de la seguridad. Se compone
  en el renderer del consumidor (antes de construir los mensajes) y en el preámbulo del flujo.
- `llm-client` redacta `<variable>` en sus spans por contrato (ADR-1, §1); `secure-base` hace lo mismo aguas
  arriba, sobre el payload que podría entrar a un prompt.

## 5. Qué NO contrata este documento

- No define el lint anti-prompts (sem. 7, `ci-pack`): solo su motor de detección.
- No reemplaza el manejo de secretos de la máquina del desarrollador: no es un gestor de claves.
- No garantiza detección perfecta: los patrones son heurísticos; la prueba de que algo no se filtró es
  estructural (el texto que sale de `redact` no contiene ningún hallazgo).

## 6. Criterio de aceptación del contrato (semana 4)

- [x] `detect` encuentra los 9 tipos en un texto de prueba y no delira con código limpio.
- [x] `redact` es unidireccional y determinista: nada del secreto crudo sobrevive; mismo input → mismo output.
- [x] `sanitize_for_prompt` deja `assert_redacted(...) == []` (el texto que cruza al proveedor está limpio).
- [x] `assert_redacted(text, profile)` filtra por los tipos declarados.
- [x] Primer consumidor real: `sec-check` (sem. 4), que redacta diffs antes de enviarlos al LLM.