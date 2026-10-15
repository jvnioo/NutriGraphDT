"""Proceso: cómo se trabajó (Scrumban, revisiones, checks locales y costo cero)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import streamlit as st

from nutrigraphdt.demo import data, plots, ui

_PREFIX = re.compile(r"^([A-Z]{1,3}\d{0,2})[-—\s]")


def render() -> None:
    ui.hero(
        "Proceso",
        "Cómo se construyó.",
        "El equipo trabaja con Scrumban: cada tarea es una Issue con criterios de aceptación; "
        "se toma desde Ready, se desarrolla en una rama, se valida localmente y entra a main "
        "solo con un Pull Request revisado por otra persona.",
    )
    snapshot = data.progress_snapshot()
    if snapshot is None:
        st.info(
            "Ejecute `python scripts/export_board_snapshot.py` para generar la foto del tablero."
        )
        return
    issues: list[dict[str, Any]] = snapshot["issues"]
    closed = sum(issue["state"] == "closed" for issue in issues)
    ui.metric_cards(
        [
            ("Tareas cerradas", f"{closed} / {len(issues)}", "Issues del tablero"),
            ("PR fusionados", f"{snapshot['merged_pull_requests']}", "integrados a main"),
            ("Tests", f"{snapshot['tests_collected']}", "ruff · mypy estricto · pytest"),
            ("Costo", "$0", "sin servicios ni cómputo de pago"),
        ]
    )
    st.caption(f"Foto del tablero: {snapshot['generated_at']} (UTC).")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        groups[_group(issue)].append(issue)
    rows = [
        {
            "grupo": name,
            "cerradas": sum(i["state"] == "closed" for i in items),
            "abiertas": sum(i["state"] == "open" for i in items),
        }
        for name, items in sorted(groups.items(), key=lambda item: _order(item[0]))
    ]
    st.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.bars_figure(
            rows,
            category="grupo",
            values=["cerradas", "abiertas"],
            title="Tareas por actividad del cronograma",
        ),
    )
    for name, items in sorted(groups.items(), key=lambda item: _order(item[0])):
        done = sum(i["state"] == "closed" for i in items)
        with st.expander(f"{name} · {done}/{len(items)} cerradas"):
            for issue in items:
                mark = "✅" if issue["state"] == "closed" else "⏳"
                st.markdown(f"{mark} #{issue['number']} {issue['title']}")

    st.subheader("Reglas del trabajo")
    st.markdown(
        """
- **Definition of Done:** criterios de aceptación cumplidos, tests y checks locales en verde
  citados en el PR, revisión aprobada de otra persona, documentación al día.
- **Sin CI de pago:** `ruff check`, `ruff format`, `mypy src` (modo estricto) y `pytest` se
  ejecutan localmente antes de cada PR.
- **Trazabilidad científica:** no se inventan valores; las decisiones abiertas quedan en la
  Issue o el PR, y los datos crudos no se versionan (se regeneran con sus scripts).
- **Costo cero:** solo herramientas libres; la GPU es opcional y CPU es la referencia.
"""
    )


def _group(issue: dict[str, Any]) -> str:
    if issue.get("activity"):
        return str(issue["activity"])
    match = _PREFIX.match(issue["title"])
    return match.group(1).rstrip("-") if match else "Otras"


def _order(name: str) -> tuple[int, str]:
    # Primero las tareas iniciales del dataset y la validación (DS, VG), luego A34, A35…
    return (0 if not name.startswith("A") else 1, name)
