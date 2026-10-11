"""Genera una partición train/val/test estratificada y sin fuga de datos (A40-1, #71).

Uso:

    # Genera la partición canónica para D1 HoloFood a partir del fixture
    python scripts/create_split.py

    # Para una descarga completa en data/raw/D1_holofood/
    python scripts/create_split.py --input data/raw/D1_holofood/metadata.tsv \\
        --output configs/splits/d1_holofood.json --overwrite

    # Configuración personalizada
    python scripts/create_split.py --group-by pen_code --stratify-by diet_treatment_code \\
        --seed 42 --ratios 0.6 0.2 0.2

Código de salida: 0 si la partición se guardó correctamente, 2 si ocurrió un error en los datos.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nutrigraphdt.data.split import create_split, save_split


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera y guarda una partición train/val/test reproducible sin data leakage."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("tests/fixtures/holofood/metadata.tsv"),
        help="Ruta al archivo TSV/CSV de metadatos.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("configs/splits/d1_holofood.json"),
        help="Ruta donde guardar la partición JSON.",
    )
    parser.add_argument(
        "--dataset-id",
        default="D1_holofood",
        help="Identificador del dataset.",
    )
    parser.add_argument(
        "--group-by",
        default="pen_code",
        help="Campo por el cual agrupar para evitar fugas (ej. corral o animal).",
    )
    parser.add_argument(
        "--stratify-by",
        default="diet_treatment_code",
        help="Campo por el cual estratificar (ej. tratamiento dietario).",
    )
    parser.add_argument(
        "--ratios",
        type=float,
        nargs=3,
        default=[0.6, 0.2, 0.2],
        help="Proporciones deseadas (train, val, test).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semilla determinista.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescribir el archivo de salida si ya existe.",
    )
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        print(
            f"El archivo {args.output} ya existe. Use --overwrite para sobrescribir.",
            file=sys.stderr,
        )
        return 2

    if not args.input.exists():
        print(f"El archivo de entrada {args.input} no existe.", file=sys.stderr)
        return 2

    try:
        ratios_tuple = (args.ratios[0], args.ratios[1], args.ratios[2])
        split = create_split(
            args.input,
            group_key=args.group_by,
            stratify_key=args.stratify_by,
            ratios=ratios_tuple,
            seed=args.seed,
            dataset_id=args.dataset_id,
        )
        save_split(split, args.output)
    except Exception as error:
        print(f"Error generando la partición: {error}", file=sys.stderr)
        return 2

    print(f"Partición generada exitosamente en {args.output}:")
    print(f"  Total muestras: {len(split)}")
    print(f"  Train: {len(split.train)} ({split.ratios[0]:.0%})")
    print(f"  Val:   {len(split.val)} ({split.ratios[1]:.0%})")
    print(f"  Test:  {len(split.test)} ({split.ratios[2]:.0%})")
    print(
        f"  Grupos ({args.group_by}): {len(split.groups.get('train', ()))} train, "
        f"{len(split.groups.get('val', ()))} val, {len(split.groups.get('test', ()))} test"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
