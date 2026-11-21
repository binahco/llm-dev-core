"""Tests de vector-core: determinismo, coseno acotado, léxico declarado (D4)."""

from __future__ import annotations

import pytest

from vector_core import LexicalEmbedder, VectorStore, cosine


def test_mismo_texto_mismo_vector_y_coseno_uno() -> None:
    emb = LexicalEmbedder(dims=256)
    assert emb.embed("clasificar issues de la flota") == emb.embed("clasificar issues de la flota")
    store = VectorStore(emb)
    store.add("a", "digest diario de la flota con fecha y resumen")
    assert store.pair("a", "a") == pytest.approx(1.0)


def test_vocabulario_disjunto_coseno_casi_cero() -> None:
    emb = LexicalEmbedder(dims=1024)
    a = emb.embed("rotar credenciales expuestas purgar registro servidor")
    b = emb.embed("redactar notas version paquete publicado boletin")
    assert cosine(a, b) < 0.05


def test_determinismo_entre_procesos_no_hash_saltado() -> None:
    """sha256 con semilla fija, no `hash()` nativo (salta por proceso)."""
    emb = LexicalEmbedder(dims=64)
    v1 = emb.embed("determinista entre corridas")
    v2 = LexicalEmbedder(dims=64).embed("determinista entre corridas")
    assert v1 == v2


def test_busqueda_encuentra_al_gemelo_primero() -> None:
    emb = LexicalEmbedder()
    store = VectorStore(emb)
    store.add("digest-flota", "Eres el cronista. Recibes un dia y redactas un digest en JSON con summary y watch.")
    store.add("commit-msg", "Eres el revisor. Recibes un diff y propones un mensaje de commit conventional.")
    store.add("digest-sitio", "Eres el cronista. Recibes un dia y redactas un digest del sitio en JSON con summary.")
    resultados = store.search("Eres el cronista. Recibes un dia y redactas un digest en JSON con summary y watch.", top_k=2, exclude="digest-flota")
    assert resultados[0].id == "digest-sitio"
    assert 0.5 < resultados[0].score <= 1.0


def test_pairs_ordenados_y_filtrados() -> None:
    emb = LexicalEmbedder()
    store = VectorStore(emb)
    store.add("a", "uno dos tres cuatro")
    store.add("b", "uno dos tres cuatro cinco")
    store.add("c", "nada que ver aqui verdad")
    pares = store.pairs(min_score=0.5)
    assert pares and pares[0].id == "a ⟷ b" and pares[0].score > 0.5
    ids_en_pares = {p.id for p in pares}
    assert all("c" not in i for i in ids_en_pares)


def test_texto_vacio_da_vector_cero_sin_explotar() -> None:
    emb = LexicalEmbedder(dims=32)
    assert emb.embed("") == [0.0] * 32
    store = VectorStore(emb)
    store.add("vacio", "")
    assert store.pair("vacio", "vacio") == 0.0


def test_id_duplicado_y_par_desconocido_son_errores_visibles() -> None:
    store = VectorStore(LexicalEmbedder())
    store.add("a", "texto")
    with pytest.raises(ValueError, match="duplicado"):
        store.add("a", "otro")
    with pytest.raises(KeyError):
        store.pair("a", "no-existe")


def test_dimensiones_chicas_se_rechazan() -> None:
    with pytest.raises(ValueError, match="dims"):
        LexicalEmbedder(dims=8)
