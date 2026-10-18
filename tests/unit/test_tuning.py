"""Tests de la búsqueda de hiperparámetros y la variabilidad por semilla (A45-5, #105).

El entrenamiento se reemplaza por funciones deterministas, así que no requieren entrenar.
"""

from __future__ import annotations

import csv
import io
import json
import math

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("yaml")

from nutrigraphdt.models.gnn import ModelConfigError, parse_model_config  # noqa: E402
from nutrigraphdt.models.gnn.factory import GNNModelConfig  # noqa: E402
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow  # noqa: E402
from nutrigraphdt.models.training.tuning import (  # noqa: E402
    DEFAULT_SEEDS,
    INITIAL,
    SELECTED,
    RunOutcome,
    grid_configs,
    grid_to_csv,
    outcome_from_report,
    run_tuning,
    seed_runs_to_csv,
    select_best,
    selection_to_dict,
    summarize,
    summary_to_csv,
    summary_to_markdown,
    with_capacity,
)

HOMO = parse_model_config({"variant": "homo_sage"})
HETERO = parse_model_config({"variant": "hetero_sage"})
GAT = parse_model_config({"variant": "hetero_gat", "heads": 4})
INITIAL_CONFIGS: dict[str, GNNModelConfig] = {
    "homo_sage": HOMO,
    "hetero_sage": HETERO,
    "hetero_gat": GAT,
}


def _outcome(
    config: GNNModelConfig,
    seed: int,
    *,
    val: float,
    test: float = 1.0,
    run_id: str | None = None,
) -> RunOutcome:
    return RunOutcome(
        model_config=config,
        seed=seed,
        run_id=run_id or f"{config.variant}_h{config.hidden_channels}_l{config.num_layers}_s{seed}",
        averages={
            ("val", "rmse"): val,
            ("val", "mae"): val / 2,
            ("val", "r2"): 0.1,
            ("test", "rmse"): test,
            ("test", "mae"): test / 2,
            ("test", "r2"): 0.2,
        },
    )


def _fake_train(calls: list[tuple[str, int, int, int]]):  # type: ignore[no-untyped-def]
    """RMSE de val mínimo en 128×1; el de test es mínimo en la combinación opuesta."""

    def train(config: GNNModelConfig, seed: int) -> RunOutcome:
        hidden, layers = config.hidden_channels, config.num_layers
        calls.append((config.variant, hidden, layers, seed))
        val = 10.0 + abs(hidden - 128) / 32 + (layers - 1) + seed / 1000
        test = 10.0 - abs(hidden - 128) / 32 - (layers - 1)
        return _outcome(config, seed, val=val, test=test)

    return train


# ---------------------------------------------------------------------------
# Grilla
# ---------------------------------------------------------------------------


class TestGrid:
    def test_default_grid_is_the_design_range(self) -> None:
        configs = grid_configs(HOMO)
        assert [(c.hidden_channels, c.num_layers) for c in configs] == [
            (32, 1),
            (32, 2),
            (32, 3),
            (64, 1),
            (64, 2),
            (64, 3),
            (128, 1),
            (128, 2),
            (128, 3),
        ]

    def test_other_fields_are_kept(self) -> None:
        changed = with_capacity(GAT, 128, 3)
        assert changed.model_dump() == {**GAT.model_dump(), "hidden_channels": 128, "num_layers": 3}

    def test_invalid_combination_is_rejected_like_a_yaml(self) -> None:
        with pytest.raises(ModelConfigError, match="divisible"):
            with_capacity(GAT, 30, 2)

    @pytest.mark.parametrize("values", [(), (32, 32), (0,), (True,)])
    def test_invalid_values(self, values: tuple[int, ...]) -> None:
        with pytest.raises(ValueError, match="hidden_channels"):
            grid_configs(HOMO, hidden_channels=values)


# ---------------------------------------------------------------------------
# Selección
# ---------------------------------------------------------------------------


class TestSelectBest:
    def test_lowest_val_rmse(self) -> None:
        candidates = [
            _outcome(with_capacity(HOMO, 32, 1), 42, val=9.0),
            _outcome(with_capacity(HOMO, 64, 2), 42, val=8.0),
            _outcome(with_capacity(HOMO, 128, 3), 42, val=8.5),
        ]
        assert select_best(candidates) is candidates[1]

    def test_test_metrics_do_not_change_the_choice(self) -> None:
        base = [
            _outcome(with_capacity(HOMO, 32, 1), 42, val=9.0, test=1.0),
            _outcome(with_capacity(HOMO, 64, 2), 42, val=8.0, test=100.0),
        ]
        flipped = [
            _outcome(with_capacity(HOMO, 32, 1), 42, val=9.0, test=100.0),
            _outcome(with_capacity(HOMO, 64, 2), 42, val=8.0, test=1.0),
        ]
        assert select_best(base).hidden_channels == select_best(flipped).hidden_channels == 64

    def test_only_val_is_read(self) -> None:
        # Sin métricas de test la selección funciona igual.
        no_test = RunOutcome(HOMO, 42, "a", {("val", "rmse"): 1.0})
        assert select_best([no_test]) is no_test

    def test_tie_prefers_the_smaller_model(self) -> None:
        candidates = [
            _outcome(with_capacity(HOMO, 128, 1), 42, val=8.0),
            _outcome(with_capacity(HOMO, 64, 3), 42, val=8.0),
            _outcome(with_capacity(HOMO, 64, 2), 42, val=8.0),
        ]
        chosen = select_best(candidates)
        assert (chosen.hidden_channels, chosen.num_layers) == (64, 2)

    def test_missing_val_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="sin RMSE promedio de val"):
            select_best([RunOutcome(HOMO, 42, "a", {("test", "rmse"): 1.0})])

    def test_no_candidates(self) -> None:
        with pytest.raises(ValueError, match="No hay corridas"):
            select_best([])


# ---------------------------------------------------------------------------
# Flujo completo
# ---------------------------------------------------------------------------


class TestRunTuning:
    def test_selects_with_val_and_repeats_with_seeds(self) -> None:
        calls: list[tuple[str, int, int, int]] = []
        result = run_tuning(INITIAL_CONFIGS, "homo_sage", _fake_train(calls))
        assert (result.selected.hidden_channels, result.selected.num_layers) == (128, 1)
        assert result.grid_seed == DEFAULT_SEEDS[0]
        assert len(result.grid) == 9
        assert all(o.seed == DEFAULT_SEEDS[0] for o in result.grid)
        assert set(result.seed_runs) == {
            ("homo_sage", INITIAL),
            ("hetero_sage", INITIAL),
            ("hetero_gat", INITIAL),
            ("homo_sage", SELECTED),
        }
        for outcomes in result.seed_runs.values():
            assert [o.seed for o in outcomes] == list(DEFAULT_SEEDS)

    def test_each_configuration_and_seed_is_trained_once(self) -> None:
        calls: list[tuple[str, int, int, int]] = []
        run_tuning(INITIAL_CONFIGS, "homo_sage", _fake_train(calls))
        assert len(calls) == len(set(calls))
        # 9 de la grilla + 3 variantes × 5 semillas + 5 de la elegida, menos lo repetido:
        # homo_sage 64×2 y 128×1 con la semilla de la grilla ya estaban entrenadas.
        assert len(calls) == 9 + 15 + 5 - 2

    def test_selected_equal_to_initial_is_not_retrained(self) -> None:
        calls: list[tuple[str, int, int, int]] = []

        def prefers_initial(config: GNNModelConfig, seed: int) -> RunOutcome:
            calls.append((config.variant, config.hidden_channels, config.num_layers, seed))
            best = (config.hidden_channels, config.num_layers) == (64, 2)
            return _outcome(config, seed, val=1.0 if best else 2.0)

        result = run_tuning({"homo_sage": HOMO}, "homo_sage", prefers_initial, seeds=(1, 2))
        assert result.seed_runs[("homo_sage", SELECTED)] == result.seed_runs[("homo_sage", INITIAL)]
        assert len(calls) == 9 + 1  # la semilla 2 de 64×2 es la única fuera de la grilla

    def test_custom_grid_and_grid_seed(self) -> None:
        calls: list[tuple[str, int, int, int]] = []
        result = run_tuning(
            {"homo_sage": HOMO},
            "homo_sage",
            _fake_train(calls),
            hidden_channels=(32, 64),
            num_layers=(1,),
            seeds=(7, 8),
            grid_seed=99,
        )
        assert [(o.hidden_channels, o.num_layers, o.seed) for o in result.grid] == [
            (32, 1, 99),
            (64, 1, 99),
        ]

    def test_variant_without_initial_configuration(self) -> None:
        with pytest.raises(ValueError, match="configuración inicial"):
            run_tuning({"homo_sage": HOMO}, "hetero_gat", _fake_train([]))

    @pytest.mark.parametrize("seeds", [(), (1, 1), (-1,)])
    def test_invalid_seeds(self, seeds: tuple[int, ...]) -> None:
        with pytest.raises(ValueError, match="seeds"):
            run_tuning({"homo_sage": HOMO}, "homo_sage", _fake_train([]), seeds=seeds)


# ---------------------------------------------------------------------------
# Resumen y salidas
# ---------------------------------------------------------------------------


class TestSummary:
    def test_mean_and_sample_std(self) -> None:
        config = with_capacity(HOMO, 64, 2)
        runs = {
            ("homo_sage", INITIAL): [_outcome(config, s, val=v) for s, v in [(1, 1.0), (2, 3.0)]]
        }
        rows = {(r.split, r.metric): r for r in summarize(runs)}
        assert rows[("val", "rmse")].mean == pytest.approx(2.0)
        assert rows[("val", "rmse")].std == pytest.approx(math.sqrt(2.0))
        assert rows[("val", "rmse")].n == 2
        assert rows[("test", "r2")].mean == pytest.approx(0.2)

    def test_single_seed_has_no_std(self) -> None:
        runs = {("homo_sage", INITIAL): [_outcome(HOMO, 1, val=1.0)]}
        assert all(math.isnan(r.std) for r in summarize(runs))

    def test_outcome_from_report(self) -> None:
        report = EvaluationReport(
            rows=(
                MetricRow("homo_sage", "rmse", {"acetate": 1.0}, 2.5, split="val"),
                MetricRow("homo_sage", "rmse", {"acetate": 1.0}, 3.5, split="test"),
                MetricRow("other", "rmse", {"acetate": 1.0}, 9.9, split="val"),
                MetricRow("homo_sage", "mae", {"acetate": 1.0}, 1.0),
            )
        )
        outcome = outcome_from_report(report, model_config=HOMO, seed=1, run_id="x")
        assert dict(outcome.averages) == {("val", "rmse"): 2.5, ("test", "rmse"): 3.5}


class TestOutputs:
    @pytest.fixture
    def result(self):  # type: ignore[no-untyped-def]
        return run_tuning(INITIAL_CONFIGS, "homo_sage", _fake_train([]), seeds=(1, 2))

    def test_grid_csv_has_only_val_metrics(self, result) -> None:  # type: ignore[no-untyped-def]
        rows = list(csv.DictReader(io.StringIO(grid_to_csv(result.grid))))
        assert len(rows) == 9
        assert not [name for name in rows[0] if name.startswith("test")]
        assert {name for name in rows[0] if name.startswith("val_")} == {
            "val_rmse",
            "val_mae",
            "val_r2",
        }

    def test_selection_record(self, result) -> None:  # type: ignore[no-untyped-def]
        record = selection_to_dict(result)
        text = json.dumps(record)
        assert "test_rmse" not in text and "test_mae" not in text
        assert record["selection"] == {
            "split": "val",
            "metric": "rmse_average",
            "rule": "mínimo; empate: menos hidden_channels y luego menos num_layers",
            "test_used": False,
        }
        assert len(record["candidates"]) == 9
        best = min(record["candidates"], key=lambda c: c["val_rmse_average"])
        assert best["run_id"] == record["selected"]["run_id"]
        assert record["selected"]["model_config"]["hidden_channels"] == 128

    def test_seed_runs_and_summary_csv(self, result) -> None:  # type: ignore[no-untyped-def]
        seeds = list(csv.DictReader(io.StringIO(seed_runs_to_csv(result.seed_runs))))
        assert len(seeds) == 4 * 2
        assert {"val_rmse", "test_rmse"} <= set(seeds[0])
        summary = list(csv.DictReader(io.StringIO(summary_to_csv(result.summary))))
        assert len(summary) == 4 * 2 * 3  # (variante, configuración) × subconjunto × métrica

    def test_markdown_table(self, result) -> None:  # type: ignore[no-untyped-def]
        table = summary_to_markdown(result.summary)
        lines = table.splitlines()
        assert len(lines) == 2 + 4
        assert "| homo_sage | elegida | 128 × 1 |" in table
        assert "±" in table
