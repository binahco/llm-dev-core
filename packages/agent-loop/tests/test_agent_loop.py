"""Tests de agent-loop: cerebro inyectado, confirmación, presupuesto, errores visibles."""

from __future__ import annotations

import pytest

from agent_loop import Action, ToolRegistry, run_agent


def registro() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("leer", "lee un archivo", lambda args: f"contenido de {args['path']}")
    reg.register("explotar", "siempre falla", lambda args: (_ for _ in ()).throw(RuntimeError("boom")))
    return reg


def brain_guion(acciones: list[Action]):
    """Cerebro determinista: devuelve las acciones del guion en orden y termina."""
    i = {"n": 0}

    def brain(vista: dict) -> Action:
        n = i["n"]
        i["n"] += 1
        return acciones[n] if n < len(acciones) else Action(final="fin del guion")

    return brain


def test_corre_herramientas_y_termina_con_final() -> None:
    acciones = [
        Action(razon="mirar el readme", tool="leer", args={"path": "README.md"}),
        Action(razon="ya alcanza", final="encontré lo buscado"),
    ]
    trace = run_agent("verificar el repo", registry=registro(), brain=brain_guion(acciones))
    assert trace.paro == "done"
    assert [s.estado for s in trace.steps] == ["ok", "final"]
    assert "README.md" in trace.steps[0].salida
    assert trace.final == "encontré lo buscado"


def test_una_herramienta_que_falla_no_mata_el_loop() -> None:
    acciones = [
        Action(tool="explotar"),
        Action(tool="leer", args={"path": "x"}),
        Action(final="recuperado tras el error"),
    ]
    trace = run_agent("tolerante", registry=registro(), brain=brain_guion(acciones))
    assert trace.paro == "done"
    assert [s.estado for s in trace.steps] == ["error", "ok", "final"]
    assert "RuntimeError" in trace.steps[0].detalle


def test_confirmacion_negada_termina_con_rechazado() -> None:
    acciones = [Action(tool="leer", args={"path": "secreto"})]
    trace = run_agent(
        "con puerta humana",
        registry=registro(),
        brain=brain_guion(acciones),
        confirm=lambda action: False,
    )
    assert trace.paro == "rechazado"
    assert trace.steps[0].estado == "rechazado"
    assert trace.final is None


def test_presupuesto_de_pasos_sin_final() -> None:
    acciones = [Action(tool="leer", args={"path": "x"})] * 20
    trace = run_agent("infinito", registry=registro(), brain=brain_guion(acciones), max_steps=3)
    assert trace.paro == "presupuesto"
    assert len(trace.steps) == 3


def test_el_cerebro_ve_las_herramientas_y_el_transcript() -> None:
    vistas: list[dict] = []

    def brain(vista: dict) -> Action:
        vistas.append(vista)
        if vista["step"] == 1:
            return Action(tool="leer", args={"path": "a"})
        return Action(final="basta")

    run_agent("introspectivo", registry=registro(), brain=brain)
    nombres = [t["name"] for t in vistas[0]["tools"]]
    assert nombres == ["explotar", "leer"]  # spec ordenada y sin la función
    assert vistas[1]["transcript"][0]["estado"] == "ok"


def test_herramienta_duplicada_y_desconocida_son_errores_visibles() -> None:
    reg = registro()
    with pytest.raises(ValueError, match="duplicada"):
        reg.register("leer", "otra vez", lambda args: "x")
    with pytest.raises(KeyError, match="desconocida"):
        reg.run("no-existe", {})


def test_determinismo_mismo_cerebro_mismo_trace() -> None:
    acciones = [Action(tool="leer", args={"path": "x"}), Action(final="fin")]
    t1 = run_agent("d", registry=registro(), brain=brain_guion(acciones))
    t2 = run_agent("d", registry=registro(), brain=brain_guion(acciones))
    assert t1 == t2
