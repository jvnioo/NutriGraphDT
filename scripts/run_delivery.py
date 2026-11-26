"""Ejecuta el pipeline sintético completo con la configuración de entrega (A117, #347).

Datos → grafo → modelo (con y sin restricciones) → reproducibilidad frente a las corridas
congeladas → simulación del catálogo → explicación, con `configs/delivery.json`. Escribe el
registro en `--output` (por defecto `reports/delivery/`): `results.json` y `report.md`. Las
corridas nuevas quedan en `--work-dir` (por defecto `artifacts/delivery/`, sin versionar).

No usa red ni `data/raw/`. Requiere los extras `graph`, `baselines` y `demo`. Uso:

    python scripts/run_delivery.py

Código de salida: `0` si todo se reproduce y cada escenario da su estado esperado; `1` si hay
alguna desviación sin explicar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nutrigraphdt.delivery import DELIVERY_CONFIG, REPO_ROOT, run_delivery, write_delivery_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DELIVERY_CONFIG)
    parser.add_argument("--work-dir", type=Path, default=REPO_ROOT / "artifacts" / "delivery")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "reports" / "delivery")
    args = parser.parse_args(argv)
    record = run_delivery(args.config, work_dir=args.work_dir)
    write_delivery_report(record, args.output)
    import json

    data = json.loads((args.output / "results.json").read_text(encoding="utf-8"))
    pending = [d["what"] for d in data["deviations"] if not d["explained"]]
    print(f"Reporte: {args.output / 'report.md'}")
    for item in pending:
        print(f"Desviación sin explicar: {item}")
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
