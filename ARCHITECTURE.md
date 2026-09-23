# ARCHITECTURE.md — llm-dev-core

> **Estado:** v0.4 (seed revisado) · **Última revisión:** 2026-09-22
> **Audiencia:** yo en 52 semanas, cualquiera que revise este repo, y entrevistadores técnicos.

---

## 1. La idea

**52 proyectos en 52 semanas no son 52 repos: son un solo sistema acumulativo.**

La tentación del desarrollador asistido por LLM es acumular demos desconectadas: cada una con su propio wrapper del API, su propio manejo de errores y su propio logging. Eso produce *volumen*, no *capacidad*. El año 2026 está lleno de portfolios así, y todos dicen lo mismo: "sé llamar a una API".

Este repo existe para hacer lo contrario: **cada semana se construye un proyecto nuevo consumiendo infraestructura de semanas anteriores**. La complejidad no se suma, se *reutiliza*. Y la reutilización no es un ahorro de tiempo: es la prueba de que las abstracciones son correctas. Una abstracción que solo se usa una vez es una hipótesis; una que se usa 30 veces es un diseño.

El core es la acumulación física de esa idea.

## 2. El objetivo

Construir, en 52 semanas, un paquete publicado y versionado que sea la base verificable de 52 proyectos reales en GitHub, demostrando no que puedo *generar código con un LLM*, sino que puedo **dirigir, acumular, versionar y mantener** código asistido por LLM.

El calendario es un grafo de dependencias, no un reloj: la semana es un *número de secuencia*. Si una semana no existe (vida, enfermedad, una entrevista real), el número se salta y lo que se preserva es la cadena de acumulación, no la fecha.

| Métrica | Meta |
|---|---|
| Proyectos consumidores publicados | 52 |
| Superficie nueva por proyecto (semanas de composición) | ≤ 30% (≥ 70% reutilización) |
| Llamadas a LLM que pasan por `llm-client` | 100%, sin excepciones |
| Prompts con metadatos desde sem. 2; en `prompt-registry` desde sem. 13 | 100% de los prompts en producción |
| Prompts nuevos con eval desde la sem. 5 | 100% |
| Evals en CI desde la semana 5 | en todo consumidor |
| Retrofittings documentados | ≥ 5 |
| Releases | v1.0 (sem. 13) → v2.0 (sem. 26) → v3.0 (sem. 39) → v4.0 (sem. 52, solo si hay consumidores que lo justifiquen; si no, consolidación) |
| Compat check (core vs. consumidores) | desde v1.0, en cada merge |
| Página de evidencia auto-generada | viva desde v1.0 |

Si al final del año el core no tiene consumidores reales más allá de mí, habré construido 52 demos y este documento será una mentira elegante. La meta es que ningún proyecto del año pueda existir sin él.

### 2.1 Cómo se verificarán las métricas

Las métricas de este proyecto no son aspiracionales. Cada una tiene una fuente de verdad y, cuando es posible, una verificación automática que rompe el build.

| Métrica | Fuente de verdad | Verificación |
|---|---|---|
| Proyectos consumidores publicados | Repos semanales | Topic `llm-dev-consumer` + `core-consumer.yml` |
| Superficie nueva ≤ 30% | Manifest del consumidor | `new_surface` y `reused_modules` declarados y revisados |
| Llamadas LLM vía `llm-client` | Código | Lint anti-imports directos: el build falla si un repo importa el SDK fuera de `llm-client` |
| Prompts en el registry | Archivos de prompts | Lint anti-prompts inline + frontmatter obligatorio desde sem. 2 |
| Todo prompt nuevo tiene eval (desde sem. 5) | Frontmatter `eval` + dataset | `make validate-consumer` rompe si el prompt referencia un eval que no existe / con dataset vacío |
| Evals en CI desde sem. 5 | CI del consumidor | Job `eval-smoke` obligatorio en la plantilla |
| Retrofittings documentados | Issues/PRs | Label `retrofit` + plantilla antes/después |
| Compat check | CI del core | Workflow `compat-last-5` en cada merge a `main` |

Cada consumidor declara en la raíz de su repo un manifest que es a la vez contrato e inventario:

```yaml
# core-consumer.yml
week: 14
name: contract-reviewer
core_version: 1.3.0
reused_modules:
  - llm-client
  - schema-validate
  - prompt-registry
  - web-api-base
  - test-kit
new_surface:
  - multi-tenant contract workspace
  - clause versioning
estimated_new_surface: 25%
```

El porcentaje es estimado; no puede ser perfectamente automático. Pero el acto de declararlo obliga a pensar en reutilización, y junto al lint anti-imports hace que la métrica sea auditable, no prometida.

El 70/30 solo aplica a **semanas de composición**. Las **semanas-seed** (donde nace un módulo del core) se miden por otra vara: el módulo extraído, su contrato y su primer consumidor. Si no se distinguen, las semanas 2–7 parecen "mal planteadas" bajo el principio 4, cuando son la excepción explícita y deseada.

## 3. Principios no negociables

Los principios son **invariantes ejecutables**, no aspiraciones: cada uno tiene un lint o un job de CI que lo hace cumplir (ver §2.1). Lo no verificado no es un principio, es una anécdota.

1. **Toda llamada a un LLM pasa por `llm-client`.** Sin excepciones, ni siquiera en spikes. Lo no medido no se refactoriza. *Verificación:* el build falla si hay llamadas al SDK del proveedor fuera de `llm-client`.
2. **Todo prompt vive versionado con metadatos.** Los prompts son código: se versionan, se evalúan y se revierten como cualquier otro cambio. Desde sem. 2 en `/prompts` (frontmatter obligatorio); desde sem. 13 en el paquete `prompt-registry`. *Verificación:* lint de frontmatter y anti-prompts inline.
3. **La salida de un LLM es input no confiable y acción no confiable.** Todo pasa por `schema-validate` antes de tocarse; las herramientas de agentes operan con allowlist, sandbox y confirmación explícita (§3.1).
4. **No existe "proyecto desde cero".** Si una semana de composición propone algo que no reutiliza ≥70% del core, la semana está mal planteada: se recorta alcance, nunca calidad. Las semanas-seed son la excepción explícita: su alcance es el módulo nuevo más su primer consumidor, y se declaran como tales en el manifest.
5. **El excedente no se corta, se traslada.** Si una semana se desborda, el sobrante es la primera tarea de la siguiente, como mejora al core. El calendario se mantiene; la deuda queda visible.
6. **El core nace de los consumidores, no antes.** Nada entra al core por elegancia: entra porque dos proyectos lo necesitaron, porque la semana 13/26/39/52 lo consolidó, o porque la regla del tercer uso (D12) lo declaró.

### 3.1 Seguridad operativa

Muchos proyectos LLM fallan exactamente aquí: prompts con datos reales, agentes con permisos excesivos, scrapers sin control, costos sin techo.

1. **Los secretos y datos sensibles no entran en prompts sin redacción.** El core ofrece utilidades de máscara para emails, tokens, claves, teléfonos y datos personales.
2. **La salida del LLM es acción no confiable.** Las herramientas de agentes operan con permisos mínimos, allowlist y sandbox; las acciones irreversibles requieren confirmación explícita.
3. **Los proveedores LLM son procesadores externos.** Cada consumidor declara qué datos envía, con qué retención y bajo qué configuración de privacidad.
4. **Scraping y acceso externo respetan límites.** Rate limiting, caché, `robots.txt` cuando aplique y respeto a los términos de servicio.
5. **Toda integración con GitHub o APIs externas usa permisos mínimos.** Nada de tokens con alcance excesivo para demos.
6. **El costo de llamadas y evals tiene techo.** Presupuesto declarado por consumidor (§8.1); cualquier llamada que exceda su cap se registra como anomalía, no como gasto normal.

## 4. Argumentación de las decisiones

**D1 — Un core publicado, no 52 repos independientes.** El formato natural del challenge es 1 repo por semana; eso es lo que casi todos hacen, y produce volumen sin capacidad. La decisión: un paquete `llm-dev-core` versionado del que los 52 repos dependen como librería, publicado en un registry público (PyPI) — de otra forma los repos no son instalables por un tercero y la historia de evidencia se rompe. Cualquiera pega un prompt en un README; muy pocos muestran un changelog que dice *"v2.0: breaking change — cost log por token; consumidores migrados: repos 14, 21, 25, 34"*. Mantener código con usuarios —aunque el único usuario sea mi yo del pasado— es la habilidad que separa dirección de copia-pega. *Trade-off aceptado:* acoplamiento; se mitiga con D8, no se niega.

**D2 — Monorepo para el core, repos separados para los consumidores.** Los módulos del core viven en un solo repo (cambios atómicos entre módulos, una sola CI); cada proyecto semanal es un repo propio con `depends on core ^x.y`. Los 52 repos existen como testigos públicos independientes, con su demo y su "Recicla de"; el core existe como ingeniería. Confundir ambos en un mega-repo destruiría las dos propiedades. *Trade-off aceptado:* consumidores congelados en versiones viejas; es semver funcionando.

**D3 — Semver honesto: `0.x` hasta la semana 13.** Durante el Q1 el core es `0.x`: "todo puede romperse". En la semana 13, con 12 consumidores reales detrás, se congela **v1.0** y empiezan las garantías. Prometer estabilidad sin usuarios es teatro; esperar a que 12 proyectos sufran mis abstracciones antes de fijar contratos es el orden correcto. Por la misma regla, cada hito (26, 39, 52) solo publica major si hay consumidores que lo justifiquen; si no, es un hito de consolidación sin release.

**D4 — `llm-client` con telemetría desde el día 1 (sem. 2).** El primer módulo del core —nacido en un CLI trivial de commits— ya incluye retry con backoff, streaming, JSON mode y **log estructurado por llamada**. En aplicaciones LLM, el costo no es una métrica de negocio secundaria: es parte del runtime. Si no se observa desde el día 1, el sistema no es operable.

Lo que no se retrofittea gratis no es el sink de datos: es el **formato del span**. El schema es **contrato público de `llm-client` desde la semana 2**, no propiedad de `cost-obs` ni de nadie. Si 37 semanas de spans viven en JSONL heterogéneos por repo, la semana 39 hereda un problema de datos, no un dataset. Campos mínimos:

```text
trace_id  ·  consumer_repo  ·  prompt_id  ·  prompt_version  ·  model_alias
model  ·  provider  ·  tokens_input  ·  tokens_output  ·  latency_ms  ·  cost_usd
retry_count  ·  cache_hit  ·  status  ·  call_skipped  ·  retry_unnecessary
```

`call_skipped` y `retry_unnecessary` capturan la pregunta que importa en la semana 39: no cuánto costó la llamada, sino **si se necesitaba**. El log de costo dice cuánto gastaste; el log de utilidad dice cuánto tiraste.

Igual de no-retrofitteable: **record/replay**. `llm-client` nace con una interfaz de proveedor que incluye un backend de replay (cassettes grabados). Es lo que hace posible evals deterministas en CI de 52 repos, compatible check sin golpear APIs vivas y pipelines sin API keys. `test-kit` lo implementa en la sem. 5; el compat check lo consume en la 13.

*Trade-off:* ~ms de overhead por llamada, irrelevante frente a 11 meses de telemetría propia.

**D5 — `schema-validate`: el LLM como input no confiable (sem. 3).** Toda salida se valida contra un esquema (Pydantic) con una pasada de reparación automática (re-prompt con el error de validación) antes de entrar al dominio. En apps tradicionales el input del usuario es el enemigo; en apps LLM, *la respuesta del modelo* lo es. JSON mode no garantiza cumplimiento de esquema, solo formato.

La reparación tiene **presupuesto**: máximo 2 intentos y un cap de costo por mensaje. Sin tope, el re-prompt es una quemadora de dinero en casos patológicos. El efecto secundario es una métrica gratis: la **tasa de reparación por prompt** (qué fracción de primeras respuestas no validó). Ese número es señal de calidad de prompt y alimenta directamente a `prompt-registry`. *Trade-off:* latencia extra en reparación; menor que el costo de un objeto inválido propagado.

**D6 — `prompt-registry`: fuente única de verdad, en fases.** "Mejoré el prompt y funciona mejor" no es ingeniería: es superstición. Un prompt solo es mejorable si tiene un dataset que lo acorrala. Y la semana 48 (marketplace) solo es posible si los prompts ya eran ciudadanos de primera clase. El registry no nace completo — si intentara nacer entero en la semana 2, sería un paquete sin usuarios — así que evoluciona.

### D6.1 — `prompt-registry` evoluciona en tres fases

1. **Fase 1 — Convención (semanas 2–12).** Los prompts viven en `/prompts` dentro de cada consumidor, con frontmatter mínimo obligatorio:

```yaml
id: commit-message-generator
version: 0.4.0
owner: llm-dev-core
model_family: gpt-4o-mini
schema: CommitMessage
eval: evals/commit-message-generator.jsonl
status: experimental
```

2. **Fase 2 — Paquete mínimo (semanas 13–34).** `prompt-registry` se extrae como paquete del core: carga por ID, valida metadatos, impide prompts inline y pinning de versiones. La métrica "100% en `prompt-registry`" se cuenta como *metadatos desde sem. 2* y como *manejado por el paquete desde sem. 13* — no es una contradicción, es la fase en la que vive el sistema.

3. **Fase 3 — Registry formal (semana 35+).** Incorpora datasets de eval, regresión, métricas de calidad, historial de cambios y preparación para marketplace.

**Regla desde la semana 5:** todo prompt *nuevo* tiene ≥1 eval asociado (exigido por CI). Los prompts de los consumidores 2–4 (anteriores a `test-kit`) se retrofitean en la semana 6 como **retrofit documentado #0** — deuda reconocida, no heredada.

Dos problemas que la Fase 3 hereda y que se anticipan desde el diseño de `test-kit`: (a) cuando un prompt lo comparten 3 consumidores, su dataset tiene un dueño declarado — o la fase 35 reescribe el formato; (b) dataset congelado + modelo que deriva = re-baselining como operación documentada (runbook), porque si no, cada actualización del proveedor parece una regresión propia.

*Trade-off:* fricción al añadir un prompt (hay que escribir sus evals) — es la fricción correcta, está donde debe estar.

**D7 — `test-kit`: en desarrollo LLM, los tests son datasets (sem. 5).** La semana 5 no genera "tests unitarios": construye el formato de dataset (input → salida esperada → criterio de evaluación) que todos usarán. El comportamiento LLM tiene distribuciones, no assertions; sin evals versionados, ningún cambio de prompt o modelo es seguro, y este año es un refactor continuo. Los evals son el suelo.

Dos capas por encima del formato:

- **¿Quién evalúa al evaluador?** Un LLM-as-judge con bias sistemático (respuestas largas = mejor score) convergería los prompts hacia verbosidad. Hay una capa de calibración: un dataset pequeño (~20 casos) etiquetado **a mano** sirve de ground truth contra el que se calibra al evaluador. Sin eso, se mide consistencia, no calidad.
- **Determinismo por record/replay.** Los evals corren sobre cassettes; no golpean APIs vivas en CI. El evaluador LLM no es la única puerta de merge: convive con aserciones deterministas sobre los runs grabados (D4).

`eval-smoke` (diario, barato) y `eval-full` (releases, cambios de prompt o modelo) se definen en §8.1. *Trade-off:* ruido y costo del evaluador; se mitiga con umbrales sobre datasets congelados y presupuestos.

**D8 — Compat check: el core se prueba contra sus consumidores (desde v1.0).** El CI corre la suite completa contra consumidores en cada merge a `main`. El riesgo real no es romper el core: es romper a quienes lo usan. Es la respuesta honesta al acoplamiento de D1, y convierte "uso GitHub Actions" en "diseño de sistemas".

"Los últimos 5" son los menos representativos: los repos en riesgo de romperse son los de pins más viejos, que nunca entrarían al check. La muestra **se estratifica: 3 consumidores recientes + 2 con pins antiguos**. Los secrets se resuelven con los cassettes de D4 (record/replay), nunca con API keys vivas en el CI. La política y el protocolo de degradación están en §6.1. *Trade-off:* CI más lento; es el precio de tener usuarios.

**D9 — Regla 70/30 de superficie nueva.** Ninguna semana de composición acepta más de un concepto nuevo; el resto es composición del core. El calendario solo es realista si la novedad es acotada: el SaaS de contratos (sem. 40) cabe en una semana no por pequeño, sino porque auth, validación, generación, PDF y costos ya existen; lo nuevo es la composición multi-tenant. Romper esta regla es romper el calendario. Las semanas-seed están fuera de esta vara (ver §2.1).

**D10 — Hitos de consolidación en semanas 13, 26, 39 y 52.** Cada 13 semanas no hay proyecto nuevo: hay extracción, versionado y documentación del core. Sin hitos forzados, el core se pudre en "ya lo extraeré luego". La 13 extrae lo que 12 consumidores ya necesitaron; la 26 lo endurece con la auditoría de seguridad; la 39 lo instrumenta; la 52 decide si merece v4.0 o es el cierre. *Trade-off:* 4 semanas sin demo nueva. El core es el producto; las demos son su marketing.

**D11 — Stack único: Python 3.12+ (además, la ADR-0).** El core tiene un único runtime principal; mantener dos lenguajes en el core significa duplicar todo: cliente, validación, evals, CI, packaging, errores y documentación. *Decisión:* Python 3.12+, Pydantic (validación), FastAPI (APIs), pytest (tests), uv (tooling) y logging estructurado (observabilidad). Pydantic es la implementación natural de "la salida del LLM es input no confiable". Los consumidores pueden tener frontends u otros componentes en otras tecnologías, pero toda lógica LLM, validación, prompts, evals y observabilidad pasan por el core en el stack oficial. ADR expandido en `docs/decisions/0000-stack.md`. *Trade-off aceptado:* quien quiera usar el core desde otro runtime queda fuera; es el precio de no mantener dos ecosistemas. Es la decisión más barata del documento y la única con deadline inmediato: bloquea la semana 2.

**D12 — Regla del tercer uso.** "Que se compongan en el consumidor" es correcto al comienzo e incorrecto cuando el patrón se repite. Si `agent-loop` y `vector-core` se componen en consumidores 22, 25 y 31 con el mismo patrón, eso no es composición: es un módulo faltante. La regla: en el **tercer uso** del mismo patrón, el patrón es candidato a módulo propio. Ni antes (se extrae una hipótesis), ni después (se acepta deuda como diseño).

## 5. Estructura

```
llm-dev-core/
├── packages/
│   ├── llm-client/        # C1  [seed sem. 2]
│   ├── schema-validate/   # C2  [seed sem. 3]
│   ├── secure-base/       # C3  [seed sem. 4]
│   ├── test-kit/          # C4  [seed sem. 5]
│   ├── web-api-base/      # C5  [seed sem. 6]
│   ├── ci-pack/           # C6  [seed sem. 7]
│   ├── cache-ratelimit/   # C7  [seed sem. 8]
│   ├── bot-base/          # C8  [seed sem. 9]
│   ├── parser-io/         # C9  [seed sem. 10]
│   ├── docs-gen/          # C10 [seed sem. 12]
│   ├── vector-core/       # C11 [seed sem. 16]
│   ├── diff-engine/       # C12 [seed sem. 19]
│   ├── agent-loop/        # C13 [seed sem. 21]
│   ├── auth-base/         # C14 [seed sem. 25]
│   ├── gh-app/            # C15 [seed sem. 27]
│   ├── scraper/           # C16 [seed sem. 28]
│   ├── prompt-registry/   # C17 [seed sem. 35]
│   └── cost-obs/          # C18 [seed sem. 39]
├── scripts/
│   ├── check_consumers.py # invariantes ejecutables: manifiestos y prompts (`make validate`)
│   ├── collect_metrics.py # página de evidencia (§10.1)
│   └── compat_check.sh    # workflow compat-last-5
├── templates/
│   ├── consumer-readme.md
│   ├── core-consumer.yml
│   ├── prompt.md
│   ├── eval-dataset.jsonl
│   └── retrofit-issue.md
├── docs/
│   ├── decisions/         # un ADR por decisión (0000-stack, 0001-D1, …)
│   ├── metrics/           # datos crudos de la página de evidencia
│   └── runbooks/          # degradación, re-baseline, expulsión de módulo
├── ARCHITECTURE.md
└── CHANGELOG.md           # desde v1.0 (sem. 13)
```

**Reglas de dependencia:** `llm-client` es la hoja (no depende de nadie) y expone la reparación con presupuesto; `schema-validate` se compone con ella **solo vía el hook `validator`** (nunca importada por el cliente — ver ADR-2). `prompt-registry` y `test-kit` dependen de `llm-client`, nunca al revés. `agent-loop` no depende de `vector-core` — que se compongan en el consumidor hasta que la regla del tercer uso (D12) diga lo contrario. `cost-obs` lee los spans de `llm-client`; ningún módulo depende de `cost-obs`.

La semana 2 no empieza desde cero: clona la plantilla de consumidor (`templates/`), no un repo vacío.

### 5.1 Semana mínima viable

52 semanas es ambicioso, y la presión del calendario produce exactamente lo que este documento prohíbe: el corte silencioso. Si una semana no alcanza para el proyecto completo, se entrega un **consumidor mínimo válido**:

- repo público,
- dependencia versionada de `llm-dev-core`,
- una funcionalidad demostrable,
- un prompt versionado con frontmatter,
- un eval básico,
- README con "Recicla de",
- issue de excedente para la semana siguiente.

Esto preserva la cadena de acumulación y evita el abandono silencioso. **Máximo 3 semanas así en el año** — no es una puerta de escape, es la elasticidad que evita que una semana mala quiebre el sistema. Una 4.ª semana mínima se marca como anomalía, no como excepción.

## 6. Ciclo de vida de un módulo

```
experimental (en un consumidor) → propuesto (PR al core) → seed (0.x)
→ consolidado (≥2 consumidores) → estable (v1.0+, garantías semver)
→ mejorado (minor) → deprecado (major, con migración documentada)
```

**Criterio de admisión:** un módulo es admisible en el core si su razón de existir es *alimentar o consumir el pipeline LLM*. Es lo que mantiene al scraper dentro (scrapear → extraer → validar es pipeline LLM) y a un CSV-helper fuera. Sin esta frontera, la semana 28 inicia el deslizamiento hacia el cementerio de utilidades que este documento teme.

Un módulo seed sin segundo consumidor en 13 semanas se revisa a fondo o se expulsa: el core no es un cementerio de utilidades que solo usé una vez. La expulsión es un runbook, no una tragedia: se depreca con migración documentada, como cualquier breaking change.

### 6.1 Política de compatibilidad

El core existe para ser usado, y usarlo implica proteger a sus consumidores.

- Cada consumidor declara la versión mayor de `llm-dev-core` que usa (en `core-consumer.yml`).
- El CI del core ejecuta un compat check contra **5 consumidores no deprecados: 3 recientes + 2 con pins antiguos**.
- Un merge a `main` no puede romper a esos 5 consumidores.
- Si un consumidor queda obsoleto, se marca como deprecado con issue y fecha.
- Todo breaking change requiere:
  - entrada de changelog,
  - guía de migración,
  - al menos un consumidor migrado como referencia.
- Versiones soportadas: la major actual recibe features, fixes y mejoras; la major anterior, solo parches críticos durante un ciclo limitado.

**Protocolo de degradación** (¿qué pasa si `llm-client` v2.3 rompe a los consumidores 30–35?):

```
merge a main → compat-last-5 → FAIL
  1. revert del merge: el core nunca queda roto en `main`
  2. hotfix branch del defecto; los consumidores pineados siguen en su versión
  3. si el fix es breaking para la major, se envía como minor con guía de migración
```

D8 detecta el problema; este protocolo es la respuesta. Un consumidor congelado en v2.2 sigue funcionando mientras su versión esté en soporte — ese es el valor de los pins, y lo que evita que la cadena dependa del último `main` en cada minuto.

## 7. Definition of Done

Hay dos DoD, una por tipo de semana. Una semana no puede ser las dos cosas: si extraes un módulo, tu superficie nueva es el módulo, no el 30% de un proyecto.

### DoD — semana-seed (nace un módulo del core)

- [ ] El módulo nace dentro de un consumidor real (nunca como repositorio de utilidades).
- [ ] Contrato público escrito: API, schema de span, ejemplo de uso.
- [ ] Primera versión publicada en el registry público.
- [ ] Un consumidor real lo usa (el de la propia semana, por defecto).
- [ ] Changelog entry, y ADR si cambió una decisión.

### DoD — semana de composición (consumidor regular)

- [ ] Declara `llm-dev-core` como dependencia versionada (nunca código copiado).
- [ ] `core-consumer.yml` presente con `reused_modules`, `new_surface` y `estimated_new_surface`.
- [ ] 100% de llamadas LLM por `llm-client` (lint anti-imports en verde); 100% de prompts con frontmatter en `/prompts` (lint en verde).
- [ ] README con: problema, demo, arquitectura, **"Recicla de"**, limitaciones, roadmap.
- [ ] Salida LLM validada por `schema-validate`.
- [ ] ≥ 1 eval del prompt principal en CI (vía `test-kit`); job `eval-smoke` en verde.
- [ ] Si tocó el core: PR con changelog entry.
- [ ] Si el core mejoró después: issue de retrofit documentado (label `retrofit`).

### DoD — común a ambas

- [ ] Sin datos sensibles sin redacción en prompts (§3.1).
- [ ] Lints de invariantes (§3) en verde.
- [ ] Si la semana no llega: aplicar §5.1, nunca cortar en silencio.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Romper el core rompe N repos | Compat check estratificado (D8) + semver + pins + protocolo de degradación (§6.1) |
| Repos delgados percibidos como repetitivos | "Recicla de" visible + demos distintas |
| Reutilizar = copiar-pegar disfrazado | Prohibido copiar: solo importar el paquete (lo hace cumplir el lint anti-imports) |
| Desbordamiento semanal corrompe el calendario | Regla 5: excedente al core, nunca corte silencioso |
| Semana que no existe (vida, enfermedad, entrevista real) | Semana = secuencia, no fecha; §5.1 con máximo 3 usos al año |
| Prompts que "funcionan" sin evals | CI falla si un prompt de producción no tiene dataset (desde sem. 5) |
| Evals caros, lentos o flaky | §8.1: presupuestos, smoke vs full, datasets congelados, record/replay |
| Bias del evaluador LLM (consistencia ≠ calidad) | Calibración sobre ground truth etiquetado a mano (D7) |
| El mantenedor es un único punto de fallo | ADRs, runbooks, changelog y página de evidencia: el conocimiento vive en el repo, no en mi cabeza |
| Drift del proveedor (modelos deprecados, pricing) | Los proveedores se abstraen detrás de `llm-client`; el span registra modelo y costo reales |
| El año termina siendo 52 demos | Las métricas de §2.1 y la página de evidencia son la vara; si falla, este archivo se reescribe con lo aprendido |

### 8.1 Costo y evals

Los evals son infraestructura, no un lujo. Pero cuestan dinero y tiempo, así que se administran.

Un eval no es un test que dice "el LLM respondió bonito". Un eval es un **dataset con criterio de éxito, costo conocido y umbral de regresión**.

- Cada consumidor declara un presupuesto máximo de evals en `core-consumer.yml`.
- El CI diario corre un `eval-smoke`: dataset pequeño, costo acotado, rápido, umbral claro.
- El `eval-full` corre en: releases del core, cambios de prompt, cambios de modelo, o semanalmente.
- Los cambios de prompt corren evals on-change; el resto de la semana depende del smoke. El evaluador LLM no es la única puerta de merge.
- Ningún cambio de modelo se acepta sin una corrida de regresión.
- Los datasets de eval se versionan igual que el código; los umbrales corren sobre datasets congelados.
- Re-baselining de un dataset es una operación documentada (runbook), no un ajuste silencioso.
- Se permite cacheo de respuestas solo cuando el eval es determinístico o está explícitamente marcado como no sensible a variabilidad.
- El costo de evals corre por record/replay (D4): en CI no se gastan llamadas en lo que ya está grabado.

La regla es simple: si no puedes pagar el eval de forma repetible, el eval está mal dimensionado.

## 9. Qué NO es este proyecto

- **No es un framework universal.** Publicado, pero opiniado y egoísta: sirve a mis 52 proyectos primero.
- **No es "production-ready" por decreto.** La estabilidad se gana por uso (D3), no por etiqueta.
- **No persigue cobertura de features.** Persigue un historial de decisiones defendibles. Diez módulos con argumentación honesta valen más que treinta con marketing.
- **No es un cementerio de utilidades.** Nada entra sin un consumidor que lo avale (§6) y nada queda sin un segundo consumidor que lo justifique.
- **No es una demo de prompts.** Es una demo de *dirección*: el LLM genera código bajo estas restricciones, y el sistema se sostiene porque las restricciones son buenas.

## 10. Estado actual

- **Versión:** v0.9
- **Módulos existentes:** `packages/llm-client` v0.1.0 (seed sem. 2) — `complete`/`stream`, retry+backoff+jitter, reparación con tope, cap de costo, cache, span de 20 campos, record/replay nativo, transportes `opencode` (sesión local sin API key) y `openai-compatible` (HTTP). `packages/schema-validate` v0.1.0 (seed sem. 3) — validación Pydantic de la salida LLM (ADR-2): JSON con/sin caretas, errores campo a campo, registro `SchemaId → modelo`, `parsed` en `ValidationResult`; compone con `llm-client` vía el hook `validator` (que respeta el contrato `schema=None → ok` desde v0.5). `packages/secure-base` v0.1.0 (seed sem. 4) — utilidad de máscara (ADR-3): `detect`/`redact`/`sanitize_for_prompt`/`assert_redacted` + `SecurityProfile`; máscara unidireccional y determinista (placeholder `[REDACTED:<tipo>:<n>]`), 9 detectores (exactitud auditada en la sem. 7), hoja de la seguridad (no depende de `llm-client` ni `schema-validate`); compone en los renderers, antes de que el texto cruce al proveedor. `packages/test-kit` v0.1.0 (seed sem. 5) — los tests de prompts son datasets (ADR-4): `EvalDataset.from_jsonl` (casos `{prompt_id, prompt_version, input, expected, criteria}`), tres criterios deterministas (`deterministic_match`, `json_match`, `schema_match`), runner agnóstico del transporte (`judge: EvalCase → CompletionResult` inyectado), modo `smoke`/`full`, umbral y costo acumulado (§8.1). `packages/web-api-base` v0.1.0 (seed sem. 6) — FastAPI LLM-ready (ADR-5): `create_app(title, version, *, client)` expone `GET /health` y `POST /llm` (pipeline completo de `llm-client` con la validez como gate: 422 `salida_no_validada`), errores uniformes (429 `presupuesto_excedido`, 422, 502 `proveedor_indisponible`, 500 `error_interno`), `llm_complete`/`sse_response` para reuso; composición, no acoplamiento — recibe el `client` ya cableado y **no** importa `test-kit`. `packages/ci-pack` v0.1.0 (seed sem. 7) — compliance y evidencia automaticables (ADR-6): `lints` (`run_lints`/`lint_imports`/`lint_inline_prompts`/`lint_secrets`) sobre el código de cada consumidor — lo que cruza al proveedor (cassettes, prompts, evals, src) se audita, lo que no viaja (tests, scripts) se salta; `metrics` (`collect` desde `core-consumer.yml` + spans de `llm-client`, `render` como HTML) alimentando la página de evidencia (§10.1); `jobs` (`render_eval_smoke_job`) generando los `eval-smoke.yml` de la flota con el layout local reproducible en CI. `packages/cache-ratelimit` v0.1.0 (seed sem. 8) — caché y ritmo como *política de composición* (ADR-7): `RateLimiter` (token bucket `rpm`/`burst`, reloj inyectable para CI determinista), `ThrottledProvider` y `CachedProvider` (TTL + poda) implementan `Provider` y se enchufan donde hoy se enchufa cualquier provider — la hoja de `llm-client` no cambia. `packages/bot-base` v0.1.0 (seed sem. 9) — recurrencia programada determinista (ADR-8): `Schedule` (intervalo monótono o predicado de calendario, reloj inyectable), `RunStore`/`JsonRunStore` (idempotencia por última corrida, escritura atómica), `Task` + `run_tasks` con `Digest` (ok/skipped/failed, fallos visibles); no depende del core (pydantic + stdlib) y el LLM se compone en el consumidor.
- **Consumidores:** `Proyectos/commit-cli` (sem. 2) — CLI que propone mensajes de commit desde `git diff`; `Proyectos/release-scribe` (sem. 3) — release notes JSON validadas por `schema-validate` desde `git log`; `Proyectos/sec-check` (sem. 4) — escáner de secretos con triaje LLM: redacta con `secure-base` y aborta si `assert_redacted` no es vacío, reporte `sec-findings-v1` validado por `schema-validate`; `Proyectos/bench-runner` (sem. 5) — CLI de evals con datasets congelados y umbral (exit 0/1/2) cuyo propio prompt `regression-report-generator` (triaje de regresión en `modo json`/`modo texto`) nace evaluado: dogfood del seed, reusa `llm-client` + `schema-validate` + `test-kit`, cassettes reales para CI determinista (D4); `Proyectos/eval-api` (sem. 6) — "bench-runner como servicio": FastAPI sobre `web-api-base` con `POST /evals/run` (test-kit por HTTP, 422 `dataset_invalido`) y `POST /summarize` (prompt `eval-summarizer`, schema `eval-summary-v1`), cuyo resumidor nace evaluado: dogfood del conjunto `test-kit` + `web-api-base`; `Proyectos/ci-scribe` (sem. 7) — fleet ops + evidencia: CLI `eval`/`audit`/`evidence` y Web API sobre la base (`POST /fleet/audit` con los lints de `ci-pack`, `POST /fleet/triage` con el prompt `eval-triage-generator`), nace evaluado y su página de evidencia la regenera él mismo con `ci-pack.metrics`; `Proyectos/llm-gateway` (sem. 8) — proxy HTTP con caché y límite de ritmo sobre `web-api-base`: `POST /llm` con la cadena `ThrottledProvider(CachedProvider)` de `cache-ratelimit`, `GET /gateway/stats` (bucket + hits/miss) y cabecera `X-Cache`, nace evaluado y con CI determinista.  `Proyectos/fleet-bot` (sem. 9) — ciclo matutino de la flota: audit (`ci-pack.lints`) + evidencia + digest LLM del día (`daily-digest-generator`), con el lock de recurrencia de `bot-base` en `.bot/state.json` (idempotencia por día), nace evaluado y con CI determinista.  **Retrofit #0 (sem. 6):** los prompts de los consumidores 2–4 pasaron de seed de 1 caso a datasets congelados reales (3 casos) + cassettes; **sem. 7:** la auditoría de flota con `ci-pack.lints` endureció el detector `bearer` de `secure-base` y aseguró las fixtures de `sec-check` (cassette re-grabado sin credenciales residuales); deuda CI de `bench-runner` cerrada (su `eval-smoke.yml` nace de `ci_pack.jobs`). Los siete dependen de la dist unificada `llm-dev-core` (editable). La métrica de reutilización real se mide en §10.1 desde el corte semanal.
- **Empaquetado:** una sola dist `llm-dev-core` (D1) publicada en PyPI: `llm_client`, `schema_validate`, `secure_base`, `test_kit`, `web_api_base`, `ci_pack`, `cache_ratelimit` y `bot_base` top-level. La publicación es automática desde tag `v*` vía trusted publishing OIDC (workflow `publish.yml`, sin tokens guardados). FastAPI, starlette y PyYAML son dependencias obligatorias del wheel (ADR-5, ADR-6).
- **Enforcement:** ADR-0 … ADR-8 (`bot-base-contract`) en `docs/decisions/`, plantillas en `templates/`, `make validate` (estructura + tests + regeneración de la evidencia) y `make validate-consumer CONSUMER=../<repo>`.
- **Pasos por semana según el plan:** se mantiene el calendario semanal (estructura C1–C18 de §5, armonizada en la sem. 3): `schema-validate` (sem. 3), `secure-base` (sem. 4), `test-kit` (sem. 5), `web-api-base` (sem. 6), `ci-pack` (sem. 7), `cache-ratelimit` (sem. 8), `bot-base` (sem. 9), `parser-io` (sem. 10), `docs-gen` (sem. 12), ... hasta `cost-obs` (sem. 39).
- **Próximo hito:** v1.0 en la semana 13, con 12 consumidores reales detrás.

### 10.1 La página de evidencia

El entregable del año no son 52 repos: es un **URL**. Un dashboard auto-generado por `ci-pack` (`scripts/collect_metrics.py`) en cada merge, que convierte las promesas de §2 en datos:

- % de reutilización por semana (desde los `core-consumer.yml`),
- costo por proyecto y acumulado (desde los spans de `llm-client`),
- cobertura de evals (prompts con dataset / prompts totales),
- matriz repo × versión-de-core,
- retrofittings cerrados vs. reportados.

Ya operativa: `docs/metrics/evidence.html` se regenera en el core (`make validate`) y en
`ci-scribe` (`ci-scribe evidence`), ambas desde `ci_pack.metrics` sobre `core-consumer.yml` +
spans. Las afirmaciones de un README son promesas; los gráficos de ese URL son evidencia. Un entrevistador que quiera ver cómo se mantiene esto no necesita creerme en palabra: necesita un enlace.

---

*"La abstracción que solo se usa una vez es una hipótesis; la que se usa treinta, un diseño."*

---

Notas finales sobre el documento: las decisiones (D1–D12, con D11 como ADR-0) están redactadas en formato de ADR comprimido — cada una se expande en `docs/decisions/` con fecha y estado (aceptada/superseded), el formato que los entrevistadores staff reconocen al instante. Los puntos flacos que señaló la revisión (verificación, políticas, protocolos de fallo, stack, seguridad) están resueltos como capas de enforcement dentro del documento: §2.1, §3, §3.1, §5.1, §6.1, §8.1 y la página de evidencia (§10.1). Y la frase del cierre, además de epígrafe, es la descripción del repo en GitHub.