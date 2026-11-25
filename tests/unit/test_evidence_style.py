"""Estilo de las aristas del subgrafo explicativo por estado de evidencia (C-03, #243)."""

from __future__ import annotations

import pytest

from nutrigraphdt.explainability.contract import EVIDENCE_METHOD_STATUS
from nutrigraphdt.explainability.style import (
    EVIDENCE_STYLES,
    HYPOTHETICAL_LABEL,
    evidence_legend,
    evidence_style,
)
from nutrigraphdt.graph.contracts import _ALLOWED_EVIDENCE_STATUSES


def test_one_style_per_ds01_status() -> None:
    assert set(EVIDENCE_STYLES) == set(_ALLOWED_EVIDENCE_STATUSES)
    assert set(EVIDENCE_METHOD_STATUS.values()) <= set(EVIDENCE_STYLES)
    assert [style.status for style in evidence_legend()] == list(EVIDENCE_STYLES)


def test_states_are_distinguishable_without_color() -> None:
    styles = evidence_legend()
    assert len({style.dash for style in styles}) == len(styles)
    assert len({style.color for style in styles}) == len(styles)
    assert len({style.label for style in styles}) == len(styles)


def test_hypothetical_label() -> None:
    assert HYPOTHETICAL_LABEL == "hipotética: sin respaldo empírico"
    assert evidence_style("hypothetical").label == HYPOTHETICAL_LABEL


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="DS-01"):
        evidence_style("provisional")
