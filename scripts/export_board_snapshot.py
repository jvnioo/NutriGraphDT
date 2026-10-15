"""Exporta una foto del avance del proyecto para la demo (`scripts/demo_app.py`).

Lee las Issues y los PR del repositorio con GitHub CLI (`gh`, ya autenticado) y cuenta los
tests con `pytest --collect-only`. Escribe `reports/progress/board_snapshot.json`, que la página
"Proceso" muestra sin necesitar credenciales ni red durante la presentación. No guarda cuerpos
de Issues, nombres de personas ni datos privados: solo número, título, estado, etiquetas y
fechas.

Uso:

    python scripts/export_board_snapshot.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "progress" / "board_snapshot.json"
ACTIVITY = re.compile(r"^A\d{2}$")


def _gh(*args: str) -> Any:
    completed = subprocess.run(
        ["gh", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout)


def _test_count() -> int | None:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"(\d+) tests? collected", completed.stdout)
    return int(match.group(1)) if match else None


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    issues = _gh(
        "issue",
        "list",
        "--state",
        "all",
        "--limit",
        "500",
        "--json",
        "number,title,state,labels,createdAt,closedAt",
    )
    pulls = _gh("pr", "list", "--state", "merged", "--limit", "500", "--json", "number,mergedAt")
    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tests_collected": _test_count(),
        "merged_pull_requests": len(pulls),
        "issues": [
            {
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"].lower(),
                "activity": next(
                    (label["name"] for label in issue["labels"] if ACTIVITY.match(label["name"])),
                    None,
                ),
                "labels": sorted(label["name"] for label in issue["labels"]),
                "created_at": issue["createdAt"],
                "closed_at": issue["closedAt"],
            }
            for issue in sorted(issues, key=lambda item: item["number"])
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    closed = sum(issue["state"] == "closed" for issue in snapshot["issues"])
    print(
        f"{len(snapshot['issues'])} issues ({closed} cerradas), {len(pulls)} PR fusionados, "
        f"{snapshot['tests_collected']} tests. Archivo: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
