"""Partición train/val/test sin fuga de datos (data leakage) para NutriGraphDT (A40-1, #71).

Este módulo define la partición única y versionada que utilizarán tanto los modelos de referencia
(baselines: Random Forest, Ridge, MLP, etc.) como las redes neuronales en grafos (GNN), para que
la evaluación comparativa sea científicamente válida e idéntica entre ejecuciones.

Principios aplicados:
1. **Sin fuga de información (no data leakage)**: el agrupamiento se realiza a nivel de corral
   (`pen_code`) o de animal/muestra, nunca por fila individual. Ningún animal ni corral aparece en
   más de un subconjunto (verificado mediante pruebas y validación estricta de disjuntos).
2. **Estratificación equilibrada**: estratifica por tratamiento dietario (`diet_treatment_code` o
   `diet_treatment_name`), tolerando grupos pequeños (incluyendo estratos con 1, 2 o 3 elementos)
   sin generar errores.
3. **Reproducibilidad determinista**: partición fijada con semilla determinista (`seed=42`).
4. **Persistencia versionada**: los índices y metadatos de la partición se guardan en un archivo
   JSON versionado en el repositorio (`configs/splits/`).
5. **Función canónica `get_split()`**: expuesta para devolver la misma partición en cualquier
   ejecución sin requerir parámetros obligatorios.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_DATASET_ID = "D1_holofood"
DEFAULT_SPLIT_FILE = "d1_holofood.json"
DEFAULT_RATIOS: tuple[float, float, float] = (0.6, 0.2, 0.2)
DEFAULT_SEED = 42


def _find_repo_root() -> Path:
    """Encuentra la raíz del repositorio de manera robusta."""
    file_root = Path(__file__).resolve().parents[3]
    if (file_root / "pyproject.toml").exists() or (file_root / "configs").exists():
        return file_root
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() or (cwd / "configs").exists():
        return cwd
    for parent in cwd.parents:
        if (parent / "pyproject.toml").exists() or (parent / "configs").exists():
            return parent
    return file_root


@dataclass(frozen=True)
class DatasetSplit:
    """Representación inmutable de una partición train/val/test versionada."""

    train: tuple[str, ...]
    val: tuple[str, ...]
    test: tuple[str, ...]
    dataset_id: str = DEFAULT_DATASET_ID
    version: str = "1.0.0"
    split_strategy: str = "group_stratified"
    group_key: str | None = "pen_code"
    stratify_key: str | None = "diet_treatment_code"
    seed: int | None = DEFAULT_SEED
    ratios: tuple[float, float, float] = DEFAULT_RATIOS
    groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def __iter__(self) -> Iterator[tuple[str, ...]]:
        """Permite desempaquetar la partición directamente: `train, val, test = split`."""
        yield self.train
        yield self.val
        yield self.test

    def __getitem__(self, key: str) -> tuple[str, ...]:
        """Permite acceso tipo diccionario: `split['train']`."""
        if key == "train":
            return self.train
        if key == "val":
            return self.val
        if key == "test":
            return self.test
        raise KeyError(f"Subconjunto no válido: {key!r}. Use 'train', 'val' o 'test'.")

    def __len__(self) -> int:
        """Número total de muestras en la partición."""
        return len(self.train) + len(self.val) + len(self.test)

    @property
    def all_samples(self) -> tuple[str, ...]:
        """Tupla con todos los identificadores de muestras ordenados."""
        return tuple(sorted(set(self.train) | set(self.val) | set(self.test)))

    def subset_of(self, sample_id: str) -> str | None:
        """Devuelve el nombre del subconjunto al que pertenece `sample_id` o None."""
        if sample_id in self.train:
            return "train"
        if sample_id in self.val:
            return "val"
        if sample_id in self.test:
            return "test"
        return None

    def validate(self) -> None:
        """Verifica que no exista fuga de datos (data leakage) entre subconjuntos ni grupos."""
        train_set = set(self.train)
        val_set = set(self.val)
        test_set = set(self.test)

        train_val = train_set & val_set
        train_test = train_set & test_set
        val_test = val_set & test_set

        if train_val:
            raise ValueError(
                f"Fuga detectada: {len(train_val)} muestras compartidas entre train y val: "
                f"{sorted(train_val)}"
            )
        if train_test:
            raise ValueError(
                f"Fuga detectada: {len(train_test)} muestras compartidas entre train y test: "
                f"{sorted(train_test)}"
            )
        if val_test:
            raise ValueError(
                f"Fuga detectada: {len(val_test)} muestras compartidas entre val y test: "
                f"{sorted(val_test)}"
            )

        if self.groups:
            g_train = set(self.groups.get("train", ()))
            g_val = set(self.groups.get("val", ()))
            g_test = set(self.groups.get("test", ()))

            g_tv = g_train & g_val
            g_tt = g_train & g_test
            g_vt = g_val & g_test

            if g_tv:
                raise ValueError(f"Fuga de grupos detectada entre train y val: {sorted(g_tv)}")
            if g_tt:
                raise ValueError(f"Fuga de grupos detectada entre train y test: {sorted(g_tt)}")
            if g_vt:
                raise ValueError(f"Fuga de grupos detectada entre val y test: {sorted(g_vt)}")

    def filter(
        self,
        data: Mapping[str, T] | Sequence[T],
        key_fn: Callable[[T], str] | None = None,
    ) -> tuple[dict[str, T] | list[T], dict[str, T] | list[T], dict[str, T] | list[T]]:
        """Filtra una colección de datos (mapeo o secuencia) en tuplas (train, val, test).

        Si `data` es un diccionario con claves como `SAMEA112904772` o `D1_holofood:SAMEA112904772`,
        empareja extrayendo el `sample_id` tras el prefijo del grafo.
        """
        train_set = set(self.train)
        val_set = set(self.val)
        test_set = set(self.test)

        if isinstance(data, Mapping):
            train_map: dict[str, T] = {}
            val_map: dict[str, T] = {}
            test_map: dict[str, T] = {}

            for key, val in data.items():
                match_id = key.split(":", 1)[1] if ":" in key else key
                if match_id in train_set:
                    train_map[key] = val
                elif match_id in val_set:
                    val_map[key] = val
                elif match_id in test_set:
                    test_map[key] = val

            return train_map, val_map, test_map

        if key_fn is None:
            raise ValueError("Se requiere `key_fn` para filtrar secuencias que no son mapeos.")

        train_list: list[T] = []
        val_list: list[T] = []
        test_list: list[T] = []

        for item in data:
            key = key_fn(item)
            match_id = key.split(":", 1)[1] if ":" in key else key
            if match_id in train_set:
                train_list.append(item)
            elif match_id in val_set:
                val_list.append(item)
            elif match_id in test_set:
                test_list.append(item)

        return train_list, val_list, test_list

    def mask(self, sample_ids: Sequence[str]) -> dict[str, list[bool]]:
        """Genera máscaras booleanas para una lista de sample_ids (útil para PyTorch/NumPy)."""
        train_set = set(self.train)
        val_set = set(self.val)
        test_set = set(self.test)

        return {
            "train": [s in train_set for s in sample_ids],
            "val": [s in val_set for s in sample_ids],
            "test": [s in test_set for s in sample_ids],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serializa la partición a un diccionario compatible con JSON."""
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "split_strategy": self.split_strategy,
            "group_key": self.group_key,
            "stratify_key": self.stratify_key,
            "seed": self.seed,
            "ratios": {
                "train": self.ratios[0],
                "val": self.ratios[1],
                "test": self.ratios[2],
            },
            "counts": {
                "train": len(self.train),
                "val": len(self.val),
                "test": len(self.test),
                "total": len(self),
            },
            "subsets": {
                "train": list(self.train),
                "val": list(self.val),
                "test": list(self.test),
            },
            "groups": {k: list(v) for k, v in self.groups.items()},
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DatasetSplit:
        """Construye un `DatasetSplit` a partir de un diccionario."""
        subsets = data.get("subsets", {})
        ratios_dict = data.get("ratios", {})
        ratios = (
            float(ratios_dict.get("train", DEFAULT_RATIOS[0])),
            float(ratios_dict.get("val", DEFAULT_RATIOS[1])),
            float(ratios_dict.get("test", DEFAULT_RATIOS[2])),
        )
        groups = {k: tuple(str(g) for g in v) for k, v in data.get("groups", {}).items()}
        return cls(
            train=tuple(str(s) for s in subsets.get("train", ())),
            val=tuple(str(s) for s in subsets.get("val", ())),
            test=tuple(str(s) for s in subsets.get("test", ())),
            dataset_id=str(data.get("dataset_id", DEFAULT_DATASET_ID)),
            version=str(data.get("version", "1.0.0")),
            split_strategy=str(data.get("split_strategy", "group_stratified")),
            group_key=data.get("group_key"),
            stratify_key=data.get("stratify_key"),
            seed=data.get("seed"),
            ratios=ratios,
            groups=groups,
            metadata=dict(data.get("metadata", {})),
        )

    def save(self, path: str | Path) -> Path:
        """Guarda la partición en un archivo JSON estructurado y ordenado."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out_path

    @classmethod
    def load(cls, path: str | Path) -> DatasetSplit:
        """Carga una partición desde un archivo JSON."""
        in_path = Path(path)
        if not in_path.exists():
            raise FileNotFoundError(f"Archivo de partición no encontrado: {in_path}")
        content = json.loads(in_path.read_text(encoding="utf-8"))
        return cls.from_dict(content)


def _extract_records(
    source: Sequence[Mapping[str, Any]] | Path | str | Any,
) -> list[dict[str, Any]]:
    """Normaliza diferentes entradas a una lista de diccionarios de metadatos."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Archivo de metadatos no encontrado: {path}")
        delimiter = "\t" if path.suffix in (".tsv", ".txt") else ","
        with path.open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle, delimiter=delimiter))

    # Si es NormalizedTabularDataset (de nutrigraphdt.data.schema)
    if hasattr(source, "instances"):
        instances = source.instances
        return [
            {
                "sample_id": inst.sample_id,
                "graph_id": inst.graph_id,
                "study_id": getattr(inst, "study_id", None),
                "diet_treatment": getattr(inst, "diet_treatment", None),
                "diet_treatment_code": getattr(inst, "diet_treatment", None),
                "timepoint": getattr(inst, "timepoint", None),
            }
            for inst in instances
        ]

    # Secuencia estándar de mapeos
    return [dict(row) for row in source]


def create_split(
    records: Sequence[Mapping[str, Any]] | Path | str | Any,
    *,
    sample_key: str = "sample_id",
    group_key: str | None = "pen_code",
    stratify_key: str | None = "diet_treatment_code",
    ratios: tuple[float, float, float] = DEFAULT_RATIOS,
    seed: int = DEFAULT_SEED,
    dataset_id: str = DEFAULT_DATASET_ID,
) -> DatasetSplit:
    """Crea una partición train/val/test estratificada por grupos sin fuga de datos.

    Args:
        records: Entrada (ruta a TSV/CSV, lista de diccionarios o NormalizedTabularDataset).
        sample_key: Campo clave de identificación de muestra / animal (por defecto 'sample_id').
        group_key: Campo de agrupación para evitar fuga (por defecto 'pen_code' para corral; si
            está ausente en una muestra, se agrupa por `sample_id`).
        stratify_key: Campo para estratificar (por defecto 'diet_treatment_code'; busca alternativas
            como 'diet_treatment_name' o 'diet_treatment' si es necesario).
        ratios: Proporciones deseadas (train, val, test); deben sumar 1.0.
        seed: Semilla determinista para asegurar reproducibilidad.
        dataset_id: Identificador del dataset.

    Returns:
        DatasetSplit inmutable y validado.
    """
    total_ratio = sum(ratios)
    if not (0.999 <= total_ratio <= 1.001):
        raise ValueError(f"Los ratios deben sumar 1.0, pero suman {total_ratio:.4f}")
    if any(r < 0 for r in ratios):
        raise ValueError(f"Los ratios no pueden ser negativos: {ratios}")

    raw_records = _extract_records(records)
    if not raw_records:
        raise ValueError("No se proporcionaron registros para particionar.")

    # 1. Agrupar muestras por `group_key` (ej. corral pen_code o animal)
    group_samples: dict[str, list[str]] = defaultdict(list)
    group_strata: dict[str, str] = {}

    for row in raw_records:
        sample_id = str(row[sample_key])

        # Determinar grupo
        group_val = row.get(group_key) if group_key else None
        group_id = sample_id if group_val is None or group_val == "" else str(group_val)

        group_samples[group_id].append(sample_id)

        # Determinar estrato
        stratum_val = None
        if stratify_key and stratify_key in row and row[stratify_key] not in (None, ""):
            stratum_val = row[stratify_key]
        elif "diet_treatment_name" in row and row["diet_treatment_name"] not in (None, ""):
            stratum_val = row["diet_treatment_name"]
        elif "diet_treatment" in row and row["diet_treatment"] not in (None, ""):
            stratum_val = row["diet_treatment"]

        stratum = str(stratum_val) if stratum_val is not None else "default"
        # En diseño HoloFood el tratamiento se asigna por corral (un estrato por corral)
        if group_id not in group_strata:
            group_strata[group_id] = stratum

    # 2. Agrupar identificadores de grupo por estrato
    strata_groups: dict[str, list[str]] = defaultdict(list)
    for group_id, stratum in group_strata.items():
        strata_groups[stratum].append(group_id)

    # 3. Barajar y repartir grupos por estrato de forma determinista
    rng = random.Random(seed)
    train_groups: list[str] = []
    val_groups: list[str] = []
    test_groups: list[str] = []

    # Alternador para estratos pequeños (ej. cuando N=2 se alterna entre val y test)
    small_stratum_toggle = 0

    # Ordenar los estratos alfabéticamente para estabilidad absoluta de iteración
    for stratum in sorted(strata_groups.keys()):
        groups = sorted(strata_groups[stratum])
        rng.shuffle(groups)
        n_groups = len(groups)

        if n_groups == 1:
            # Si solo hay 1 grupo en el estrato, se asigna al conjunto mayoritario (train)
            train_groups.extend(groups)
        elif n_groups == 2:
            # 1 a train, 1 alternado entre val y test
            train_groups.append(groups[0])
            if small_stratum_toggle % 2 == 0:
                val_groups.append(groups[1])
            else:
                test_groups.append(groups[1])
            small_stratum_toggle += 1
        elif n_groups == 3:
            # 1 a cada conjunto
            train_groups.append(groups[0])
            val_groups.append(groups[1])
            test_groups.append(groups[2])
        else:
            # n_groups >= 4: cálculo proporcional respetando mínimos
            r_tr, r_va, r_te = ratios
            n_va = max(1, round(n_groups * r_va))
            n_te = max(1, round(n_groups * r_te))
            n_tr = n_groups - n_va - n_te

            # Ajuste de seguridad si train queda en cero
            if n_tr < 1:
                n_tr = 1
                if n_va >= n_te and n_va > 1:
                    n_va -= 1
                elif n_te > 1:
                    n_te -= 1

            train_groups.extend(groups[:n_tr])
            val_groups.extend(groups[n_tr : n_tr + n_va])
            test_groups.extend(groups[n_tr + n_va :])

    # 4. Expandir grupos a listas ordenadas de sample_ids
    train_samples = sorted({s for g in train_groups for s in group_samples[g]})
    val_samples = sorted({s for g in val_groups for s in group_samples[g]})
    test_samples = sorted({s for g in test_groups for s in group_samples[g]})

    # 5. Calcular metadatos del desglose por estrato
    strata_counts: dict[str, dict[str, int]] = {}
    for stratum, s_groups in sorted(strata_groups.items()):
        s_g_set = set(s_groups)
        s_train = sum(len(group_samples[g]) for g in train_groups if g in s_g_set)
        s_val = sum(len(group_samples[g]) for g in val_groups if g in s_g_set)
        s_test = sum(len(group_samples[g]) for g in test_groups if g in s_g_set)
        strata_counts[stratum] = {
            "total_groups": len(s_groups),
            "train_samples": s_train,
            "val_samples": s_val,
            "test_samples": s_test,
        }

    metadata = {
        "total_records": len(raw_records),
        "total_groups": len(group_samples),
        "strata": strata_counts,
    }

    group_mapping = {
        "train": tuple(sorted(train_groups)),
        "val": tuple(sorted(val_groups)),
        "test": tuple(sorted(test_groups)),
    }

    split = DatasetSplit(
        train=tuple(train_samples),
        val=tuple(val_samples),
        test=tuple(test_samples),
        dataset_id=dataset_id,
        split_strategy="group_stratified",
        group_key=group_key,
        stratify_key=stratify_key,
        seed=seed,
        ratios=ratios,
        groups=group_mapping,
        metadata=metadata,
    )
    split.validate()
    return split


def get_split(
    dataset_id: str = DEFAULT_DATASET_ID,
    *,
    split_file: str | Path | None = None,
) -> DatasetSplit:
    """Devuelve la partición train/val/test versionada e idéntica en cualquier ejecución.

    Si no se pasa `split_file`, busca el archivo versionado correspondiente en
    `configs/splits/{dataset_id.lower()}.json`.

    Args:
        dataset_id: Nombre de la fuente/dataset (por defecto 'D1_holofood').
        split_file: Ruta explícita opcional a un archivo JSON de partición.

    Returns:
        DatasetSplit versionado con los subconjuntos train, val y test.
    """
    if split_file is not None:
        target_path = Path(split_file)
        if not target_path.is_absolute():
            target_path = _find_repo_root() / target_path
        return DatasetSplit.load(target_path)

    repo_root = _find_repo_root()
    splits_dir = repo_root / "configs" / "splits"

    candidates = [
        splits_dir / f"{dataset_id.lower()}.json",
        splits_dir / f"{dataset_id}.json",
        splits_dir / DEFAULT_SPLIT_FILE,
    ]

    for candidate in candidates:
        if candidate.exists():
            return DatasetSplit.load(candidate)

    # Fallback automático generando sobre fixtures si está disponible
    fixture_metadata = repo_root / "tests" / "fixtures" / "holofood" / "metadata.tsv"
    if fixture_metadata.exists() and dataset_id.lower() in ("d1_holofood", "holofood"):
        split = create_split(fixture_metadata, dataset_id=dataset_id)
        split.save(candidates[0])
        return split

    raise FileNotFoundError(
        f"No se encontró el archivo de partición versionado para '{dataset_id}' en {splits_dir}."
    )


def save_split(split: DatasetSplit, path: str | Path) -> Path:
    """Guarda un `DatasetSplit` en disco."""
    return split.save(path)


def load_split(path: str | Path) -> DatasetSplit:
    """Carga un `DatasetSplit` desde disco."""
    return DatasetSplit.load(path)


# ---------------------------------------------------------------------------
# Huella de la partición (#133)
# ---------------------------------------------------------------------------


def split_content_sha256(content: Mapping[str, Any]) -> str:
    """SHA-256 del JSON canónico de una partición.

    Serialización canónica: `json.dumps(content, sort_keys=True, ensure_ascii=False)` con los
    separadores por omisión (`", "` y `": "`), codificada en UTF-8. Es la misma que `split_info`
    usa desde A44-5 para una partición sin archivo, así que esos hashes no cambian. No depende del
    fin de línea, de la indentación ni del orden de las claves del archivo, sino solo de su
    contenido: un cambio en cualquier valor, incluida la lista de muestras, cambia el hash.
    """
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def split_file_sha256(path: str | Path) -> str:
    """SHA-256 canónico (`split_content_sha256`) del contenido JSON de un archivo de partición."""
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(content, Mapping):
        raise ValueError(f"{path}: se esperaba un objeto JSON.")
    return split_content_sha256(content)


def split_file_digests(path: str | Path) -> frozenset[str]:
    """SHA-256 aceptados al comparar una corrida registrada con un archivo de partición.

    Incluye el hash canónico (`split_file_sha256`), que es el que registran las corridas nuevas, y
    los hashes de bytes que registraban las corridas anteriores a #133: el archivo tal como está,
    con fines de línea LF y con CRLF (Git con `core.autocrlf` en Windows). Así las corridas ya
    registradas siguen siendo válidas sin aceptar ningún otro contenido.
    """
    raw = Path(path).read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    legacy = (raw, lf, lf.replace(b"\n", b"\r\n"))
    return frozenset({split_file_sha256(path), *(hashlib.sha256(v).hexdigest() for v in legacy)})
