"""Regenera las corridas de demostración de `tests/fixtures/api/frozen_runs/` (A81-P2, #288).

Entrena dos corridas pequeñas con `nutrigraphdt.api.fixtures.train_fixture_run`:

- `synthetic`: cohorte **sintética** de 20 animales (`build_synthetic_cohort`, semillas 1 a 20);
  test = los 4 últimos animales.
- `d1_fixture`: los seis animales **reales** del fixture de D1 (`tests/fixtures/holofood/`); test
  = un animal Control (SAMEA112904810). Cada animal tiene su propio corral, así que el val interno
  es un corral. Con cinco animales de train no se puede estratificar por dieta (el Control
  restante es uno solo), así que el reparto interno usa un único estrato.

No usa red ni la descarga completa de D1. Las predicciones de estas corridas no tienen valor
científico: sirven para probar la plataforma. Requiere los extras `graph` y `baselines`.

Uso:
    python scripts/build_api_fixtures.py
"""

from __future__ import annotations

import csv
import sys

from nutrigraphdt.api.demo import (
    FROZEN_RUNS_DIR,
    SYNTHETIC_ANIMALS,
    SYNTHETIC_FIRST_SEED,
)
from nutrigraphdt.api.engine import D1_FIXTURE_DIR, REPO_ROOT, d1_base, synthetic_cohort_base
from nutrigraphdt.api.fixtures import train_fixture_run

OUTPUT = FROZEN_RUNS_DIR
SYNTHETIC_TEST = 4
D1_TEST = ("SAMEA112904810",)


def main() -> int:
    synthetic = synthetic_cohort_base(SYNTHETIC_ANIMALS, first_seed=SYNTHETIC_FIRST_SEED)
    ids = synthetic.sample_ids
    run = train_fixture_run(
        synthetic,
        test_ids=ids[-SYNTHETIC_TEST:],
        pens={s: s for s in ids},
        diets={s: "synthetic" for s in ids},
        days={s: "synthetic" for s in ids},
        output_dir=OUTPUT / "synthetic",
    )
    print(f"Corrida sintética: {run.relative_to(REPO_ROOT).as_posix()}")

    with (D1_FIXTURE_DIR / "metadata.tsv").open(encoding="utf-8", newline="") as handle:
        rows = {row["sample_id"]: row for row in csv.DictReader(handle, delimiter="\t")}
    real = d1_base()
    run = train_fixture_run(
        real,
        test_ids=D1_TEST,
        pens={s: rows[s]["pen_code"] for s in real.sample_ids},
        diets={s: "d1_fixture" for s in real.sample_ids},
        days={s: rows[s]["sampling_day"] for s in real.sample_ids},
        output_dir=OUTPUT / "d1_fixture",
    )
    print(f"Corrida del fixture de D1: {run.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
