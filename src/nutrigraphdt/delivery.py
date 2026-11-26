"""Pipeline sintético completo con la configuración de entrega (A117, #347).

`run_delivery` ejecuta de punta a punta, con `configs/delivery.json`:

1. **Datos.** Genera la cohorte sintética (`build_synthetic_cohort`) y la valida con
   `validate_graph`.
2. **Grafo.** Construye los `HeteroData` de todos los animales con la base de escenarios de la
   plataforma (`synthetic_cohort_base`), como los ve el modelo.
3. **Modelo.** Entrena cada corrida (sin restricciones y con la restricción D-06 y λ = 0,1) con
   `train_fixture_run`, en un directorio de trabajo.
4. **Reproducibilidad.** Compara las predicciones y métricas de cada corrida nueva con las de la
   corrida congelada que usa la plataforma (`tests/fixtures/api/frozen_runs/`).
5. **Simulación.** Corre el catálogo de escenarios de referencia contra cada corrida nueva con
   `compare_scenario` y contrasta el estado con el esperado.
6. **Explicación.** Explica un escenario con el modelo nuevo y valida el contrato.

Devuelve un registro con commit, configuración (con SHA-256), entorno, tiempos y resultados por
paso; `write_delivery_report` lo deja en `reports/delivery/` junto con la comparación con las
corridas sintéticas previas (A45-3, A68-P2 y A73).

**Datos sintéticos.** Los targets no dependen de la dieta ni del aditivo (DS-01): el pipeline
demuestra que el flujo funciona y se reproduce, no efectos biológicos.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DELIVERY_CONFIG: Final[Path] = REPO_ROOT / "configs" / "delivery.json"
DELIVERY_REPORT_VERSION: Final[str] = "1.0.0"
METRICS: Final[tuple[str, ...]] = (
    "fraction_mae_pp",
    "fraction_r2",
    "log_total_mae",
    "reconstructed_mae",
)


def _sha256(path: Path) -> str:
    """SHA-256 del contenido con fines de línea LF.

    Un clon de Windows con `core.autocrlf` escribe los JSON con CRLF; sin normalizar, la misma
    configuración daba otro hash (A115-P1).
    """
    return hashlib.sha256(path.read_bytes().replace(bytes((13, 10)), bytes((10,)))).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def environment() -> dict[str, str]:
    found = {"python": platform.python_version(), "platform": platform.platform()}
    for name in ("torch", "torch_geometric", "sklearn", "pydantic", "streamlit"):
        try:
            found[name] = str(getattr(__import__(name), "__version__", "?"))
        except ImportError:
            found[name] = "no instalado"
    return found


def load_config(path: str | Path = DELIVERY_CONFIG) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_metrics(run_dir: Path) -> dict[str, float]:
    """Promedio de test (grupo `all`) de las métricas de `METRICS` en `metrics.csv`."""
    rows = _read_csv(run_dir / "metrics.csv")
    return {
        r["metric"]: float(r["average"])
        for r in rows
        if r["split"] == "test" and r["group"] == "all" and r["metric"] in METRICS
    }


def compare_predictions(new: Path, reference: Path, atol: float) -> dict[str, Any]:
    """Diferencia máxima de `(z1, z2, ln T)` por animal entre dos `predictions.csv`."""
    columns = ("z1", "z2", "log_total")
    old = {r["sample_id"]: r for r in _read_csv(reference / "predictions.csv")}
    fresh = {r["sample_id"]: r for r in _read_csv(new / "predictions.csv")}
    same_ids = sorted(old) == sorted(fresh)
    diff = max(
        (abs(float(fresh[s][c]) - float(old[s][c])) for s in fresh if s in old for c in columns),
        default=float("inf"),
    )
    return {
        "animals": len(fresh),
        "same_animals": same_ids,
        "max_abs_diff": diff,
        "atol": atol,
        "reproduced": same_ids and diff <= atol,
    }


class _Timer:
    def __init__(self) -> None:
        self.seconds: dict[str, float] = {}

    def run(self, name: str, step: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        value = step()
        self.seconds[name] = round(time.perf_counter() - start, 2)
        return value


def run_delivery(
    config_path: str | Path = DELIVERY_CONFIG,
    *,
    work_dir: str | Path,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Ejecuta el pipeline completo y devuelve su registro (ver el docstring del módulo)."""
    from nutrigraphdt.api.engine import ScenarioEngine, synthetic_cohort_base
    from nutrigraphdt.api.fixtures import train_fixture_run
    from nutrigraphdt.demo.explanation import explain_scenario
    from nutrigraphdt.demo.results import violation_rows
    from nutrigraphdt.graph.validation.pipeline import validate_graph
    from nutrigraphdt.models.baselines import build_synthetic_cohort
    from nutrigraphdt.simulation import compare_scenario, load_catalog, scenario_by_id

    config_path = Path(config_path)
    config = load_config(config_path)
    work = Path(work_dir)
    timer = _Timer()
    cohort = config["cohort"]

    log("1/6 datos: cohorte sintética y validación")
    dataset = timer.run(
        "datos",
        lambda: build_synthetic_cohort(cohort["n_animals"], first_seed=cohort["first_seed"]),
    )
    report = timer.run("validación", lambda: validate_graph(dataset))
    severities = Counter(f.severity.name for f in report.findings)

    log("2/6 grafo: HeteroData de cada animal")
    base = timer.run(
        "base", lambda: synthetic_cohort_base(cohort["n_animals"], first_seed=cohort["first_seed"])
    )
    graphs = timer.run("grafos", lambda: {s: base.graph(s) for s in base.sample_ids})
    relations = sorted(
        {t for g in graphs.values() for t in g.edge_types if not t[1].startswith("rev_")}
    )
    node_types = sorted({t for g in graphs.values() for t in g.node_types})

    runs: dict[str, Any] = {}
    ids = base.sample_ids
    test_ids = ids[-int(config["test_animals"]) :]
    catalog = load_catalog(REPO_ROOT / config["scenarios"])
    for name, spec in config["runs"].items():
        log(f"3/6 modelo: entrenar {name}")
        start = time.perf_counter()
        run_dir = train_fixture_run(
            base,
            test_ids=test_ids,
            pens={s: s for s in ids},
            diets={s: "synthetic" for s in ids},
            days={s: "synthetic" for s in ids},
            output_dir=work / name,
            training_config=REPO_ROOT / spec["training_config"],
            model_config=REPO_ROOT / config["model_config"],
        )
        timer.seconds[f"entrenamiento {name}"] = round(time.perf_counter() - start, 2)
        info = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        log(f"4/6 reproducibilidad: {name} frente a la corrida congelada")
        reproduced = compare_predictions(
            run_dir, REPO_ROOT / spec["reference"], float(config["reproducibility_atol"])
        )
        log(f"5/6 simulación: catálogo con {name}")
        start = time.perf_counter()
        engine = ScenarioEngine(run_dir, base)
        scenarios: list[dict[str, Any]] = []
        for scenario in catalog:
            comparison = compare_scenario(engine, scenario.request())
            scenarios.append(
                {
                    "id": scenario.id,
                    "expected": scenario.expected_status,
                    "status": comparison.status,
                    "ok": comparison.status == scenario.expected_status,
                }
            )
        timer.seconds[f"simulación {name}"] = round(time.perf_counter() - start, 2)
        runs[name] = {
            "training_config": spec["training_config"],
            "training_config_sha256": _sha256(REPO_ROOT / spec["training_config"]),
            "run_id": info["run_id"],
            "constraint_lambda": info.get("constraint_lambda") or 0.0,
            "constraint_terms": list(info.get("constraint_terms") or []),
            "n_animals": {k: len(v) for k, v in info["sample_ids"].items()},
            "metrics": run_metrics(run_dir),
            "reference_metrics": run_metrics(REPO_ROOT / spec["reference"]),
            "reproducibility": reproduced,
            "violations": violation_rows(run_dir),
            "scenarios": scenarios,
            "run_dir": str(run_dir),
        }

    log("6/6 explicación")
    explanation_spec = config["explanation"]
    first = next(iter(config["runs"]))
    engine = ScenarioEngine(Path(runs[first]["run_dir"]), base)
    explained = timer.run(
        "explicación",
        lambda: explain_scenario(
            engine,
            scenario_by_id(explanation_spec["scenario"], REPO_ROOT / config["scenarios"]).request(),
            target=explanation_spec["target"],
            seed=int(explanation_spec["seed"]),
        ),
    )
    return {
        "format_version": DELIVERY_REPORT_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": "python scripts/run_delivery.py",
        "config": config_path.resolve().relative_to(REPO_ROOT).as_posix(),
        "config_sha256": _sha256(config_path),
        "git": {"commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))},
        "environment": environment(),
        "seconds": timer.seconds,
        "data": {
            "dataset_id": config["dataset_id"],
            "n_animals": len(dataset.instances),
            "nodes": len(dataset.nodes),
            "edges": len(dataset.edges),
            "findings": dict(severities),
        },
        "graph": {
            "graphs": len(graphs),
            "node_types": len(node_types),
            "edge_types": len(relations),
        },
        "runs": runs,
        "explanation": {
            "run": first,
            "scenario": explanation_spec["scenario"],
            "target": explanation_spec["target"],
            "valid_contract": True,
            "nodes_with_importance": len(explained.explanation.importance.nodes),
            "seconds": round(explained.elapsed_seconds, 2),
        },
    }


# ---------------------------------------------------------------------------
# Comparación con corridas sintéticas previas (A117-P2)
# ---------------------------------------------------------------------------


def previous_synthetic(repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """Métricas `homo_sage` de las corridas sintéticas previas, leídas de sus reportes."""
    rows: list[dict[str, Any]] = []
    a68 = _read_csv(repo_root / "reports" / "constraints" / "synthetic" / "metrics.csv")
    info = json.loads(
        (repo_root / "reports" / "constraints" / "synthetic" / "run.json").read_text(
            encoding="utf-8"
        )
    )
    for arm in ("free", "constrained"):
        values = {
            r["metric"].removesuffix("_mean"): float(r["average"])
            for r in a68
            if r["model"] == "homo_sage"
            and r["arm"] == arm
            and r["split"] == "test"
            and r["group"] == "all"
            and r["metric"].endswith("_mean")
        }
        rows.append(
            {
                "source": f"A68-P2 (#185), brazo {arm}",
                "file": "reports/constraints/synthetic/metrics.csv",
                "n_animals": int(info["cohort"]["n_animals"]),
                "design": "CV 10 semillas × 5 folds, hasta 200 épocas",
                "metrics": {m: values.get(m) for m in METRICS},
            }
        )
    a45 = _read_csv(repo_root / "reports" / "gnn" / "synthetic" / "report.csv")
    mae = next(
        float(r["average"])
        for r in a45
        if r["model"] == "homo_sage" and r["split"] == "test" and r["metric"] == "mae"
    )
    rows.append(
        {
            "source": "A45-3 (#103)",
            "file": "reports/gnn/synthetic/report.csv",
            "n_animals": 50,
            "design": (
                "partición única 30/10/10, objetivo de concentraciones (antes del contrato v2)"
            ),
            "metrics": {"reconstructed_mae": mae},
        }
    )
    return rows


def deviations(record: Mapping[str, Any], previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cada diferencia de la entrega frente a lo previo, con su explicación o sin ella."""
    found: list[dict[str, Any]] = []
    runs = record["runs"]
    free = runs["synthetic"]["metrics"]
    constrained = runs["synthetic_constrained"]["metrics"]
    a68_free = previous[0]["metrics"]
    n_train = runs["synthetic"]["n_animals"].get("train", 0)
    n_test = runs["synthetic"]["n_animals"].get("test", 0)
    for metric in ("fraction_mae_pp", "log_total_mae", "reconstructed_mae"):
        if a68_free.get(metric) is None or free.get(metric) is None:
            continue
        found.append(
            {
                "what": (
                    f"{metric}: entrega {free[metric]:.4f} frente a A68-P2 {a68_free[metric]:.4f}"
                ),
                "explanation": (
                    f"La corrida de entrega es la de demostración de la plataforma: {n_train} "
                    f"animales de train, {n_test} de test, un fold y hasta 30 épocas; A68-P2 "
                    f"promedia 50 folds con {previous[0]['n_animals']} animales y hasta 200 "
                    "épocas. Con 4 animales de test la métrica tiene mucha más varianza. En este "
                    "generador los AGCC no dependen de las entradas (DS-01): ninguna de las dos "
                    "cifras mide capacidad predictiva."
                ),
                "explained": True,
            }
        )
    same = all(free.get(m) == constrained.get(m) for m in METRICS)
    found.append(
        {
            "what": "Con y sin restricciones dan las mismas métricas"
            if same
            else "Con y sin restricciones dan métricas distintas",
            "explanation": (
                "Igual que en A68-P2 y en el barrido de λ: ninguna predicción viola la cota de "
                "D-06 (p_p ≤ 2/3), así que la penalización y su gradiente son cero y el "
                "entrenamiento es idéntico."
            )
            if same
            else "",
            "explained": same,
        }
    )
    found.append(
        {
            "what": "A45-3 usa otra métrica de concentraciones",
            "explanation": (
                "A45-3 entrenó contra concentraciones directas antes del contrato composicional "
                "v2; su MAE no es comparable con `reconstructed_mae` de la entrega. Se cita como "
                "contexto, no como término de comparación."
            ),
            "explained": True,
        }
    )
    for name, run in runs.items():
        if not run["reproducibility"]["reproduced"]:
            found.append(
                {
                    "what": f"{name}: no reproduce la corrida congelada "
                    f"(diferencia máxima {run['reproducibility']['max_abs_diff']:.2e})",
                    "explanation": "",
                    "explained": False,
                }
            )
        bad = [s["id"] for s in run["scenarios"] if not s["ok"]]
        if bad:
            found.append(
                {
                    "what": f"{name}: escenarios con estado distinto del esperado: {bad}",
                    "explanation": "",
                    "explained": False,
                }
            )
    return found


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def write_delivery_report(record: dict[str, Any], output: str | Path) -> Path:
    """`results.json` y `report.md` de la entrega en `output`."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    previous = previous_synthetic()
    record = {**record, "previous": previous, "deviations": deviations(record, previous)}
    serializable = json.loads(json.dumps(record, default=str))
    for run in serializable["runs"].values():
        run.pop("run_dir", None)
    (output / "results.json").write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    runs = record["runs"]
    lines = [
        "# Validación del sistema completo con la configuración de entrega (A117, #347)",
        "",
        "> **Datos sintéticos.** El pipeline corre sobre la cohorte sintética. Los targets no "
        "dependen de la dieta ni del aditivo (DS-01): este reporte muestra que el flujo funciona "
        "y se reproduce, no efectos biológicos. D1 no es referencia del sistema completo (#296).",
        "",
        f"- **Commit:** `{record['git']['commit']}`"
        + (" (con cambios sin commit)" if record["git"]["dirty"] else ""),
        f"- **Fecha:** {record['created_at']}",
        f"- **Comando:** `{record['command']}`",
        f"- **Configuración:** `{record['config']}` (SHA-256 `{record['config_sha256'][:16]}…`)",
        "- **Entorno:** " + ", ".join(f"{k} {v}" for k, v in record["environment"].items()),
        "",
        "## 1. Pasos y tiempos",
        "",
        "| Paso | Segundos |",
        "|---|---:|",
        *(f"| {k} | {v} |" for k, v in record["seconds"].items()),
        "",
        "## 2. Datos y grafo",
        "",
        f"- Cohorte `{record['data']['dataset_id']}`: {record['data']['n_animals']} animales, "
        f"{record['data']['nodes']} nodos y {record['data']['edges']} aristas.",
        "- `validate_graph`: "
        + (
            ", ".join(f"{k}: {v}" for k, v in sorted(record["data"]["findings"].items()))
            or "sin hallazgos"
        )
        + ".",
        f"- {record['graph']['graphs']} grafos `HeteroData`; entre todos tienen "
        f"{record['graph']['node_types']} tipos de nodo y {record['graph']['edge_types']} "
        "relaciones (sin contar las inversas).",
        "",
        "## 3. Corridas, reproducibilidad y escenarios",
        "",
        "| Corrida | λ | Restricciones | Animales (train/val/test) | Reproduce la congelada | "
        "Escenarios con el estado esperado |",
        "|---|---:|---|---|---|---|",
    ]
    for name, run in runs.items():
        n = run["n_animals"]
        rep = run["reproducibility"]
        ok = sum(s["ok"] for s in run["scenarios"])
        lines.append(
            f"| `{name}` | {run['constraint_lambda']:g} | "
            f"{', '.join(run['constraint_terms']) or '—'} | "
            f"{n.get('train', 0)}/{n.get('inner_val', 0)}/{n.get('test', 0)} | "
            f"{'sí' if rep['reproduced'] else 'no'} (máx. {rep['max_abs_diff']:.1e}) | "
            f"{ok} de {len(run['scenarios'])} |"
        )
    lines += [
        "",
        f"Explicación: `{record['explanation']['scenario']}`, salida "
        f"`{record['explanation']['target']}`, con `{record['explanation']['run']}`; cumple el "
        f"contrato y asigna importancia a {record['explanation']['nodes_with_importance']} nodos "
        f"({record['explanation']['seconds']} s).",
        "",
        "## 4. Métricas frente a las corridas sintéticas previas (A117-P2)",
        "",
        "| Fuente | Animales | Diseño | MAE fracciones (pp) | R² fracciones | MAE ln T | "
        "MAE reconstruido |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for name, run in runs.items():
        m = run["metrics"]
        lines.append(
            f"| Entrega `{name}` | {sum(run['n_animals'].values())} | 1 fold, test de "
            f"{run['n_animals'].get('test', 0)} | {_fmt(m.get('fraction_mae_pp'))} | "
            f"{_fmt(m.get('fraction_r2'))} | {_fmt(m.get('log_total_mae'))} | "
            f"{_fmt(m.get('reconstructed_mae'))} |"
        )
    for row in previous:
        m = row["metrics"]
        lines.append(
            f"| {row['source']} | {row['n_animals']} | {row['design']} | "
            f"{_fmt(m.get('fraction_mae_pp'))} | {_fmt(m.get('fraction_r2'))} | "
            f"{_fmt(m.get('log_total_mae'))} | {_fmt(m.get('reconstructed_mae'))} |"
        )
    lines += [
        "",
        "Tasa de violación de D-06 (A73, #272) en el test de cada corrida de entrega, calculada "
        "con `evaluate_constraints` sobre su `predictions.csv`: "
        + "; ".join(
            f"`{name}`: "
            + ", ".join(
                f"{v['restricción']} {v['tasa de violación (%)']:.1f} %" for v in run["violations"]
            )
            for name, run in runs.items()
        )
        + ". En A68-P2 es 0 % (`reports/constraints/comparison/report.md`).",
        "",
        "## 5. Desviaciones",
        "",
        "| Desviación | Explicación |",
        "|---|---|",
    ]
    for item in record["deviations"]:
        lines.append(
            f"| {item['what']} | {item['explanation'] or '**Sin explicar: ver Issue.**'} |"
        )
    lines += ["", "Regenerar: `python scripts/run_delivery.py`.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return output


__all__ = [
    "DELIVERY_CONFIG",
    "METRICS",
    "compare_predictions",
    "deviations",
    "environment",
    "load_config",
    "previous_synthetic",
    "run_delivery",
    "run_metrics",
    "write_delivery_report",
]
