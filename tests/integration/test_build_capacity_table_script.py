"""`scripts/build_capacity_table.py` con un catálogo local, sin red (#175)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "build_capacity_table.py"
KO = "ko:K00925"


def _main():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("build_capacity_table", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


def _write_inputs(root: Path) -> list[str]:
    s04 = root / "s04.tsv"
    s04.write_text(
        "# tabla\n"
        "silva_taxon_id\tgtdb_taxon_id\trelationship\tnotes\n"
        "g__Uno\tg__UnoGtdb\t1:1\tnota\n"
        "g__Varios\t\t1:N\tnota\n"
        "g__Nada\t\tsin par\tnota\n",
        encoding="utf-8",
    )
    produces = root / "produces.tsv"
    produces.write_text(
        "function_id\tmetabolite_id\tevidence_method\tevidence_source\tnotes\n"
        f"{KO}\tacetate\tdatabase_annotation\tKEGG@120.0\tackA\n",
        encoding="utf-8",
    )
    catalogue = root / "catalogue"
    (catalogue / "eggnog").mkdir(parents=True)
    lineage = "d__Bacteria;p__F;c__C;o__O;f__Fam;g__{};s__{}"
    (catalogue / "genomes-all_metadata.tsv").write_text(
        "Genome\tSpecies_rep\tLineage\n"
        f"G1\tG1\t{lineage.format('UnoGtdb', 'a')}\n"
        # `1:N` en S-04: su género homónimo en el catálogo no genera filas.
        f"G2\tG2\t{lineage.format('Varios', 'b')}\n",
        encoding="utf-8",
    )
    (catalogue / "eggnog" / "G1_eggNOG.tsv").write_text(
        f"#query\tKEGG_ko\ngen\t{KO},ko:K00001\n", encoding="utf-8"
    )
    output = root / "capacity.tsv"
    return [
        "--s04-table",
        str(s04),
        "--produces-table",
        str(produces),
        "--catalogue-dir",
        str(catalogue),
        "--output",
        str(output),
    ]


def test_writes_only_one_to_one_genera_with_approved_functions(tmp_path: Path) -> None:
    assert _main()(_write_inputs(tmp_path)) == 0

    lines = (tmp_path / "capacity.tsv").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if not line.startswith("#")] == [
        "silva_taxon_id\tgtdb_taxon_id\tfunction_id\tspecies_with_ko\tspecies",
        f"g__Uno\tg__UnoGtdb\t{KO}\t1\t1",
    ]
    assert lines[0].startswith("# has_capacity de D1")


def test_a_missing_table_exits_with_code_2(tmp_path: Path) -> None:
    args = _write_inputs(tmp_path)
    (tmp_path / "s04.tsv").unlink()

    assert _main()(args) == 2
