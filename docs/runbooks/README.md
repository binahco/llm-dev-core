# Runbooks

Procedimientos documentados para situaciones que no deberían improvisarse. Estado actual: índices vacíos — los runbooks se escriben cuando existe contenido real.

## Previstos

| Runbook | Cuándo | Estado |
|---|---|---|
| **Degradación** (compat-last-5 FAIL → revert/hotfix/bump) | sem. 13, con v1.0 | pendiente |
| **Re-baseline** de un dataset congelado | sem. 5+, con test-kit | pendiente |
| **Expulsión** de un módulo seed sin segundo consumidor | sem. 15+ | pendiente |

Regla general (§3.1, §8.1): la degradación del core nunca queda rota en `main`; el re-baseline nunca es un ajuste silencioso; la expulsión siempre con migración documentada.