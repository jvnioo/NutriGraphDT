"""Configuración de entrega (A115-P2, #345): semillas coherentes y hash estable entre clones."""

from __future__ import annotations

import json
from pathlib import Path

from nutrigraphdt import delivery

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_delivery_seeds_match_the_configs_that_use_them() -> None:
    config = delivery.load_config()
    seeds = config["seeds"]
    assert config["cohort"]["first_seed"] == seeds["cohort_first_seed"]
    assert config["explanation"]["seed"] == seeds["explanation_seed"]
    for run in config["runs"].values():
        training = json.loads((REPO_ROOT / run["training_config"]).read_text(encoding="utf-8"))
        assert training["seed"] == seeds["training_seed"]
    from nutrigraphdt.api.engine import INTERVAL_SEED

    assert seeds["mc_dropout_seed"] == INTERVAL_SEED


def test_lock_file_pins_exact_versions() -> None:
    config = delivery.load_config()
    lines = (REPO_ROOT / config["lock_file"]).read_text(encoding="utf-8").splitlines()
    packages = [line for line in lines if line and not line.startswith(("#", "--"))]
    assert packages and all("==" in line for line in packages)
    names = {line.split("==")[0].lower() for line in packages}
    assert {"torch", "torch-geometric", "pydantic", "streamlit", "scikit-learn"} <= names


def test_config_hash_does_not_depend_on_line_endings(tmp_path: Path) -> None:
    text = (REPO_ROOT / "configs" / "delivery.json").read_bytes().replace(b"\r\n", b"\n")
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(text)
    crlf.write_bytes(text.replace(b"\n", b"\r\n"))
    assert delivery._sha256(lf) == delivery._sha256(crlf)
