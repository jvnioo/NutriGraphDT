"""Dashboard de resultados (A101, #329): AGCC basal frente a intervenido, métricas y exportación.

Sin Streamlit, para poder probarlo. Todo sale de dos fuentes:

- el `SimulationResult` de A96 (`nutrigraphdt.demo.service`): las cifras del gráfico y de la
  exportación son las de ese JSON;
- los archivos registrados de la corrida (`metrics.csv`, `predictions.csv`, `run.json`): las
  métricas del panel y la tasa de violación de restricciones (A73) se leen de ellos, no se
  escriben a mano.

Un intervalo que no se calculó no se dibuja: `chart_rows` deja `lower`/`upper` vacíos y la página
dice que no está disponible.
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any, Final

import plotly.graph_objects as go

from nutrigraphdt.demo.ui import CYAN, NAVY

COMPONENTS: Final[tuple[str, str, str]] = ("acetate", "propionate", "butyrate")
LABELS: Final[dict[str, str]] = {
    "acetate": "Acetato",
    "propionate": "Propionato",
    "butyrate": "n-Butirato",
    "log_total": "ln T",
}
SCENARIOS: Final[tuple[str, str]] = ("basal", "intervenido")
CSV_HEADER: Final[list[str]] = [
    "escenario",
    "cantidad",
    "unidad",
    "estado",
    "valor",
    "inferior",
    "superior",
    "metodo_intervalo",
    "nivel_intervalo",
    "contrato",
    "corrida",
    "run_id",
    "commit",
    "rotulo",
]
METRIC_LABELS: Final[dict[str, str]] = {
    "fraction_mae_pp": "MAE de las fracciones (puntos porcentuales)",
    "fraction_r2": "R² de las fracciones",
    "log_total_mae": "MAE de ln T",
    "log_total_r2": "R² de ln T",
    "reconstructed_mae": "MAE de las concentraciones reconstruidas (mmol/kg)",
    "reconstructed_r2": "R² de las concentraciones reconstruidas",
}
PANEL_WARNINGS: Final[tuple[str, ...]] = (
    "Datos sintéticos: las métricas son de la cohorte sintética y no estiman el desempeño en "
    "animales reales. Las métricas de D1 son exploratorias y no describen esta corrida.",
    "Asociación no es causalidad: el modelo aprende asociaciones; una diferencia entre escenarios "
    "describe al modelo, no un efecto de la intervención.",
    "«No estimable» quiere decir que la predicción cae fuera del soporte empírico del train de la "
    "corrida (D-06 §7): no se informa ningún número.",
    "Corrida de demostración: pocos animales y pocas épocas; sus cifras sirven para probar la "
    "plataforma, no tienen valor científico.",
)
NO_INTERVAL: Final[str] = (
    "Intervalo no disponible para esta predicción: no se dibuja ninguna banda."
)


def _response(result: Any, scenario: str) -> Any:
    comparison = result.comparison
    return comparison.basal if scenario == "basal" else comparison.intervened


def chart_rows(result: Any) -> list[dict[str, Any]]:
    """Una fila por escenario y cantidad: valor e intervalo, o vacío si no es estimable."""
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        response = _response(result, scenario)
        interval = response.interval
        for quantity in (*COMPONENTS, "log_total"):
            value: float | None = None
            lower: float | None = None
            upper: float | None = None
            if response.status == "estimable":
                if quantity == "log_total":
                    value = response.log_total
                    bounds = interval.log_total if interval is not None else None
                else:
                    value = float(getattr(response.fractions, quantity))
                    bounds = interval.fractions.get(quantity) if interval is not None else None
                if bounds is not None:
                    lower, upper = bounds.lower, bounds.upper
            rows.append(
                {
                    "scenario": scenario,
                    "quantity": quantity,
                    "unit": "ln(mmol/kg)" if quantity == "log_total" else "fracción molar",
                    "status": response.status,
                    "value": value,
                    "lower": lower,
                    "upper": upper,
                    "interval_method": interval.method if interval is not None else None,
                    "interval_level": interval.level if interval is not None else None,
                }
            )
    return rows


def has_intervals(result: Any) -> bool:
    return any(row["lower"] is not None for row in chart_rows(result))


def results_figure(result: Any, quantities: tuple[str, ...] = COMPONENTS) -> go.Figure:
    """Barras basal frente a intervenido por cantidad, con barras de error si hay intervalo."""
    rows = [r for r in chart_rows(result) if r["quantity"] in quantities]
    figure = go.Figure()
    for scenario, color in zip(SCENARIOS, (NAVY, CYAN), strict=True):
        selected = [r for r in rows if r["scenario"] == scenario and r["value"] is not None]
        if not selected:
            continue
        with_interval = all(r["lower"] is not None for r in selected)
        figure.add_trace(
            go.Bar(
                name=scenario,
                x=[LABELS[r["quantity"]] for r in selected],
                y=[r["value"] for r in selected],
                marker_color=color,
                error_y=(
                    {
                        "type": "data",
                        "symmetric": False,
                        "array": [r["upper"] - r["value"] for r in selected],
                        "arrayminus": [r["value"] - r["lower"] for r in selected],
                    }
                    if with_interval
                    else None
                ),
                meta={"scenario": scenario, "interval": with_interval},
            )
        )
    figure.update_layout(
        barmode="group",
        height=360,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="ln(mmol/kg)" if quantities == ("log_total",) else "fracción molar",
    )
    return figure


def to_csv(result: Any) -> str:
    """CSV con una fila por AGCC (y `ln T`) y escenario, con contrato, corrida, commit y rótulo."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in chart_rows(result):
        writer.writerow(
            {
                "escenario": row["scenario"],
                "cantidad": row["quantity"],
                "unidad": row["unit"],
                "estado": row["status"],
                "valor": "" if row["value"] is None else repr(row["value"]),
                "inferior": "" if row["lower"] is None else repr(row["lower"]),
                "superior": "" if row["upper"] is None else repr(row["upper"]),
                "metodo_intervalo": row["interval_method"] or "",
                "nivel_intervalo": "" if row["interval_level"] is None else row["interval_level"],
                "contrato": result.contract_version,
                "corrida": result.run,
                "run_id": result.run_id,
                "commit": result.commit or "",
                "rotulo": result.data_label,
            }
        )
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Panel de métricas de la corrida
# ---------------------------------------------------------------------------


def _float(value: str) -> float | None:
    if value in ("", None):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def metric_rows(run_dir: str | Path) -> list[dict[str, Any]]:
    """Métricas de test de `metrics.csv` (grupo `all`), tal como están registradas."""
    path = Path(run_dir) / "metrics.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["split"] == "test" and r["group"] == "all"]
    return [
        {
            "métrica": METRIC_LABELS.get(r["metric"], r["metric"]),
            "clave": r["metric"],
            **{LABELS[c]: _float(r[c]) for c in (*COMPONENTS, "log_total")},
            "promedio": _float(r["average"]),
            "fuente": "metrics.csv",
        }
        for r in rows
    ]


def violation_rows(run_dir: str | Path) -> list[dict[str, Any]]:
    """Tasa de violación (A73) de las restricciones D-06 sobre `predictions.csv` de la corrida."""
    import torch

    from nutrigraphdt.constraints.d06 import d06_constraints
    from nutrigraphdt.constraints.evaluation import (
        compositional_constraint_inputs,
        evaluate_constraints,
    )

    path = Path(run_dir) / "predictions.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    outputs = torch.tensor(
        [[float(r["z1"]), float(r["z2"]), float(r["log_total"])] for r in rows],
        dtype=torch.float64,
    )
    evaluation = evaluate_constraints(
        compositional_constraint_inputs(outputs),
        [r["sample_id"] for r in rows],
        constraints=d06_constraints(),
    )
    return [
        {
            "restricción": s.metadata.name,
            "animales de test": s.sample_count,
            "violaciones": s.violation_count,
            "tasa de violación (%)": s.violation_rate_percent,
            "fuente": "predictions.csv",
        }
        for s in evaluation.summary.constraints
    ]


def training_summary(run_dir: str | Path) -> dict[str, Any]:
    """λ y restricciones con que se entrenó la corrida, de su `run.json`."""
    info = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
    return {
        "run_id": info["run_id"],
        "variant": info["variant"],
        "constraint_lambda": info.get("constraint_lambda", 0.0) or 0.0,
        "constraint_terms": list(info.get("constraint_terms") or []),
        "n_test": len(info["sample_ids"].get("test", [])),
    }


__all__ = [
    "CSV_HEADER",
    "NO_INTERVAL",
    "PANEL_WARNINGS",
    "chart_rows",
    "has_intervals",
    "metric_rows",
    "results_figure",
    "to_csv",
    "training_summary",
    "violation_rows",
]
