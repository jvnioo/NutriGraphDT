"""Comparación de una corrida reproducida con la original (A45-8, #108).

`scripts/reproduce_run.py` reentrena una corrida a partir de su `run.json` y usa este módulo para
comparar la corrida nueva con la original, archivo por archivo. El módulo no requiere PyTorch:
solo lee `run.json` y los CSV que deja `save_run` (A44-5).

Cada comparación produce un `Check` con uno de tres estados:

- `ok`: coincide (exactamente, o dentro de la tolerancia indicada);
- `difiere`: no coincide; el detalle dice dónde;
- `no disponible`: falta el archivo original (por ejemplo, porque solo se versionó la copia de
  `run.json`), así que no se pudo comparar.

Tolerancias (absolutas, en las unidades de cada archivo):

- `METRICS_TOLERANCE` (1e-5) para `metrics.csv`: el redondeo de float32 entre equipos y
  sistemas operativos deja diferencias del orden de 1e-7 a 1e-6 (A45-7, A45-8).
- `PREDICTIONS_TOLERANCE` (1e-4 mmol/kg) para predicciones e historia por época (pérdidas y
  métricas de `val` de cada época): float32 tiene unos 7 dígitos significativos y los AGCC llegan
  a ~100 mmol/kg; entre Windows y Linux se observó 3.8e-6.
- `SCALING_RTOL` (1e-6, relativa) para medias y desviaciones del escalado.
- `RELOAD_TOLERANCE` (1e-6) para recargar el checkpoint en el mismo equipo. Las predicciones
  del checkpoint original recargado en otro equipo se comparan con `PREDICTIONS_TOLERANCE`.
- `WEIGHTS_TOLERANCE` (1e-4) para los pesos del checkpoint original frente al reproducido
  (entre Windows y Linux se observó 4.5e-6).

`run.json` guarda el SHA-256 de los bytes del archivo de partición (A44-5). Git en Windows deja
los archivos versionados con fines de línea CRLF, así que el mismo archivo tiene otro hash en
Linux. `compare_info` acepta esa diferencia, y solo esa, si recibe los hashes del archivo con
LF y CRLF (`split_file_digests`), y lo deja escrito en el detalle.

Son provisionales: se fijaron con las diferencias observadas, no con un requisito científico.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

RUN_FILE: Final[str] = "run.json"
METRICS_FILE: Final[str] = "metrics.csv"
PREDICTIONS_FILE: Final[str] = "predictions.csv"
HISTORY_FILE: Final[str] = "history.csv"
CHECKPOINT_FILE: Final[str] = "checkpoint.pt"

OK: Final[str] = "ok"
DIFFERS: Final[str] = "difiere"
UNAVAILABLE: Final[str] = "no disponible"

METRICS_TOLERANCE: Final[float] = 1e-5
PREDICTIONS_TOLERANCE: Final[float] = 1e-4
SCALING_RTOL: Final[float] = 1e-6
RELOAD_TOLERANCE: Final[float] = 1e-6
WEIGHTS_TOLERANCE: Final[float] = 1e-4

CONFIG_KEYS: Final[tuple[str, ...]] = (
    "variant",
    "seed",
    "dataset_id",
    "source",
    "training_config",
    "model_config",
)
DATA_KEYS: Final[tuple[str, ...]] = ("split", "subsets", "metadata")
EPOCH_KEYS: Final[tuple[str, ...]] = ("best_epoch", "epochs_run", "stopped_early")
# Varían entre corridas sin afectar el resultado; no se comparan.
SOURCE_KEYS_IGNORED: Final[frozenset[str]] = frozenset({"graphs"})
# Campos de `subsets` agregados después de la corrida original (#138): su ausencia equivale a
# este valor, así las corridas anteriores siguen siendo comparables.
SUBSET_DEFAULTS: Final[Mapping[str, Any]] = {"outside_cohort": 0}


class ReproductionError(ValueError):
    """La corrida original o la reproducida no se pueden leer."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str = ""
    max_diff: float | None = None
    tolerance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "max_diff": self.max_diff,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True)
class ReproductionReport:
    original: Mapping[str, Any]
    reproduced: Mapping[str, Any]
    checks: tuple[Check, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def differs(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.status == DIFFERS)

    @property
    def reproduced_ok(self) -> bool:
        """Ninguna comparación difiere y al menos una métrica se pudo comparar."""
        metrics = [c for c in self.checks if c.name.startswith("Métricas")]
        return not self.differs and any(c.status == OK for c in metrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reproduced": self.reproduced_ok,
            "original": _summary(self.original),
            "reproduction": _summary(self.reproduced),
            "tolerances": {
                "metrics": METRICS_TOLERANCE,
                "predictions": PREDICTIONS_TOLERANCE,
                "scaling_rtol": SCALING_RTOL,
                "reload": RELOAD_TOLERANCE,
                "weights": WEIGHTS_TOLERANCE,
            },
            "checks": [c.to_dict() for c in self.checks],
            "notes": list(self.notes),
        }

    def to_markdown(self, command: str) -> str:
        original, new = _summary(self.original), _summary(self.reproduced)
        verdict = (
            "**Se reproduce**: ninguna comparación difiere."
            if self.reproduced_ok
            else "**No se reproduce**: "
            + ("; ".join(c.name for c in self.differs) or "no se pudo comparar ninguna métrica")
            + "."
        )
        lines = [
            f"# Reproducción de `{original['run_id']}` (A45-8)",
            "",
            f"Generado con `{command}`. Ver `docs/models/gnn-training.md`.",
            "",
            verdict,
            "",
            "| | Original | Reproducida |",
            "| :--- | :--- | :--- |",
        ]
        for label, key in (
            ("`run_id`", "run_id"),
            ("Variante", "variant"),
            ("Semilla", "seed"),
            ("Commit", "commit"),
            ("Dirty", "dirty"),
            ("Python", "python"),
            ("PyTorch", "torch"),
            ("PyG", "torch_geometric"),
            ("Sistema", "platform"),
            ("Dispositivo", "device"),
        ):
            lines.append(f"| {label} | {_cell(original.get(key))} | {_cell(new.get(key))} |")
        lines += [
            "",
            "| Comparación | Estado | Máx. diferencia | Tolerancia | Detalle |",
            "| :--- | :--- | ---: | ---: | :--- |",
        ]
        for check in self.checks:
            lines.append(
                f"| {check.name} | {check.status} | {_number(check.max_diff)} | "
                f"{_number(check.tolerance)} | {check.detail or '—'} |"
            )
        if self.notes:
            lines += ["", *[f"- {note}" for note in self.notes]]
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def read_run_info(path: Path) -> tuple[Path | None, dict[str, Any]]:
    """`(carpeta de la corrida, run.json)` a partir de la carpeta o de un archivo JSON.

    Un JSON con otro nombre (por ejemplo, la copia versionada `reports/gnn/<dataset>/run_*.json`)
    se acepta, pero la carpeta queda en `None`: los archivos que lo acompañan son de otras
    corridas, así que el resto de la corrida original queda como no disponible.
    """
    file = path / RUN_FILE if path.is_dir() else path
    if not file.is_file():
        raise ReproductionError(f"Falta {file}.")
    try:
        info = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReproductionError(f"{file}: JSON inválido ({error.msg}).") from error
    if not isinstance(info, dict):
        raise ReproductionError(f"{file}: se esperaba un objeto JSON.")
    missing = [k for k in (*CONFIG_KEYS, "run_id") if k not in info]
    if missing:
        raise ReproductionError(f"{file}: faltan {missing}.")
    return (file.parent if file.name == RUN_FILE else None), info


def sibling(directory: Path | None, info: Mapping[str, Any], key: str, default: str) -> Path | None:
    """Ruta de un archivo de la corrida (`files` de `run.json`), o `None` si no existe."""
    if directory is None:
        return None
    files = info.get("files") if isinstance(info.get("files"), Mapping) else {}
    assert isinstance(files, Mapping)
    candidate = directory / str(files.get(key, default))
    return candidate if candidate.is_file() else None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Comparaciones
# ---------------------------------------------------------------------------


def split_file_digests(path: Path) -> frozenset[str]:
    """SHA-256 del archivo de partición tal como está, con fines de línea LF y con CRLF."""
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    variants = (raw, lf, lf.replace(b"\n", b"\r\n"))
    return frozenset(hashlib.sha256(v).hexdigest() for v in variants)


def compare_info(
    original: Mapping[str, Any],
    new: Mapping[str, Any],
    *,
    split_digests: frozenset[str] | None = None,
) -> list[Check]:
    """Configuración, datos, escalado y épocas registrados en `run.json`.

    Con `split_digests`, una diferencia solo en `split.sha256` se acepta si ambos hashes son del
    mismo archivo con distinto fin de línea.
    """
    data = _equal_keys(
        "Datos (partición, subconjuntos, metadatos del grafo)", original, new, DATA_KEYS
    )
    if (
        data.status == DIFFERS
        and split_digests
        and _only_line_endings(original, new, split_digests)
    ):
        data = Check(
            data.name,
            OK,
            "idéntico salvo `split.sha256`: el mismo archivo de partición con fines de línea "
            "LF y CRLF (Git en Windows)",
        )
    checks = [
        _equal_keys(
            "Configuración (variante, semilla, fuente, entrenamiento, modelo)",
            original,
            new,
            CONFIG_KEYS,
        ),
        data,
    ]
    checks.append(compare_scaling(original.get("scaling"), new.get("scaling")))
    checks.append(
        _equal_keys("Épocas (mejor época, épocas corridas, detención)", original, new, EPOCH_KEYS)
    )
    return checks


def compare_scaling(original: Any, new: Any) -> Check:
    name = "Escalado ajustado con train (medias y desviaciones)"
    if original is None:
        return Check(name, UNAVAILABLE, "el run.json original no tiene `scaling`")
    a, b = dict(_flatten(original)), dict(_flatten(new))
    if a.keys() != b.keys():
        return Check(name, DIFFERS, "estructura distinta", tolerance=SCALING_RTOL)
    worst, where = 0.0, ""
    for key, value in a.items():
        other = b[key]
        if isinstance(value, float | int) and isinstance(other, float | int):
            diff = abs(float(value) - float(other)) / max(abs(float(value)), 1e-12)
            if diff > worst:
                worst, where = diff, key
        elif value != other:
            return Check(name, DIFFERS, f"{key}: {value!r} ≠ {other!r}", tolerance=SCALING_RTOL)
    status = OK if worst <= SCALING_RTOL else DIFFERS
    return Check(name, status, where if status == DIFFERS else "", worst, SCALING_RTOL)


def compare_rows(
    name: str,
    original: Sequence[Mapping[str, str]] | None,
    new: Sequence[Mapping[str, str]],
    key: Sequence[str],
    tolerance: float,
    *,
    columns: Sequence[str] | None = None,
    missing_reason: str = "falta el archivo original",
) -> Check:
    """Compara filas emparejadas por `key`; las columnas numéricas con `tolerance`.

    Las columnas no numéricas deben ser iguales. Un valor vacío (AGCC sin medir) solo coincide
    con otro vacío. Con `columns`, solo se comparan esas columnas.
    """
    if original is None:
        return Check(name, UNAVAILABLE, missing_reason)
    left = {tuple(row[k] for k in key): row for row in original}
    right = {tuple(row[k] for k in key): row for row in new}
    if left.keys() != right.keys():
        only = sorted(left.keys() ^ right.keys())[:3]
        return Check(name, DIFFERS, f"filas distintas, por ejemplo {only}", tolerance=tolerance)
    worst, where = 0.0, ""
    for row_key, row in left.items():
        other = right[row_key]
        for column in columns or [c for c in row if c not in key]:
            a, b = row.get(column, ""), other.get(column, "")
            number_a, number_b = _maybe_float(a), _maybe_float(b)
            if number_a is None or number_b is None:
                if a != b:
                    return Check(
                        name,
                        DIFFERS,
                        f"{'/'.join(row_key)} {column}: {a!r} ≠ {b!r}",
                        tolerance=tolerance,
                    )
                continue
            diff = abs(number_a - number_b)
            if diff > worst or math.isnan(diff):
                worst, where = diff, f"{'/'.join(row_key)} {column}"
    status = OK if worst <= tolerance else DIFFERS
    detail = f"{len(left)} filas" + (f"; mayor en {where}" if status == DIFFERS else "")
    return Check(name, status, detail, worst, tolerance)


def report_rows(report_csv: Path, variant: str) -> list[dict[str, str]] | None:
    """Filas `val` y `test` de la variante en un `report.csv` consolidado (A45-3, A45-4)."""
    if not report_csv.is_file():
        return None
    rows = [
        {k: v for k, v in row.items() if k != "model"}
        for row in read_csv(report_csv)
        if row.get("model") == variant and row.get("split") in {"val", "test"}
    ]
    return rows or None


def only_splits(rows: Sequence[Mapping[str, str]], splits: set[str]) -> list[dict[str, str]]:
    return [
        {k: v for k, v in row.items() if k != "model"} for row in rows if row["split"] in splits
    ]


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _only_line_endings(a: Mapping[str, Any], b: Mapping[str, Any], digests: frozenset[str]) -> bool:
    if any(_comparable(a, k) != _comparable(b, k) for k in DATA_KEYS if k != "split"):
        return False
    split_a, split_b = a.get("split"), b.get("split")
    if not isinstance(split_a, Mapping) or not isinstance(split_b, Mapping):
        return False
    rest_a = {k: v for k, v in split_a.items() if k != "sha256"}
    rest_b = {k: v for k, v in split_b.items() if k != "sha256"}
    return rest_a == rest_b and {split_a.get("sha256"), split_b.get("sha256")} <= digests


def _comparable(info: Mapping[str, Any], key: str) -> Any:
    value = info.get(key)
    if key == "source" and isinstance(value, Mapping):
        return {k: v for k, v in value.items() if k not in SOURCE_KEYS_IGNORED}
    if key == "subsets" and isinstance(value, Mapping):
        return {
            name: {**SUBSET_DEFAULTS, **subset} if isinstance(subset, Mapping) else subset
            for name, subset in value.items()
        }
    return value


def _equal_keys(
    name: str, a: Mapping[str, Any], b: Mapping[str, Any], keys: Sequence[str]
) -> Check:
    different = [k for k in keys if _comparable(a, k) != _comparable(b, k)]
    if different:
        return Check(name, DIFFERS, "distinto: " + ", ".join(f"`{k}`" for k in different))
    return Check(name, OK, "idéntico")


def _flatten(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key in sorted(value):
            yield from _flatten(value[key], f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            yield from _flatten(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _maybe_float(value: str) -> float | None:
    if value in ("", "True", "False"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _summary(info: Mapping[str, Any]) -> dict[str, Any]:
    git = info.get("git") if isinstance(info.get("git"), Mapping) else {}
    environment = info.get("environment") if isinstance(info.get("environment"), Mapping) else {}
    assert isinstance(git, Mapping) and isinstance(environment, Mapping)
    return {
        "run_id": info.get("run_id"),
        "variant": info.get("variant"),
        "seed": info.get("seed"),
        "commit": git.get("commit"),
        "dirty": git.get("dirty"),
        **{
            k: environment.get(k)
            for k in ("python", "torch", "torch_geometric", "platform", "device")
        },
    }


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "sí" if value else "no"
    text = str(value)
    return f"`{text[:12]}`" if len(text) == 40 else f"`{text}`"


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.1e}"


__all__ = [
    "CHECKPOINT_FILE",
    "DIFFERS",
    "HISTORY_FILE",
    "METRICS_FILE",
    "METRICS_TOLERANCE",
    "OK",
    "PREDICTIONS_FILE",
    "PREDICTIONS_TOLERANCE",
    "RELOAD_TOLERANCE",
    "RUN_FILE",
    "SCALING_RTOL",
    "UNAVAILABLE",
    "WEIGHTS_TOLERANCE",
    "Check",
    "ReproductionError",
    "ReproductionReport",
    "compare_info",
    "compare_rows",
    "compare_scaling",
    "only_splits",
    "read_csv",
    "read_run_info",
    "report_rows",
    "sibling",
    "split_file_digests",
]
