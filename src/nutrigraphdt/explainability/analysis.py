"""Análisis, agregación y reporte de explicaciones de modelos GNN (A71, #277).

Implementa la agregación de resultados fuera de fold (C-05), la tabulación de la estabilidad de
Nogueira (C-07, A71-P2, #279) y la generación del reporte técnico con advertencias obligatorias
(A71-P3, #280).
"""

from __future__ import annotations

import csv
import math
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from nutrigraphdt.explainability.criteria import INSTABILITY_THRESHOLD
from nutrigraphdt.explainability.out_of_fold import AnimalExplanations, OutOfFoldPlan


@dataclass(frozen=True)
class StabilityRow:
    """Fila para `stability.csv` con las dos estabilidades informadas por separado (C-07)."""

    sample_id: str
    output: str
    k: int
    d: int
    explainer_phi_mean: float
    explainer_ci_low_mean: float
    explainer_ci_high_mean: float
    kendall_mean: float
    unstable_seeds_count: int
    plan_phi: float | None
    plan_ci_low: float | None
    plan_ci_high: float | None
    total_seeds: int
    missing_seeds: str


@dataclass(frozen=True)
class TopKElementRow:
    """Frecuencia de aparición de un elemento en el subgrafo explicativo top-k."""

    output: str
    element_type: str  # "edge", "taxon", "function"
    element_id: str
    count: int
    frequency: float
    evidence_status: str


def build_stability_rows(results: Sequence[AnimalExplanations]) -> list[StabilityRow]:
    """Construye las filas de estabilidad para cada animal y salida evaluada."""
    rows: list[StabilityRow] = []
    for animal in results:
        if not animal.by_seed:
            continue
        reports = list(animal.by_seed.values())
        k = reports[0].k
        d = reports[0].d
        phi_mean = statistics.fmean(r.phi for r in reports)
        ci_low_mean = statistics.fmean(r.ci_low for r in reports)
        ci_high_mean = statistics.fmean(r.ci_high for r in reports)
        kendall_vals = [r.kendall_mean for r in reports if not math.isnan(r.kendall_mean)]
        kendall_mean = statistics.fmean(kendall_vals) if kendall_vals else float("nan")
        unstable_count = sum(1 for r in reports if r.unstable)

        p_low = animal.plan_ci[0] if animal.plan_ci is not None else None
        p_high = animal.plan_ci[1] if animal.plan_ci is not None else None
        missing_str = ",".join(str(s) for s in animal.missing_seeds)

        k_val = round(kendall_mean, 4) if not math.isnan(kendall_mean) else float("nan")
        p_phi = round(animal.plan_phi, 4) if animal.plan_phi is not None else None
        rows.append(
            StabilityRow(
                sample_id=animal.sample_id,
                output=animal.output,
                k=k,
                d=d,
                explainer_phi_mean=round(phi_mean, 4),
                explainer_ci_low_mean=round(ci_low_mean, 4),
                explainer_ci_high_mean=round(ci_high_mean, 4),
                kendall_mean=k_val,
                unstable_seeds_count=unstable_count,
                plan_phi=p_phi,
                plan_ci_low=round(p_low, 4) if p_low is not None else None,
                plan_ci_high=round(p_high, 4) if p_high is not None else None,
                total_seeds=len(animal.by_seed),
                missing_seeds=missing_str,
            )
        )
    return rows


def write_stability_csv(path: Path | str, rows: Sequence[StabilityRow]) -> None:
    """Escribe el archivo `stability.csv`."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "output",
        "k",
        "d",
        "explainer_phi_mean",
        "explainer_ci_low_mean",
        "explainer_ci_high_mean",
        "kendall_mean",
        "unstable_seeds_count",
        "plan_phi",
        "plan_ci_low",
        "plan_ci_high",
        "total_seeds",
        "missing_seeds",
    ]
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(asdict(r))


def collect_top_k_elements(results: Sequence[AnimalExplanations]) -> list[TopKElementRow]:
    """Identifica taxones, KO y aristas más frecuentes en el top-k por salida."""
    outputs = sorted({a.output for a in results})
    rows: list[TopKElementRow] = []

    for out in outputs:
        out_animals = [a for a in results if a.output == out]
        total_subgraphs = 0
        edge_counter: Counter[tuple[str, str, str, str, str, str]] = Counter()
        taxon_counter: Counter[str] = Counter()
        function_counter: Counter[str] = Counter()

        for animal in out_animals:
            for report in animal.by_seed.values():
                # Tomamos la primera explicación de cada reporte para no sobrerrepresentar
                exp = report.explanations[0]
                total_subgraphs += 1

                for edge_ref in exp.subgraph.edges:
                    # Encontrar evidencia en importance.edges
                    ev_status = "none"
                    for e in exp.importance.edges:
                        if (
                            e.source_type == edge_ref.source_type
                            and e.relation_type == edge_ref.relation_type
                            and e.target_type == edge_ref.target_type
                            and e.source_id == edge_ref.source_id
                            and e.target_id == edge_ref.target_id
                        ):
                            if e.evidence is not None:
                                ev_status = e.evidence.evidence_status
                            break
                    edge_key = (
                        edge_ref.source_type,
                        edge_ref.relation_type,
                        edge_ref.target_type,
                        edge_ref.source_id,
                        edge_ref.target_id,
                        ev_status,
                    )
                    edge_counter[edge_key] += 1

                for node_ref in exp.subgraph.nodes:
                    if node_ref.node_type == "taxon":
                        taxon_counter[node_ref.node_id] += 1
                    elif node_ref.node_type == "function":
                        function_counter[node_ref.node_id] += 1

        if total_subgraphs == 0:
            continue

        # Ordenar y agregar
        for (st, rel, tt, sid, tid, ev), count in edge_counter.most_common():
            edge_repr = f"({st}:{sid}) -[{rel}]-> ({tt}:{tid})"
            rows.append(
                TopKElementRow(
                    output=out,
                    element_type="edge",
                    element_id=edge_repr,
                    count=count,
                    frequency=round(count / total_subgraphs, 4),
                    evidence_status=ev,
                )
            )

        for taxon_id, count in taxon_counter.most_common():
            rows.append(
                TopKElementRow(
                    output=out,
                    element_type="taxon",
                    element_id=taxon_id,
                    count=count,
                    frequency=round(count / total_subgraphs, 4),
                    evidence_status="observed",
                )
            )

        for func_id, count in function_counter.most_common():
            rows.append(
                TopKElementRow(
                    output=out,
                    element_type="function",
                    element_id=func_id,
                    count=count,
                    frequency=round(count / total_subgraphs, 4),
                    evidence_status="annotated",
                )
            )

    return rows


def write_top_k_csv(path: Path | str, rows: Sequence[TopKElementRow]) -> None:
    """Escribe el archivo `top_k_elements.csv`."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["output", "element_type", "element_id", "count", "frequency", "evidence_status"]
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(asdict(r))


def generate_explainability_report(
    results: Sequence[AnimalExplanations],
    plan: OutOfFoldPlan,
    *,
    variant: str,
    edges_arm: str,
    top_k: int,
) -> str:
    """Genera el contenido markdown de `reports/explainability/d1/report.md` (A71-P3, #280)."""
    stability_rows = build_stability_rows(results)
    top_k_rows = collect_top_k_elements(results)

    outputs = sorted({r.output for r in results})
    total_animals = len(plan.assignments)
    missing_animals = [s for s, m in plan.missing.items() if len(m) == len(plan.seeds)]

    # Conteo de inestabilidad
    unstable_by_out: dict[str, int] = {}
    phi_by_out: dict[str, list[float]] = {}
    plan_phi_by_out: dict[str, list[float]] = {}
    for r in stability_rows:
        phi_by_out.setdefault(r.output, []).append(r.explainer_phi_mean)
        if r.explainer_phi_mean < INSTABILITY_THRESHOLD:
            unstable_by_out[r.output] = unstable_by_out.get(r.output, 0) + 1
        if r.plan_phi is not None:
            plan_phi_by_out.setdefault(r.output, []).append(r.plan_phi)

    lines = [
        "# Primeras explicaciones de animales reales de D1 (A71-P3, #280)",
        "",
        f"- **Variante:** `{variant}` (brazo `{edges_arm}`) evaluada fuera de fold (C-05).",
        (
            f"- **Cohorte evaluada:** {total_animals} animales de `D1_holofood`; "
            f"faltantes: {len(missing_animals)}."
        ),
        f"- **Salidas explicadas:** {', '.join(f'`{o}`' for o in outputs)}.",
        (
            f"- **Subgrafo top-k:** k = {top_k} aristas por valor absoluto con desempate léxico "
            "determinista."
        ),
        "- **Explicador:** `EdgeGradientSaliency` (determinista, gradiente exacto sobre aristas).",
        "",
        "## 1. Lo que se puede y no se puede afirmar (decisión #256, sección 4)",
        "",
        "| Se puede afirmar | No se puede afirmar |",
        "|---|---|",
        (
            "| Las asociaciones aprendidas por la GNN entre entradas del grafo y "
            "salidas de AGCC. | "
            "Causalidad, actividad metabólica ni flujo funcional real en el ciego. |"
        ),
        (
            "| Qué géneros y KO aparecen con mayor frecuencia relativa en el subgrafo top-k. | "
            "Que la dieta o los aditivos actúen a través del microbioma (#258). |"
        ),
        (
            "| Estabilidad cuantitativa del top-k entre semillas del explicador (C-07) "
            "y del plan. | "
            "Validación biológica ni mecanismos confirmados sin evidencia experimental "
            "independiente. |"
        ),
        (
            "| Que la estructura es funcional anotada basada en homología y catálogos públicos. | "
            "Estructura mecanística demostrada para las interacciones. |"
        ),
        "",
        "## 2. Marco metodológico y límites del modelo",
        "",
        (
            "1. **Estructura funcional anotada, no mecanística (#256).** La red conecta "
            "taxones agregados a nivel"
        ),
        (
            "   de género con capacidades metabólicas anotadas (`has_capacity`) y metabolitos "
            "(`produces`)."
        ),
        "   No modela cinética enzimática, dinámica poblacional ni absorción intestinal.",
        (
            "2. **La GNN no supera a `ridge` por familia (#268).** En D1, la GNN alcanza 3,90 pp "
            "de MAE macro"
        ),
        (
            "   de fracciones frente a 3,69 pp de `ridge_family`. La diferencia no es "
            "estadísticamente demostrable"
        ),
        ("   y el grafo no añade ventaja predictiva demostrable sobre los baselines tabulares."),
        (
            "3. **Explicación estrictamente fuera de fold (C-05, #241).** Cada animal se explica "
            "exclusivamente con"
        ),
        (
            "   el modelo del fold en que estuvo en test y con el escalador ajustado únicamente en "
            "el conjunto"
        ),
        ("   de entrenamiento de ese fold. Se previene cualquier memorización o fuga de datos."),
        (
            "4. **Cobertura por AGCC (#256, sección 5).** La cobertura de la ruta funcional es "
            "heterogénea entre metabolitos:"
        ),
        "",
        (
            "| AGCC | Géneros con ruta | % lecturas a género | % del total de lecturas | "
            "Soporte de la ruta |"
        ),
        "|---|---:|---:|---:|---|",
        "| Acetato | 35 | 36,1 % | 16,1 % | Moderado (*Faecalibacterium* dominante) |",
        "| n-Butirato | 14 | 35,8 % | 16,0 % | Moderado (*Faecalibacterium* dominante) |",
        "| Propionato | 7 | 2,1 % | 0,9 % | **Muy bajo soporte**: solo 2,1 % de lecturas |",
        "",
        "> [!WARNING]",
        (
            "> **Bajo soporte del propionato:** Para el propionato, solo el 2,1 % de las "
            "lecturas a género y"
        ),
        (
            "> el 0,9 % del total poseen anotación en la ruta. Las explicaciones sobre "
            "`log_propionate_acetate`"
        ),
        (
            "> tienen base empírica muy limitada y no deben interpretarse como "
            "representativas del ciego."
        ),
        "",
        "## 3. Análisis de estabilidad (A71-P2, #279)",
        "",
        "Se midieron las dos estabilidades de forma independiente, conforme a la regla C-07:",
        (
            "- **Estabilidad entre semillas del explicador:** Índice $\\hat{\\Phi}$ de Nogueira et "
            "al. (2018) con IC 95 %"
        ),
        (
            "  asintótico, comparando las selecciones del top-k con el modelo fijo a lo largo "
            "de 5 semillas."
        ),
        (
            "- **Estabilidad entre semillas del plan:** $\\hat{\\Phi}_{plan}$ evaluado sobre la "
            "primera corrida de cada modelo."
        ),
        (
            "- **Umbral de inestabilidad:** 0,40. *Aclaración:* El umbral 0,40 es "
            "**provisional** (trasladado desde"
        ),
        (
            "  selección de variables en aprendizaje estadístico) y no constituye un estándar "
            "establecido en la literatura."
        ),
        "",
        (
            "| Salida | Animales evaluados | $\\hat{\\Phi}$ medio explicador | "
            "$\\hat{\\Phi}$ medio plan | Animales bajo umbral (< 0,40) |"
        ),
        "|---|---:|---:|---:|---:|",
    ]

    for out in outputs:
        p_list = phi_by_out.get(out, [])
        pp_list = plan_phi_by_out.get(out, [])
        mean_p = statistics.fmean(p_list) if p_list else float("nan")
        mean_pp = statistics.fmean(pp_list) if pp_list else float("nan")
        unstable = unstable_by_out.get(out, 0)
        pct = (unstable / len(p_list) * 100) if p_list else 0.0
        pp_str = f"{mean_pp:.4f}" if not math.isnan(mean_pp) else "N/A (< 2 semillas)"
        lines.append(
            f"| `{out}` | {len(p_list)} | {mean_p:.4f} | {pp_str} | "
            f"{unstable} / {len(p_list)} ({pct:.1f} %) |"
        )

    lines.extend(
        [
            "",
            "## 4. Elementos más frecuentes en el subgrafo top-k",
            "",
            "Aparición relativa de taxones, funciones KO y aristas en el subgrafo top-k:",
            "",
        ]
    )

    for out in outputs:
        lines.extend(
            [
                f"### Salida `{out}`",
                "",
                "#### Taxones más frecuentes en el subgrafo top-k",
                "| Género / Taxón | Frecuencia | Apariciones |",
                "|---|---:|---:|",
            ]
        )
        taxa = [r for r in top_k_rows if r.output == out and r.element_type == "taxon"][:8]
        if taxa:
            for t in taxa:
                lines.append(f"| `{t.element_id}` | {t.frequency * 100:.1f} % | {t.count} |")
        else:
            lines.append("| *Sin taxones en top-k* | — | — |")

        lines.extend(
            [
                "",
                "#### Funciones (KO) más frecuentes en el subgrafo top-k",
                "| Función (KO) | Frecuencia | Apariciones | Evidencia |",
                "|---|---:|---:|---|",
            ]
        )
        funcs = [r for r in top_k_rows if r.output == out and r.element_type == "function"][:8]
        if funcs:
            for f in funcs:
                lines.append(
                    f"| `{f.element_id}` | {f.frequency * 100:.1f} % | {f.count} | "
                    f"`{f.evidence_status}` |"
                )
        else:
            lines.append("| *Sin funciones en top-k* | — | — | — |")

        lines.extend(
            [
                "",
                "#### Aristas con mayor frecuencia en el subgrafo top-k",
                "| Arista | Frecuencia | Apariciones | Evidencia |",
                "|---|---:|---:|---|",
            ]
        )
        edges = [r for r in top_k_rows if r.output == out and r.element_type == "edge"][:8]
        if edges:
            for e in edges:
                lines.append(
                    f"| `{e.element_id}` | {e.frequency * 100:.1f} % | {e.count} | "
                    f"`{e.evidence_status}` |"
                )
        else:
            lines.append("| *Sin aristas en top-k* | — | — | — |")
        lines.append("")

    lines.extend(
        [
            "## 5. Advertencias obligatorias del contrato (C-02, EXP-08)",
            "",
            "Toda explicación emitida incluye las advertencias de interpretación exigidas:",
            (
                "- `association_not_causation`: Importancia calculada refleja asociación dentro "
                "del modelo, no causalidad."
            ),
            (
                "- `importance_is_not_evidence`: La importancia matemática no equivale a "
                "evidencia biológica."
            ),
            (
                "- `diet_day_confounding`: Confusión entre dieta y día de muestreo "
                "en la cohorte de D1."
            ),
            (
                "- `exploratory_treatment_contrast`: Desbalance muestral (34/15/7 animales); "
                "contrastes son exploratorios."
            ),
            (
                "- `model_not_better_than_day_only`: La GNN no supera consistentemente al "
                "baseline ingenuo de día."
            ),
            "",
            "## 6. Conclusiones y recomendaciones para el informe",
            "",
            (
                "1. Presentar las explicaciones como una inspección técnica de sensibilidad de la "
                "red sobre una"
            ),
            "   **estructura funcional anotada**, evitando terminología causal o mecanística.",
            (
                "2. Subrayar que los resultados de propionato carecen de representatividad por la "
                "cobertura del 2,1 %."
            ),
            (
                "3. Acompañar siempre cada visualización con la advertencia de estabilidad y el "
                "desglose de evidencias."
            ),
            "",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utilidades para el CLI (A71-P1)
# ---------------------------------------------------------------------------

_OUTPUT_ALIASES: dict[str, str] = {
    "propionate": "log_propionate_acetate",
    "butyrate": "log_butyrate_acetate",
    "total": "log_total",
}
"""Alias cortos para --outputs en el CLI de explain_gnn.py."""

_VALID_FULL_NAMES: frozenset[str] = frozenset(
    {
        "log_propionate_acetate",
        "log_butyrate_acetate",
        "log_total",
    }
)


def parse_outputs_argument(raw: Sequence[str]) -> tuple[str, ...]:
    """Convierte los alias del CLI de `--outputs` a nombres completos del contrato.

    Acepta alias cortos (`propionate`, `butyrate`, `total`) o nombres completos
    (`log_propionate_acetate`, ...).  Lanza `ValueError` si algún elemento no se reconoce.

    Returns:
        Tupla de nombres de salida en el orden en que se pasaron.

    Raises:
        ValueError: si algún nombre no es un alias ni un nombre completo válido.
    """
    resolved: list[str] = []
    unrecognized: list[str] = []
    for name in raw:
        if name in _OUTPUT_ALIASES:
            resolved.append(_OUTPUT_ALIASES[name])
        elif name in _VALID_FULL_NAMES:
            resolved.append(name)
        else:
            unrecognized.append(name)
    if unrecognized:
        valid = sorted(_VALID_FULL_NAMES)
        raise ValueError(
            f"Salidas no reconocidas: {unrecognized}. "
            f"Use alias ({list(_OUTPUT_ALIASES)}) o nombres completos ({valid})."
        )
    return tuple(resolved)
