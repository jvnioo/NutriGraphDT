"""Corre la suite E2E de la Web App y deja su registro versionado (A105-P4, #342).

Ejecuta `pytest -m e2e` con un reporte JUnit temporal y escribe en `--output` (por defecto
`reports/e2e/`):

- `results.json`: commit, entorno, totales y el resultado de cada caso;
- `report.md`: el mismo contenido para el informe, con la tabla de casos de
  `docs/process/e2e-cases.md` y los defectos registrados allí.

Las cifras salen de la ejecución; no se escriben a mano. Requiere los extras `graph`, `baselines`
y `demo`. Uso:

    python scripts/report_e2e.py
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "e2e"
CASE = re.compile(r"test_e2e_(\d+)_")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def _versions() -> dict[str, str]:
    found = {"python": platform.python_version(), "platform": platform.platform()}
    for name in ("torch", "torch_geometric", "streamlit", "plotly", "pydantic"):
        try:
            module = __import__(name)
            found[name] = str(getattr(module, "__version__", "?"))
        except ImportError:
            found[name] = "no instalado"
    return found


def run_suite() -> tuple[list[dict[str, Any]], float, int]:
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "e2e.xml"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-m",
                "e2e",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit}",
                "tests/e2e",
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        root = ElementTree.parse(junit).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    assert suite is not None
    cases: list[dict[str, Any]] = []
    for case in suite.iter("testcase"):
        name = case.get("name", "")
        match = CASE.search(name)
        outcome = "passed"
        detail = ""
        for tag in ("failure", "error", "skipped"):
            element = case.find(tag)
            if element is not None:
                outcome = "failed" if tag != "skipped" else "skipped"
                detail = (element.get("message") or "").splitlines()[0][:200]
        cases.append(
            {
                "case": f"E2E-{match.group(1)}" if match else "?",
                "test": name,
                "outcome": outcome,
                "seconds": round(float(case.get("time", 0.0)), 2),
                "detail": detail,
            }
        )
    return cases, float(suite.get("time", 0.0)), completed.returncode


def write_report(cases: list[dict[str, Any]], seconds: float, output: Path) -> dict[str, Any]:
    totals = {o: sum(c["outcome"] == o for c in cases) for o in ("passed", "failed", "skipped")}
    record = {
        "format_version": "1.0.0",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": {"commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))},
        "environment": _versions(),
        "command": "pytest -m e2e tests/e2e",
        "seconds": round(seconds, 1),
        "totals": {"tests": len(cases), **totals},
        "cases": cases,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    by_case: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        by_case.setdefault(case["case"], []).append(case)
    lines = [
        "# Registro de la suite E2E de la Web App (A105-P4, #342)",
        "",
        "> **Datos sintéticos.** La suite recorre la app con la cohorte sintética y las corridas "
        "sintéticas congeladas. Comprueba el flujo y los contratos, no efectos biológicos.",
        "",
        f"- **Commit:** `{record['git']['commit']}`"
        + (" (con cambios sin commit)" if record["git"]["dirty"] else ""),
        f"- **Fecha:** {record['created_at']}",
        f"- **Comando:** `{record['command']}` ({record['seconds']} s)",
        "- **Entorno:** " + ", ".join(f"{k} {v}" for k, v in record["environment"].items()),
        f"- **Totales:** {len(cases)} pruebas; {totals['passed']} pasan, {totals['failed']} "
        f"fallan, {totals['skipped']} omitidas.",
        "",
        "## Casos",
        "",
        "| Caso | Pruebas | Pasan | Fallan | Detalle |",
        "|---|---:|---:|---:|---|",
    ]
    for name in sorted(by_case):
        group = by_case[name]
        failed = [c for c in group if c["outcome"] == "failed"]
        lines.append(
            f"| {name} | {len(group)} | {sum(c['outcome'] == 'passed' for c in group)} | "
            f"{len(failed)} | {'; '.join(c['detail'] for c in failed) or '—'} |"
        )
    lines += [
        "",
        "Qué prueba cada caso y los defectos encontrados y corregidos: "
        "[`docs/process/e2e-cases.md`](../../docs/process/e2e-cases.md).",
        "",
        "Regenerar: `python scripts/report_e2e.py`.",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    cases, seconds, code = run_suite()
    record = write_report(cases, seconds, args.output)
    print(f"E2E: {record['totals']} -> {args.output}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
