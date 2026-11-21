# Contrato mínimo — `vector-core`

- **Fecha:** 2026-11-21
- **Estado:** aceptada
- **Origen:** el calendario C1–C18 (§5): `vector-core` (C11) estaba sembrada para la
  sem. 16 y se pagó tarde — esa semana consumió la verificación objetiva (F0–F4). La
  deuda vivió en el issue #2 hasta hoy.
- **Implementada en:** semana 23 (`packages/vector-core` v0.1.0, dentro de
  `llm-dev-core` v1.4.0; primer consumidor: `prompt-twins`)

La flota ya compara textos: `cassette-diff` mide deriva **entre versiones de un mismo
prompt** y `adr-index` rankea por palabras clave. Lo que falta es la comparación
**entre muchos textos a la vez** — ¿cuáles prompts de la flota son gemelos? — y eso
pide infraestructura de vectores, no otro loop de `count()`.

## 1. API conceptual

```python
from vector_core import LexicalEmbedder, VectorStore

emb = LexicalEmbedder(dims=256)          # el default, léxico y declarado
store = VectorStore(emb)
store.add("fleet-bot/daily-digest", texto)
store.search(texto, top_k=3, exclude="fleet-bot/daily-digest")  # top-k por coseno
store.pairs(min_score=0.5, top=10)       # todos los pares, orden descendente
```

## 2. Reglas

- **La regla de honestidad: el default es léxico, no semántico.** `LexicalEmbedder`
  vectoriza **vocabulario** (bolsa de palabras hasheada, L2). `opencode/big-pickle`
  no expone embeddings (verificado en la sem. 23: el CLI es solo chat), así que aquí
  no se finge significado: paráfrasis con palabras distintas puntúan bajo **y el que
  usa el módulo debe saberlo**. Cuando exista un embedder real, entra por el
  protocolo `EmbeddingProvider` y ni el store ni los consumidores cambian.
- **La hoja no cambia:** stdlib + `pydantic`, como `bot-base` y `agent-loop`. Sin
  `numpy` ni dependencias nativas: la flota es chica y el coseno bruto alcanza.
- **Determinismo (D4):** el hash es `sha256` con prefijo fijo — **nunca el `hash()`
  nativo de Python**, que va salado por proceso y rompería la reproducibilidad entre
  corridas. Mismo texto, mismo vector, siempre.
- **Coseno acotado a [0, 1]:** los embeddings del módulo no son negativos; el store
  lo declara y lo garantiza.
- **Ids explícitos y únicos:** `add` con id duplicado es error visible; comparar por
  id desconocido también.

## 3. Qué NO contrata este documento

- **Embeddings semánticos reales** y su proveedor: son un problema de transporte
  (`llm-client`), no de esta capa — cuando existan, se inyectan.
- **Persistencia e índices ANN:** el store es en memoria y el coseno es bruto. Con
  miles de ítems seguirá alcanzando; cuando no, se discute (D12).
- **Multilingüe/stemming/stopwords por idioma:** el tokenizador es mínimo (minúsculas,
  términos ≥ 3); la sofisticación llega con un consumidor que la pida.
- **Chunking de documentos largos:** entra texto, sale vector; partir es del consumidor.

## 4. Criterio de aceptación del contrato (semana 23)

- [x] `LexicalEmbedder` determinista (sha256 con semilla fija, L2, dims configurable).
- [x] `VectorStore`: `add`/`search`/`pair`/`pairs` por coseno, scores en [0, 1].
- [x] Vector vacío sin explotar; ids duplicados y pares desconocidos como errores.
- [x] Primer consumidor real: `prompt-twins` (sem. 23) — encuentra prompts gemelos
      en la flota con la medición real y narra el veredicto con LLM validado.
