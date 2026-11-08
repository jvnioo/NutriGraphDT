"""Genera la tabla y el reporte de comparación A73-P2 desde artefactos versionados."""

from __future__ import annotations

import argparse
from pathlib import Path

from nutrigraphdt.models.constraints_comparison import build_constraints_comparison


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d1-dir", type=Path, default=repo_root / "reports/constraints/d1")
    parser.add_argument(
        "--synthetic-dir", type=Path, default=repo_root / "reports/constraints/synthetic"
    )
    parser.add_argument(
        "--baseline-dir", type=Path, default=repo_root / "reports/baselines/d1_composition"
    )
    parser.add_argument(
        "--plan", type=Path, default=repo_root / "configs/splits/d1_holofood_cv.json"
    )
    parser.add_argument("--output", type=Path, default=repo_root / "reports/constraints/comparison")
    args = parser.parse_args()
    csv_path, report_path = build_constraints_comparison(
        d1_dir=args.d1_dir,
        synthetic_dir=args.synthetic_dir,
        baseline_dir=args.baseline_dir,
        plan_path=args.plan,
        output_dir=args.output,
    )
    print(f"Tabla: {csv_path}")
    print(f"Reporte: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
