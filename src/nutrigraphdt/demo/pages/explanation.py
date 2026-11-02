"""Explicaciones: el subgrafo top-k con la evidencia declarada de cada arista (C-03, #243)."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from nutrigraphdt.demo import plots, ui
from nutrigraphdt.demo.data import REPO_ROOT
from nutrigraphdt.explainability.contract import ExplanationContractError
from nutrigraphdt.explainability.style import evidence_style
from nutrigraphdt.explainability.subgraph import extract_subgraph_view, load_explanation

EXAMPLE = REPO_ROOT / "docs" / "models" / "examples" / "explanation-synthetic.json"


def render() -> None:
    ui.hero(
        "Explicaciones",
        "Subgrafo explicativo top-k.",
        "Las aristas que más pesan en una salida del modelo, con la evidencia que el grafo "
        "declara para cada una. La importancia es del modelo; la evidencia, del grafo.",
    )
    uploaded = st.file_uploader(
        "Explicación del contrato 2.0.0 (JSON). Sin archivo se muestra el ejemplo sintético.",
        type="json",
    )
    raw: Any = json.loads(
        uploaded.getvalue().decode("utf-8-sig")
        if uploaded is not None
        else EXAMPLE.read_text(encoding="utf-8")
    )
    try:
        view = extract_subgraph_view(load_explanation(raw))
    except (ExplanationContractError, ValueError) as error:
        st.error(f"La explicación no cumple el contrato: {error}")
        return

    target = view.target
    st.markdown(
        f"**Salida:** `{target.output}` · **instancia:** `{target.graph_id}` · "
        f"**modelo:** `{view.run.variant}` · **explicador:** `{view.explainer.name}` · "
        f"**k:** {view.k}"
    )
    st.plotly_chart(plots.subgraph_figure(view), config=ui.CHART_CONFIG, key="subgraph")
    st.caption(
        "Grosor: |importancia| de la arista. Trazo y color: estado de evidencia declarado por el "
        "grafo, que no cambia con la importancia. Las aristas hipotéticas se muestran siempre; "
        "no se ocultan ni salen del top-k."
    )
    for warning in view.warnings:
        st.warning(f"**{warning.code}.** {warning.message}")
    st.dataframe(
        [
            {
                "arista": f"{e.source_id} → {e.relation_type} → {e.target_id}",
                "importancia": round(e.importance, 3),
                "evidencia": evidence_style(e.evidence.evidence_status).label,
                "método": e.evidence.evidence_method,
                "fuente": e.evidence.evidence_source or "",
            }
            for e in view.edges
        ],
        hide_index=True,
    )
