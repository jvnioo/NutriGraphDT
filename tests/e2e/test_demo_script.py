"""Recorrido del guion preliminar de la demostración (A123, #356), paso a paso con `AppTest`.

Cada bloque corresponde a un paso de `docs/process/demo-script-preliminary.md` y comprueba lo
que la persona que presenta debería ver. Sin red ni navegador. Requiere los extras `graph`,
`baselines` y `demo`.
"""

from __future__ import annotations

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt.demo import layout  # noqa: E402

pytestmark = pytest.mark.e2e
TIMEOUT = 300


def _app() -> None:
    import streamlit as st

    from nutrigraphdt.demo import app, layout

    specs = {spec.url_path: spec for spec in app.PAGES}
    layout.sidebar()
    app.framed(specs[st.session_state.get("_demo_page", "inicio")].render)()


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [w.value for w in (*at.info, *at.success, *at.warning, *at.error)]
    return "\n".join(parts)


def _go(at: AppTest, page: str) -> str:
    at.session_state["_demo_page"] = page
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    text = _text(at)
    assert layout.SYNTHETIC_LABEL in text
    return text


def _simulate(at: AppTest, scenario_id: str) -> None:
    at.radio(key="ng_mode").set_value("Catálogo de referencia").run()
    at.selectbox(key="ng_catalog").set_value(scenario_id)
    labels = [b.label for b in at.button]
    at.button[labels.index("Simular escenario")].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]


def test_preliminary_demo_script_runs_step_by_step() -> None:
    at = AppTest.from_function(_app, default_timeout=TIMEOUT)
    at.run()
    at.button(key="reset_state").click().run()

    # 1. Inicio: rótulo y corrida activa.
    _go(at, "inicio")
    assert "Corrida activa" in [s.value for s in at.subheader]

    # 2. Sintético frente a D1.
    assert "sintético frente a d1" in _go(at, "comparacion").lower()

    # 3. Escenario: proteína 270 g/kg desde el catálogo.
    _go(at, "escenario")
    _simulate(at, "crude-protein-270")
    assert at.success and "Estimable" in at.success[0].value
    assert "no se observó en el train" in _text(at)

    # 4. Resultados: intervalo sin calibrar, panel con violaciones y advertencias.
    text = _go(at, "resultados")
    assert "sin calibrar" in text and "Asociación no es causalidad" in text
    assert len(at.dataframe) == 3

    # 5. Grafo: filtro por relación y leyenda.
    _go(at, "grafo")
    at.multiselect(key="ng_graph_relations").set_value(["modulates", "has_capacity"]).run()
    assert not at.exception
    assert "hipotética" in str([d.value for d in at.dataframe])

    # 6. Explicación de ln T.
    text = _go(at, "explicacion")
    assert "GNNExplainer" in text and "no disponible" in text

    # 7. No estimable: dosis 0.
    _go(at, "escenario")
    _simulate(at, "additive-dose-control")
    assert not at.success
    assert at.warning and "No estimable" in at.warning[0].value
