"""Tests de los componentes compartidos de las GNN (A41-5, #81). Requiere el extra `graph`.

Encoder por tipo de nodo, residual, lectura por grafo y cabeza de regresión, probados de forma
aislada con tensores pequeños. La integración con grafos reales está en `test_gnn_base.py`.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.models.gnn import (  # noqa: E402
    EXCLUDED_FROM_READOUT,
    READOUT_NODE_TYPES,
    NodeTypeEncoder,
    ResidualUpdate,
    ScfaRegressionHead,
    infer_in_channels,
    mean_readout,
)
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS  # noqa: E402

HIDDEN = 4


def _inputs() -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    """Tipos con 2 y 1 columnas y un tipo sin columnas, como `diet` en D1."""
    generator = torch.Generator().manual_seed(0)
    x_dict = {
        "taxon": torch.rand(5, 2, generator=generator),
        "host": torch.rand(1, 1, generator=generator),
        "diet": torch.zeros(1, 0),
    }
    taxon_mask = torch.zeros(5, 2, dtype=torch.bool)
    taxon_mask[0, 1] = taxon_mask[2, 0] = True
    mask_dict = {
        "taxon": taxon_mask,
        "host": torch.zeros(1, 1, dtype=torch.bool),
        "diet": torch.zeros(1, 0, dtype=torch.bool),
    }
    return x_dict, mask_dict


def _encoder() -> NodeTypeEncoder:
    torch.manual_seed(0)
    return NodeTypeEncoder({"taxon": 2, "host": 1, "diet": 0}, HIDDEN)


def _h_dict(sizes: dict[str, int], seed: int = 0) -> dict[str, torch.Tensor]:
    generator = torch.Generator().manual_seed(seed)
    return {t: torch.randn(n, HIDDEN, generator=generator) for t, n in sizes.items()}


def _no_mask(*shape: int) -> torch.Tensor:
    return torch.zeros(*shape, dtype=torch.bool)


# ---------------------------------------------------------------------------
# NodeTypeEncoder
# ---------------------------------------------------------------------------


class TestNodeTypeEncoder:
    def test_output_shape_per_type(self) -> None:
        x_dict, mask_dict = _inputs()
        output = _encoder()(x_dict, mask_dict)
        assert {t: tuple(h.shape) for t, h in output.items()} == {
            "taxon": (5, HIDDEN),
            "host": (1, HIDDEN),
            "diet": (1, HIDDEN),
        }

    def test_linear_layer_takes_twice_the_columns(self) -> None:
        encoder = _encoder()
        assert encoder.projections["taxon"].in_features == 4
        assert encoder.projections["host"].in_features == 2
        assert "diet" not in encoder.projections

    def test_projection_is_linear_on_features_and_mask(self) -> None:
        x_dict, mask_dict = _inputs()
        encoder = _encoder()
        layer = encoder.projections["taxon"]
        features = torch.cat([x_dict["taxon"], mask_dict["taxon"].float()], dim=-1)
        expected = features @ layer.weight.T + layer.bias
        torch.testing.assert_close(encoder(x_dict, mask_dict)["taxon"], expected)

    def test_missing_zero_differs_from_measured_zero(self) -> None:
        encoder = _encoder()
        x = {"host": torch.zeros(1, 1)}
        measured = encoder(x, {"host": torch.tensor([[False]])})["host"]
        missing = encoder(x, {"host": torch.tensor([[True]])})["host"]
        assert not torch.allclose(measured, missing)

    def test_type_without_columns_uses_one_learned_vector(self) -> None:
        encoder = _encoder()
        output = encoder({"diet": torch.zeros(3, 0)}, {"diet": _no_mask(3, 0)})
        for row in output["diet"]:
            torch.testing.assert_close(row, encoder.type_embeddings["diet"])

    def test_type_without_columns_does_not_need_mask(self) -> None:
        output = _encoder()({"diet": torch.zeros(2, 0)}, {})
        assert tuple(output["diet"].shape) == (2, HIDDEN)

    def test_zero_nodes(self) -> None:
        output = _encoder()({"taxon": torch.zeros(0, 2)}, {"taxon": _no_mask(0, 2)})
        assert tuple(output["taxon"].shape) == (0, HIDDEN)

    def test_declared_type_may_be_absent(self) -> None:
        output = _encoder()({"host": torch.ones(1, 1)}, {"host": _no_mask(1, 1)})
        assert set(output) == {"host"}

    def test_gradient_reaches_every_parameter(self) -> None:
        x_dict, mask_dict = _inputs()
        encoder = _encoder()
        loss = torch.stack([h.sum() for h in encoder(x_dict, mask_dict).values()]).sum()
        loss.backward()
        for name, parameter in encoder.named_parameters():
            assert parameter.grad is not None, name
            assert parameter.grad.abs().sum() > 0, name

    def test_same_seed_same_parameters(self) -> None:
        first, second = _encoder(), _encoder()
        for a, b in zip(first.parameters(), second.parameters(), strict=True):
            torch.testing.assert_close(a, b)

    def test_unknown_type_is_rejected(self) -> None:
        with pytest.raises(KeyError, match="no declarado"):
            _encoder()({"function": torch.zeros(1, 2)}, {})

    def test_wrong_number_of_columns_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"forma \[N, 2\]"):
            _encoder()({"taxon": torch.zeros(3, 3)}, {"taxon": _no_mask(3, 3)})

    @pytest.mark.parametrize("masks", [{}, {"taxon": torch.zeros(3, 1, dtype=torch.bool)}])
    def test_missing_or_misshaped_mask_is_rejected(self, masks: dict[str, torch.Tensor]) -> None:
        with pytest.raises(ValueError, match="missing_mask"):
            _encoder()({"taxon": torch.zeros(3, 2)}, masks)

    @pytest.mark.parametrize("hidden", [0, -1, True])
    def test_invalid_hidden_channels(self, hidden: int) -> None:
        with pytest.raises(ValueError, match="hidden_channels"):
            NodeTypeEncoder({"taxon": 1}, hidden)

    @pytest.mark.parametrize("channels", [-1, True, 1.5])
    def test_invalid_in_channels(self, channels: int) -> None:
        with pytest.raises(ValueError, match="in_channels"):
            NodeTypeEncoder({"taxon": channels}, HIDDEN)

    def test_empty_in_channels(self) -> None:
        with pytest.raises(ValueError, match="al menos un tipo"):
            NodeTypeEncoder({}, HIDDEN)

    def test_infer_in_channels(self) -> None:
        x_dict, _ = _inputs()
        assert infer_in_channels(x_dict) == {"taxon": 2, "host": 1, "diet": 0}
        with pytest.raises(ValueError, match="2 dimensiones"):
            infer_in_channels({"taxon": torch.zeros(3)})


# ---------------------------------------------------------------------------
# ResidualUpdate
# ---------------------------------------------------------------------------


class TestResidualUpdate:
    def test_adds_activated_update(self) -> None:
        h_dict = _h_dict({"host": 2})
        update = _h_dict({"host": 2}, seed=1)
        output = ResidualUpdate(dropout=0.0)(h_dict, update)
        torch.testing.assert_close(output["host"], h_dict["host"] + torch.relu(update["host"]))

    def test_type_without_update_keeps_its_embedding(self) -> None:
        h_dict = _h_dict({"taxon": 3, "host": 1})
        output = ResidualUpdate()(h_dict, _h_dict({"host": 1}, seed=1))
        assert output["taxon"] is h_dict["taxon"]
        assert set(output) == {"taxon", "host"}

    def test_dropout_only_in_training(self) -> None:
        residual = ResidualUpdate(dropout=0.5)
        h_dict = {"host": torch.zeros(1, 1000)}
        update = {"host": torch.ones(1, 1000)}
        residual.train()
        assert (residual(h_dict, update)["host"] == 0).any()
        residual.eval()
        torch.testing.assert_close(residual(h_dict, update)["host"], update["host"])

    def test_unknown_type_is_rejected(self) -> None:
        with pytest.raises(KeyError, match="sin embedding previo"):
            ResidualUpdate()(_h_dict({"host": 1}), _h_dict({"taxon": 1}))

    def test_shape_mismatch_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="actualización"):
            ResidualUpdate()(_h_dict({"host": 2}), _h_dict({"host": 1}))

    @pytest.mark.parametrize("dropout", [-0.1, 1.0, True])
    def test_invalid_dropout(self, dropout: float) -> None:
        with pytest.raises(ValueError, match="dropout"):
            ResidualUpdate(dropout)


# ---------------------------------------------------------------------------
# mean_readout
# ---------------------------------------------------------------------------


class TestMeanReadout:
    def test_readout_types_follow_node_types_order(self) -> None:
        assert READOUT_NODE_TYPES == ("diet", "additive", "substrate", "taxon", "function", "host")
        assert frozenset({"metabolite", "phenotype"}) == EXCLUDED_FROM_READOUT

    def test_single_graph_is_concatenation_of_means(self) -> None:
        h_dict = _h_dict({"taxon": 5, "host": 1, "diet": 1})
        output = mean_readout(h_dict, None, 1, HIDDEN)
        zeros = torch.zeros(HIDDEN)
        expected = torch.cat(
            [
                h_dict["diet"].mean(0),
                zeros,  # additive
                zeros,  # substrate
                h_dict["taxon"].mean(0),
                zeros,  # function
                h_dict["host"].mean(0),
            ]
        ).unsqueeze(0)
        torch.testing.assert_close(output, expected)

    def test_dimension_is_six_hidden_on_any_dataset(self) -> None:
        output = mean_readout(_h_dict({"host": 1}), None, 1, HIDDEN)
        assert tuple(output.shape) == (1, 6 * HIDDEN)

    def test_metabolite_and_phenotype_are_ignored(self) -> None:
        h_dict = _h_dict({"taxon": 3, "host": 1})
        base = mean_readout(h_dict, None, 1, HIDDEN)
        with_targets = {**h_dict, **_h_dict({"metabolite": 8, "phenotype": 2}, seed=5)}
        torch.testing.assert_close(mean_readout(with_targets, None, 1, HIDDEN), base)

    def test_batch_equals_graph_by_graph(self) -> None:
        first = _h_dict({"taxon": 3, "host": 1}, seed=1)
        second = _h_dict({"taxon": 2, "host": 1}, seed=2)
        batched = {t: torch.cat([first[t], second[t]]) for t in first}
        batch_dict = {"taxon": torch.tensor([0, 0, 0, 1, 1]), "host": torch.tensor([0, 1])}
        output = mean_readout(batched, batch_dict, 2, HIDDEN)
        torch.testing.assert_close(output[0], mean_readout(first, None, 1, HIDDEN)[0])
        torch.testing.assert_close(output[1], mean_readout(second, None, 1, HIDDEN)[0])

    def test_trailing_graph_without_nodes_of_a_type(self) -> None:
        h_dict = _h_dict({"taxon": 2, "host": 2})
        batch_dict = {"taxon": torch.tensor([0, 0]), "host": torch.tensor([0, 1])}
        output = mean_readout(h_dict, batch_dict, 2, HIDDEN)
        assert tuple(output.shape) == (2, 6 * HIDDEN)
        taxon = slice(3 * HIDDEN, 4 * HIDDEN)
        torch.testing.assert_close(output[1, taxon], torch.zeros(HIDDEN))

    def test_invariant_to_node_order(self) -> None:
        h_dict = _h_dict({"taxon": 6})
        permuted = {"taxon": h_dict["taxon"][torch.randperm(6)]}
        torch.testing.assert_close(
            mean_readout(permuted, None, 1, HIDDEN), mean_readout(h_dict, None, 1, HIDDEN)
        )

    def test_inconsistent_batch_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="batch_dict"):
            mean_readout(_h_dict({"taxon": 3}), {"taxon": torch.tensor([0, 1])}, 2, HIDDEN)

    def test_wrong_hidden_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="forma"):
            mean_readout({"taxon": torch.zeros(2, HIDDEN + 1)}, None, 1, HIDDEN)

    def test_invalid_num_graphs(self) -> None:
        with pytest.raises(ValueError, match="num_graphs"):
            mean_readout(_h_dict({"taxon": 1}), None, 0, HIDDEN)


# ---------------------------------------------------------------------------
# ScfaRegressionHead
# ---------------------------------------------------------------------------


class TestScfaRegressionHead:
    def test_output_shape_and_targets(self) -> None:
        head = ScfaRegressionHead(HIDDEN)
        assert head.targets == DEFAULT_SCFA_TARGETS == ("acetate", "propionate", "butyrate")
        assert tuple(head(torch.randn(7, 6 * HIDDEN)).shape) == (7, 3)

    def test_mlp_structure(self) -> None:
        head = ScfaRegressionHead(HIDDEN, dropout=0.2)
        first, activation, dropout, last = head.mlp
        assert (first.in_features, first.out_features) == (6 * HIDDEN, HIDDEN)
        assert isinstance(activation, torch.nn.ReLU)
        assert dropout.p == pytest.approx(0.2)
        assert (last.in_features, last.out_features) == (HIDDEN, 3)

    def test_no_final_activation(self) -> None:
        head = ScfaRegressionHead(HIDDEN)
        torch.nn.init.zeros_(head.mlp[-1].weight)
        torch.nn.init.constant_(head.mlp[-1].bias, -5.0)
        assert (head(torch.randn(2, 6 * HIDDEN)) < 0).all()

    def test_wrong_input_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="lectura"):
            ScfaRegressionHead(HIDDEN)(torch.randn(2, HIDDEN))

    @pytest.mark.parametrize("targets", [(), ("acetate", "acetate"), "acetate"])
    def test_invalid_targets(self, targets: tuple[str, ...]) -> None:
        with pytest.raises(ValueError, match="targets"):
            ScfaRegressionHead(HIDDEN, targets=targets)

    def test_invalid_dropout(self) -> None:
        with pytest.raises(ValueError, match="dropout"):
            ScfaRegressionHead(HIDDEN, dropout=1.0)
