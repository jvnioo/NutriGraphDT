"""Ejecuta todos los baselines y consolida la tabla comparativa (A40-6, #76).

Entrena y evalúa los 5 modelos de referencia de NutriGraphDT sobre una cohorte sintética o
la fuente real D1 HoloFood (solo la cohorte supervisada de `configs/cohorts/`, #138), con
validación cruzada agrupada sin fuga de datos:
- Trivial: `dummy_mean` (A40-4)
- Lineales: `ridge`, `elasticnet` (A40-4)
- Árboles: `random_forest`, `hist_gradient_boosting` (A40-5)

Genera en `--output` (por defecto `reports/baselines`):
- `baseline_comparison.md`: tabla comparativa consolidada (macro y por AGCC) para el
  informe de avance 2 (act. 46).
- `baseline_comparison.csv`: versión tabular delimitada de la tabla comparativa.
- `report.csv` y `report.md`: reporte de evaluación completo con formato común de A40-2.
- `importances.csv`: importancia por permutación sobre `val` para los modelos de árboles.
- `run.json`: metadatos de ejecución, tamaños de partición e hiperparámetros óptimos.

Uso:

    pip install -e ".[dev,baselines]"
    python scripts/compare_baselines.py
    python scripts/compare_baselines.py --output reports/baselines
    python scripts/compare_baselines.py --dataset d1
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from nutrigraphdt.data.cohort import load_cohort
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.models.baselines import (
    IMPORTANCE_SPLIT,
    SYNTHETIC_COHORT_ID,
    BaselineResult,
    LinearBaselineConfig,
    TreeBaselineConfig,
    build_synthetic_baseline_dataset,
    format_comparison_table_csv,
    format_comparison_table_markdown,
    train_all_baselines,
)
from nutrigraphdt.models.tabular import TabularDataset, build_tabular_dataset


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


DEFAULT_LINEAR_CONFIG = _repo_root() / "configs" / "baselines" / "linear.json"
DEFAULT_TREE_CONFIG = _repo_root() / "configs" / "baselines" / "trees.json"
DEFAULT_OUTPUT = _repo_root() / "reports" / "baselines"
DEFAULT_SOURCES = _repo_root() / "configs" / "sources.json"
GRAPH_TARGET_REL_TOL = 1e-6
GRAPH_TARGET_ABS_TOL = 1e-6


def _load_d1_dataset(
    sources_file: Path, *, min_ssu_reads: int | None = None
) -> tuple[TabularDataset, dict[str, str], dict[str, Any]]:
    """Carga D1, retiene la cohorte supervisada (#138) y verifica el mismo target que la GNN."""
    from nutrigraphdt.graph.builder import build_hetero_graph
    from nutrigraphdt.models.gnn.target import add_graph_target

    sources = load_sources(sources_file)
    tables = DataPipeline({"D1_holofood": sources["D1_holofood"]}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(sources["D1_holofood_metadata"]).load(),
        metabolites=MetaboliteLoader(sources["D1_holofood_scfa_content"]).load(),
    )
    complete = build_tabular_dataset(tables).filter_complete_targets()
    cohort = load_cohort(sources, min_ssu_reads=min_ssu_reads)
    outside = sorted(cohort.sample_ids - set(complete.sample_ids))
    if outside:
        raise ValueError(
            f"La cohorte incluye animales sin los tres AGCC en la tabla de atributos: {outside}."
        )
    dataset = complete.filter_samples(cohort.sample_ids)

    with Path(sources["D1_holofood_metadata"].path_or_url).open(
        encoding="utf-8", newline=""
    ) as handle:
        groups = {
            row["sample_id"]: row["pen_code"]
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("sample_id") and row.get("pen_code")
        }

    graphs = build_hetero_graph(tables).graphs
    mismatches: list[dict[str, object]] = []
    verified = 0
    for sample in dataset.samples:
        graph = add_graph_target(graphs[sample.graph_id])
        values = graph.y_graph[0].tolist()
        mask = graph.y_graph_mask[0].tolist()
        expected = [sample.targets[name] for name in dataset.target_names]
        if not all(mask) or any(
            not math.isclose(
                float(actual),
                expected_value,
                rel_tol=GRAPH_TARGET_REL_TOL,
                abs_tol=GRAPH_TARGET_ABS_TOL,
            )
            for actual, expected_value in zip(values, expected, strict=True)
        ):
            mismatches.append(
                {
                    "sample_id": sample.sample_id,
                    "graph_id": sample.graph_id,
                    "tabular_targets": expected,
                    "y_graph": values,
                    "y_graph_mask": mask,
                }
            )
        verified += 1
    if mismatches:
        raise ValueError(
            "Los targets tabulares de D1 no coinciden con y_graph; "
            f"hay {len(mismatches)} discrepancias."
        )

    group_counts = {
        split: len({groups[sample.sample_id] for sample in dataset.get_subset(split).samples})
        for split in ("train", "val", "test")
    }
    return (
        dataset,
        groups,
        {
            "target_verification": {
                "method": "build_hetero_graph + add_graph_target",
                "target_names": list(dataset.target_names),
                "verified_samples": verified,
                "float_comparison_tolerance": {
                    "relative": GRAPH_TARGET_REL_TOL,
                    "absolute": GRAPH_TARGET_ABS_TOL,
                },
                "mismatches": mismatches,
            },
            "group_key": "pen_code",
            "group_counts": group_counts,
            "cohort": cohort.summary(),
        },
    )


def _write_artifacts(
    output: Path,
    result: BaselineResult,
    linear_cfg: LinearBaselineConfig,
    tree_cfg: TreeBaselineConfig,
    run_meta: dict[str, object],
    header: str,
) -> str:
    """Escribe los artefactos comunes de una corrida de baselines."""
    output.mkdir(parents=True, exist_ok=True)
    comparison_md_body = format_comparison_table_markdown(result.report, include_targets=True)
    full_comparison_md = header + comparison_md_body + "\n"
    (output / "baseline_comparison.md").write_text(full_comparison_md, encoding="utf-8")
    (output / "baseline_comparison.csv").write_text(
        format_comparison_table_csv(result.report).replace("\r\n", "\n"), encoding="utf-8"
    )
    (output / "report.csv").write_text(
        result.report.to_csv().replace("\r\n", "\n"), encoding="utf-8"
    )
    (output / "report.md").write_text(result.report.to_markdown() + "\n", encoding="utf-8")

    ranked_importances = {
        model: sorted(items, key=lambda item: item.importance_mean, reverse=True)
        for model, items in result.feature_importances.items()
    }
    with (output / "importances.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["model", "split", "feature", "importance_mean", "importance_std"])
        for model, items in ranked_importances.items():
            for item in items:
                writer.writerow(
                    [
                        model,
                        IMPORTANCE_SPLIT,
                        item.feature,
                        item.importance_mean,
                        item.importance_std,
                    ]
                )

    run_meta.update(
        {
            "subset_sizes": result.subset_sizes,
            "n_features": len(result.feature_names),
            "cv_folds": result.cv_folds,
            "importance_split": IMPORTANCE_SPLIT,
            "linear_config": linear_cfg.to_dict(),
            "tree_config": tree_cfg.to_dict(),
            "best_params": result.best_params,
        }
    )
    (output / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return full_comparison_md


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", choices=("synthetic", "d1"), default="synthetic")
    parser.add_argument("--linear-config", type=Path, default=DEFAULT_LINEAR_CONFIG)
    parser.add_argument("--tree-config", type=Path, default=DEFAULT_TREE_CONFIG)
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument(
        "--min-ssu-reads",
        type=int,
        default=None,
        help="Umbral de lecturas SSU de la cohorte de D1; por defecto, el de configs/cohorts/.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    linear_cfg = LinearBaselineConfig.load(args.linear_config)
    tree_cfg = TreeBaselineConfig.load(args.tree_config)

    if args.dataset == "d1":
        dataset, groups, d1_meta = _load_d1_dataset(args.sources, min_ssu_reads=args.min_ssu_reads)
        cv_folds = int(d1_meta["group_counts"]["train"])
        linear_cfg = replace(linear_cfg, cv_folds=cv_folds)
        tree_cfg = replace(tree_cfg, cv_folds=cv_folds)
        output = args.output or DEFAULT_OUTPUT / "d1"
    else:
        dataset, groups = build_synthetic_baseline_dataset(
            args.n_samples, args.first_seed, args.split_seed
        )
        d1_meta = {}
        output = args.output or DEFAULT_OUTPUT

    result = train_all_baselines(dataset, groups, linear_cfg, tree_cfg)

    if args.dataset == "d1":
        header_md = (
            "# Tabla comparativa consolidada de baselines en D1 HoloFood (A45-2)\n\n"
            f"- **Cohorte:** D1 HoloFood, {len(dataset)} animales de la cohorte supervisada "
            f"`{d1_meta['cohort']['version']}` (≥ {d1_meta['cohort']['min_ssu_reads']} lecturas "
            "SSU, sin perfiles de AGCC repetidos; detalle en `run.json`).\n"
            f"- **Partición (A45-1):** {result.subset_sizes.get('train', 0)} train, "
            f"{result.subset_sizes.get('val', 0)} val, {result.subset_sizes.get('test', 0)} test.\n"
            "- **Grupos de CV:** `pen_code`; "
            f"{d1_meta['group_counts']['train']} corrales en train.\n"
            f"- **Validación cruzada:** {result.cv_folds} folds agrupados sobre train.\n"
            "- **Verificación target GNN:** las muestras y valores de los tres AGCC coinciden "
            "con `add_graph_target` (detalle en `run.json`).\n"
            "- **Hiperparámetros elegidos:**\n"
            "  - `dummy_mean`: sin hiperparámetros (predice la media de train).\n"
            f"  - `ridge`: {result.best_params.get('ridge', {})}.\n"
            f"  - `elasticnet`: {result.best_params.get('elasticnet', {})}.\n"
            f"  - `random_forest`: {result.best_params.get('random_forest', {})}.\n"
            "  - `hist_gradient_boosting`: "
            f"{result.best_params.get('hist_gradient_boosting', {})}.\n\n"
        )
        run_meta: dict[str, object] = {
            "dataset_id": "D1_holofood",
            "group_key": d1_meta["group_key"],
            "group_counts": d1_meta["group_counts"],
            "target_verification": d1_meta["target_verification"],
            "cohort": d1_meta["cohort"],
        }
    else:
        header_md = (
            "# Tabla comparativa consolidada de baselines (A40-6)\n\n"
            f"- **Cohorte:** `{SYNTHETIC_COHORT_ID}` ({args.n_samples} instancias sintéticas, "
            f"semillas {args.first_seed} a {args.first_seed + args.n_samples - 1}).\n"
            f"- **Partición (A40-1):** semilla `{args.split_seed}` "
            f"({result.subset_sizes.get('train', 0)} train, "
            f"{result.subset_sizes.get('val', 0)} val, "
            f"{result.subset_sizes.get('test', 0)} test).\n"
            f"- **Atributos (A40-3):** {len(result.feature_names)} columnas tabulares sin fuga.\n"
            f"- **Validación cruzada:** {result.cv_folds} folds agrupados sobre train.\n"
            "- **Hiperparámetros elegidos:**\n"
            f"  - `dummy_mean`: sin hiperparámetros (predice la media de train).\n"
            f"  - `ridge`: {result.best_params.get('ridge', {})} "
            "(borde superior de la grilla, alpha = 1000.0).\n"
            f"  - `elasticnet`: {result.best_params.get('elasticnet', {})} "
            "(anula coeficientes, idéntico a dummy_mean).\n"
            f"  - `random_forest`: {result.best_params.get('random_forest', {})}.\n"
            "  - `hist_gradient_boosting`: "
            f"{result.best_params.get('hist_gradient_boosting', {})}.\n\n"
            "> [!WARNING]\n"
            "> **Advertencia metodológica para el Informe de Avance 2 "
            "(Célula de Documentación)**:\n"
            "> Esta tabla es **exclusivamente sintética** "
            "(la partición de D1 en `configs/splits/d1_holofood.json`\n"
            "> cubre por ahora solo el fixture de 6 animales) y "
            "**no mide desempeño predictivo real ni constituye\n"
            "> un piso empírico para la GNN**.\n"
            ">\n"
            "> En el generador sintético actual, las concentraciones de AGCC "
            "no dependen de los 24 atributos\n"
            "> tabulares. Por ello, ningún baseline supera a la media "
            "($R^2$ macro en test negativo en todos los\n"
            "> modelos: -0.18 en `dummy_mean`, -0.90 en `hist_gradient_boosting`), "
            "`elasticnet` anula todos los\n"
            "> coeficientes reproduciendo a `dummy_mean`, y `ridge` queda en el "
            "límite superior de la grilla\n"
            "> (alpha = 1000.0).\n"
            ">\n"
            "> El valor de esta tabla radica únicamente en demostrar y verificar "
            "que el flujo de entrenamiento,\n"
            "> partición sin fuga, validación cruzada y extracción de métricas "
            "opera de manera reproducible.\n\n"
        )
        run_meta = {
            "dataset_id": SYNTHETIC_COHORT_ID,
            "n_samples": args.n_samples,
            "first_seed": args.first_seed,
            "split_seed": args.split_seed,
        }
    full_comparison_md = _write_artifacts(output, result, linear_cfg, tree_cfg, run_meta, header_md)

    print(full_comparison_md)
    print(f"Hiperparámetros óptimos: {json.dumps(result.best_params)}")
    print(f"Archivos generados en {output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
