"""`scripts/explain_synthetic.py` escribe una explicación válida del contrato vigente.

Requiere el extra `graph`.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.explainability import (  # noqa: E402
    EXPLANATION_FORMAT_VERSION,
    validate_explanation,
)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "explain_synthetic.py"


def test_script_writes_a_valid_explanation(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("explain_synthetic", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = tmp_path / "explanation.json"
    assert module.main(["--epochs", "2", "--top-k", "3", "--output", str(output)]) == 0
    explanation = validate_explanation(json.loads(output.read_text(encoding="utf-8")))
    assert explanation.format_version == EXPLANATION_FORMAT_VERSION
    assert explanation.subgraph.k == 3
    assert not any(e.relation_type.startswith("rev_") for e in explanation.importance.edges)
