"""Verifica que los ejemplos publicados en la guía de uso del dataset sintético funcionen (DS-07).

Ejecuta los scripts documentados en `docs/synthetic-dataset-usage.md` como procesos
independientes y los fragmentos Python de esa guía tal como están escritos, para que la
documentación no quede desalineada con la interfaz pública.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
USAGE_DOC = REPO_ROOT / "docs" / "synthetic-dataset-usage.md"
GENERATE_SCRIPT = REPO_ROOT / "scripts" / "generate_synthetic_dataset.py"
EXPLORE_SCRIPT = REPO_ROOT / "scripts" / "explore_synthetic_dataset.py"


def _run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _python_blocks(markdown: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", markdown, flags=re.DOTALL)


def test_generate_then_explore_scenarios(tmp_path: Path) -> None:
    output = tmp_path / "v1"

    generated = _run(GENERATE_SCRIPT, "--output", output)
    assert generated.returncode == 0, generated.stderr
    assert "instancias: 2  nodos: 64  aristas: 156" in generated.stdout

    explored = _run(EXPLORE_SCRIPT, "--input", output)
    assert explored.returncode == 0, explored.stderr
    assert "dataset_id: synthetic-scenarios-v1" in explored.stdout
    assert "is_synthetic: True  random_seed: 42" in explored.stdout
    assert "[synthetic:scenario:basal:0001] scenario_id=basal" in explored.stdout
    assert "[synthetic:scenario:intervened:0001] scenario_id=intervention" in explored.stdout
    assert "crude_protein: 215.0 -> 270.0 g/kg [sintético]" in explored.stdout


def test_generate_with_seed_then_explore(tmp_path: Path) -> None:
    output = tmp_path / "seed-7"

    generated = _run(GENERATE_SCRIPT, "--seed", "7", "--output", output)
    assert generated.returncode == 0, generated.stderr
    assert "instancias: 1  nodos: 32  aristas: 75" in generated.stdout

    explored = _run(EXPLORE_SCRIPT, "--input", output)
    assert explored.returncode == 0, explored.stderr
    assert "random_seed: 7" in explored.stdout
    assert "Componentes de dieta que difieren" not in explored.stdout


def test_generate_refuses_to_overwrite_without_flag(tmp_path: Path) -> None:
    output = tmp_path / "v1"
    assert _run(GENERATE_SCRIPT, "--output", output).returncode == 0

    repeated = _run(GENERATE_SCRIPT, "--output", output)
    assert repeated.returncode != 0
    assert "--overwrite" in repeated.stderr

    assert _run(GENERATE_SCRIPT, "--output", output, "--overwrite").returncode == 0


def test_explore_reports_missing_dataset(tmp_path: Path) -> None:
    explored = _run(EXPLORE_SCRIPT, "--input", tmp_path / "missing")
    assert explored.returncode != 0
    assert "python scripts/generate_synthetic_dataset.py" in explored.stderr


@pytest.mark.parametrize("index", range(len(_python_blocks(USAGE_DOC.read_text("utf-8")))))
def test_usage_doc_python_snippet_runs(
    index: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    snippet = _python_blocks(USAGE_DOC.read_text("utf-8"))[index]
    exec(compile(snippet, f"{USAGE_DOC.name}[python block {index}]", "exec"), {})
    assert (tmp_path / "artifacts" / "synthetic").is_dir()
