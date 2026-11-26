"""Registro de la suite E2E (A105-P4, #342): totales y tabla salen de los casos ejecutados."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_e2e.py"
spec = importlib.util.spec_from_file_location("report_e2e", SCRIPT)
assert spec is not None and spec.loader is not None
report_e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_e2e)


def test_report_counts_match_the_cases(tmp_path: Path) -> None:
    cases = [
        {
            "case": "E2E-01",
            "test": "test_e2e_01_x",
            "outcome": "passed",
            "seconds": 1.0,
            "detail": "",
        },
        {
            "case": "E2E-02",
            "test": "test_e2e_02_x[a]",
            "outcome": "passed",
            "seconds": 1.0,
            "detail": "",
        },
        {
            "case": "E2E-02",
            "test": "test_e2e_02_x[b]",
            "outcome": "failed",
            "seconds": 1.0,
            "detail": "boom",
        },
    ]
    record = report_e2e.write_report(cases, 3.0, tmp_path)

    assert record["totals"] == {"tests": 3, "passed": 2, "failed": 1, "skipped": 0}
    assert record["git"]["commit"]
    assert json.loads((tmp_path / "results.json").read_text(encoding="utf-8")) == record
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| E2E-02 | 2 | 1 | 1 | boom |" in text
    assert "3 pruebas; 2 pasan, 1 fallan" in text
