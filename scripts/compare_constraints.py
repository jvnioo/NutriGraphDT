"""Genera o verifica la comparación A73-P2/P3 desde los artefactos versionados."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nutrigraphdt.models.constraints_comparison import (
    build_constraints_comparison,
    verify_constraints_comparison,
)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Compara las tablas existentes con las fuentes registradas sin sobrescribirlas.",
    )
    args = parser.parse_args()
    if args.verify:
        try:
            verified, unverifiable = verify_constraints_comparison(
                d1_dir=args.d1_dir,
                synthetic_dir=args.synthetic_dir,
                baseline_dir=args.baseline_dir,
                plan_path=args.plan,
                output_dir=args.output,
                repo_root=repo_root,
            )
        except (OSError, ValueError) as error:
            print(f"ERROR: verificación A73 fallida: {error}", file=sys.stderr)
            return 1
        for item in verified:
            print(f"OK: {item}")
        for item in unverifiable:
            print(f"NO VERIFICABLE: {item}")
        print("VERIFICACIÓN COMPLETA")
        return 0

    csv_path, report_path, paired_statistics_path = build_constraints_comparison(
        d1_dir=args.d1_dir,
        synthetic_dir=args.synthetic_dir,
        baseline_dir=args.baseline_dir,
        plan_path=args.plan,
        output_dir=args.output,
    )
    print(f"Tabla: {csv_path}")
    print(f"Reporte: {report_path}")
    print(f"Estadísticos pareados: {paired_statistics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
