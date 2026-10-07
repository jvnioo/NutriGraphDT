"""Reporte consolidado de integridad y efecto de las severidades (VG-07).

Implementa la tabla "Severidades" de `docs/graph/graph-integrity-rules.md`:

- `ERROR`: el grafo **no** se entrega al modelo. Un `ERROR` de nivel dataset (`graph_id = null`,
  por ejemplo MET-03) bloquea todas las instancias, porque indica que los archivos no son
  coherentes entre sí.
- `ADVERTENCIA`: el grafo se entrega; el hallazgo queda en el reporte para revisión humana.
- `INFO`: el grafo se entrega; el hallazgo solo se registra y se cuenta.

El reporte es estructural. No afirma validez biológica: un grafo entregable es coherente con el
contrato, no una representación confirmada del organismo.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from nutrigraphdt.data.synthetic.export import SCHEMA_VERSION
from nutrigraphdt.graph.validation.findings import Finding, Severity

RULES_VERSION: Final = "1.2.0"
"""Versión de `docs/graph/graph-integrity-rules.md` que implementan los validadores."""

REPORT_FORMAT_VERSION: Final = "1.0"
"""Versión de la estructura de `ValidationReport.to_dict()`."""

SCOPE_NOTE: Final = (
    "Validación estructural de integridad computacional. No afirma validez biológica, "
    "causalidad ni calidad de la evidencia."
)

_SEVERITY_ORDER: tuple[Severity, ...] = (Severity.ERROR, Severity.WARNING, Severity.INFO)


def _sort_key(finding: Finding) -> tuple[int, str, str]:
    """Primero los hallazgos de nivel dataset, luego por instancia y regla (orden estable)."""
    return (0 if finding.graph_id is None else 1, finding.graph_id or "", finding.rule_id)


@dataclass(frozen=True)
class ValidationReport:
    """Hallazgos de todas las reglas evaluadas sobre un dataset y sus grafos.

    `graph_ids` son las instancias evaluadas. `not_evaluated` indica, por familia de reglas o por
    instancia, qué no se evaluó y por qué: un reporte sin hallazgos solo cubre lo evaluado.
    """

    findings: tuple[Finding, ...]
    graph_ids: tuple[str, ...]
    evaluated: tuple[str, ...]
    not_evaluated: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(sorted(self.findings, key=_sort_key)))
        object.__setattr__(self, "graph_ids", tuple(sorted(set(self.graph_ids))))
        object.__setattr__(self, "not_evaluated", MappingProxyType(dict(self.not_evaluated)))

    def by_severity(self, severity: Severity) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.severity is severity)

    @property
    def errors(self) -> tuple[Finding, ...]:
        return self.by_severity(Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return self.by_severity(Severity.WARNING)

    @property
    def infos(self) -> tuple[Finding, ...]:
        return self.by_severity(Severity.INFO)

    @property
    def dataset_errors(self) -> tuple[Finding, ...]:
        """Errores de nivel dataset, que bloquean todas las instancias."""
        return tuple(finding for finding in self.errors if finding.graph_id is None)

    @property
    def is_valid(self) -> bool:
        """`True` si no hay ningún `ERROR`; las advertencias no invalidan."""
        return not self.errors

    def blocking_findings(self, graph_id: str) -> tuple[Finding, ...]:
        """Errores que impiden entregar la instancia al modelo."""
        return tuple(
            finding
            for finding in self.errors
            if finding.graph_id is None or finding.graph_id == graph_id
        )

    def is_deliverable(self, graph_id: str) -> bool:
        """Si la instancia puede entregarse al modelo según la tabla de severidades."""
        return graph_id in self.graph_ids and not self.blocking_findings(graph_id)

    @property
    def deliverable_graph_ids(self) -> tuple[str, ...]:
        return tuple(graph_id for graph_id in self.graph_ids if self.is_deliverable(graph_id))

    @property
    def blocked_graph_ids(self) -> tuple[str, ...]:
        return tuple(graph_id for graph_id in self.graph_ids if not self.is_deliverable(graph_id))

    def to_dict(self) -> dict[str, Any]:
        """Estructura estable y compatible con JSON (versión `REPORT_FORMAT_VERSION`)."""
        rules: dict[str, dict[str, Any]] = {}
        for finding in self.findings:
            entry = rules.setdefault(
                finding.rule_id, {"severity": finding.severity.value, "count": 0}
            )
            entry["count"] += 1
        graphs = {}
        for graph_id in self.graph_ids:
            own = [finding for finding in self.findings if finding.graph_id == graph_id]
            counts = Counter(finding.severity for finding in own)
            graphs[graph_id] = {
                "deliverable": self.is_deliverable(graph_id),
                **{severity.value: counts[severity] for severity in _SEVERITY_ORDER},
            }
        totals = Counter(finding.severity for finding in self.findings)
        return {
            "report_format": REPORT_FORMAT_VERSION,
            "rules_version": RULES_VERSION,
            "schema_version": SCHEMA_VERSION,
            "scope": SCOPE_NOTE,
            "status": "valid" if self.is_valid else "invalid",
            "summary": {severity.value: totals[severity] for severity in _SEVERITY_ORDER},
            "dataset_errors": len(self.dataset_errors),
            "graphs": graphs,
            "rules": dict(sorted(rules.items())),
            "evaluated": list(self.evaluated),
            "not_evaluated": dict(sorted(self.not_evaluated.items())),
            "findings": [finding.to_dict() for finding in self.findings],
        }


class GraphIntegrityError(ValueError):
    """Un grafo con hallazgos `ERROR` no puede entregarse al modelo."""

    def __init__(self, report: ValidationReport, graph_ids: Iterable[str]) -> None:
        self.report = report
        self.graph_ids = tuple(graph_ids)
        # Un error de nivel dataset bloquea varias instancias; se lista una vez. `Finding` no
        # es hasheable (su `location` es un diccionario), así que se compara por identidad.
        unique: list[Finding] = []
        seen: set[int] = set()
        for graph_id in self.graph_ids:
            for finding in report.blocking_findings(graph_id):
                if id(finding) not in seen:
                    seen.add(id(finding))
                    unique.append(finding)
        preview = "; ".join(f"{finding.rule_id}: {finding.message}" for finding in unique[:5])
        more = f" (y {len(unique) - 5} más)" if len(unique) > 5 else ""
        super().__init__(
            f"{len(self.graph_ids)} grafo(s) con errores de integridad: "
            f"{', '.join(self.graph_ids)}. {preview}{more}"
        )


def require_deliverable(report: ValidationReport, graph_ids: Iterable[str] | None = None) -> None:
    """Lanza `GraphIntegrityError` si alguna instancia pedida (o del reporte) no es entregable."""
    requested = report.graph_ids if graph_ids is None else tuple(graph_ids)
    blocked = [graph_id for graph_id in requested if not report.is_deliverable(graph_id)]
    if blocked:
        raise GraphIntegrityError(report, blocked)
