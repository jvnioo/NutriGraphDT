"""Ejecuta todos los baselines y consolida la tabla comparativa (A40-6, #76).

Entrena y evalúa los 5 modelos de referencia de NutriGraphDT sobre una misma cohorte sintética
con validación cruzada agrupada sin fuga de datos:
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
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.models.baselines import (
    IMPORTANCE_SPLIT,
    SYNTHETIC_COHORT_ID,
    LinearBaselineConfig,
    TreeBaselineConfig,
    build_synthetic_baseline_dataset,
    format_comparison_table_csv,
    format_comparison_table_markdown,
    train_all_baselines,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


DEFAULT_LINEAR_CONFIG = _repo_root() / "configs" / "baselines" / "linear.json"
DEFAULT_TREE_CONFIG = _repo_root() / "configs" / "baselines" / "trees.json"
DEFAULT_OUTPUT = _repo_root() / "reports" / "baselines"


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--linear-config", type=Path, default=DEFAULT_LINEAR_CONFIG)
    parser.add_argument("--tree-config", type=Path, default=DEFAULT_TREE_CONFIG)
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    linear_cfg = LinearBaselineConfig.load(args.linear_config)
    tree_cfg = TreeBaselineConfig.load(args.tree_config)

    dataset, groups = build_synthetic_baseline_dataset(
        args.n_samples, args.first_seed, args.split_seed
    )
    result = train_all_baselines(dataset, groups, linear_cfg, tree_cfg)

    args.output.mkdir(parents=True, exist_ok=True)

    # 1. Tabla comparativa consolidada (Markdown y CSV)
    comparison_md_body = format_comparison_table_markdown(result.report, include_targets=True)
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
        f"  - `hist_gradient_boosting`: {result.best_params.get('hist_gradient_boosting', {})}.\n\n"
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
    full_comparison_md = header_md + comparison_md_body + "\n"
    (args.output / "baseline_comparison.md").write_text(full_comparison_md, encoding="utf-8")

    comparison_csv = format_comparison_table_csv(result.report)
    (args.output / "baseline_comparison.csv").write_text(comparison_csv, encoding="utf-8")

    # 2. Reporte detallado A40-2
    (args.output / "report.csv").write_text(result.report.to_csv(), encoding="utf-8")
    (args.output / "report.md").write_text(result.report.to_markdown() + "\n", encoding="utf-8")

    # 3. Importancias de atributos para árboles
    ranked_importances = {
        model: sorted(items, key=lambda item: item.importance_mean, reverse=True)
        for model, items in result.feature_importances.items()
    }
    with (args.output / "importances.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
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

    # 4. Metadatos de la corrida
    run_meta = {
        "dataset_id": SYNTHETIC_COHORT_ID,
        "n_samples": args.n_samples,
        "first_seed": args.first_seed,
        "split_seed": args.split_seed,
        "subset_sizes": result.subset_sizes,
        "n_features": len(result.feature_names),
        "importance_split": IMPORTANCE_SPLIT,
        "linear_config": linear_cfg.to_dict(),
        "tree_config": tree_cfg.to_dict(),
        "best_params": result.best_params,
    }
    (args.output / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(full_comparison_md)
    print(f"Hiperparámetros óptimos: {json.dumps(result.best_params)}")
    print(f"Archivos generados en {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
