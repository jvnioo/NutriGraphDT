"""Registro de la revisión cruzada con Investigación (A55-P4, #158).

Hace verificable el criterio de la issue: ninguna observación sale de `pendiente` sin una
respuesta escrita enlazada, y mientras quede alguna pendiente los documentos revisados siguen
declarando que no tienen aprobación científica.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW = REPO_ROOT / "docs" / "models" / "explanations-protocol-review.md"
PROTOCOL = REPO_ROOT / "docs" / "models" / "constraints-evaluation-protocol.md"
STATES = {"pendiente", "resuelta", "limitación aceptada", "convertida en issue"}
COLUMNS = 8
RESPONSE_LINK = re.compile(
    r"https://github\.com/jvnioo/NutriGraphDT/issues/\d+#issuecomment-\d+"
    r"|docs/research/[^)]+\.md"
)


def _rows() -> list[list[str]]:
    rows = []
    for line in REVIEW.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| [PC]-\d{2} \|", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append(cells)
    return rows


def test_every_observation_has_all_columns_and_a_unique_id() -> None:
    rows = _rows()
    assert rows
    assert all(len(row) == COLUMNS for row in rows)
    ids = [row[0] for row in rows]
    assert len(ids) == len(set(ids))
    for prefix in ("P", "C"):
        numbers = [int(i[2:]) for i in ids if i.startswith(prefix)]
        assert numbers == list(range(1, len(numbers) + 1))


def test_states_are_valid_and_none_is_closed_without_a_written_response() -> None:
    for row in _rows():
        state, response = row[6].strip("`"), row[7]
        assert state in STATES, row[0]
        if state != "pendiente":
            assert RESPONSE_LINK.search(response), f"{row[0]} sin respuesta enlazada"
        if state == "convertida en issue":
            assert re.search(r"#\d+", response), f"{row[0]} sin Issue enlazado"


def test_documents_do_not_claim_approval_while_observations_are_pending() -> None:
    pending = [row for row in _rows() if row[6].strip("`") == "pendiente"]
    if not pending:
        return
    assert "respuesta de Investigación pendiente" in REVIEW.read_text(encoding="utf-8")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    assert "sin aprobación científica" in protocol
    assert "explanations-protocol-review.md" in protocol


def test_protocol_uses_the_sampling_days_of_the_cohort() -> None:
    """P-01: la cohorte de D1 tiene los días 7, 21 y 35."""
    from nutrigraphdt.data.covariates import HOST_COVARIATES_BY_NAME

    days = HOST_COVARIATES_BY_NAME["sampling_day"].vocabulary
    assert tuple(days) == ("7", "21", "35")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    assert "\\{7, 21, 35\\}" in protocol
    assert not re.search(r"día (14|28)\b", protocol)
    assert '"14"' not in protocol and '"28"' not in protocol


def test_review_is_linked_from_docs() -> None:
    index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "models/explanations-protocol-review.md" in index
