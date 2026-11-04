#!/usr/bin/env python3
"""
compare_silva_mgnify_genera.py
Cruce SILVA->GTDB (solo 1:1) con catalogo MGnify chicken-gut v1.0.1.
Paginacion robusta por numero de pagina (NO por link 'next').
"""

import json
import sys
from pathlib import Path

import pandas as pd
import requests

TSV_TABLE = Path("configs/taxonomy/s04_silva_gtdb_minimal.tsv")
OUTPUT = Path("docs/research/silva_mgnify_crosscheck.tsv")

CATALOGUE_ID = "chicken-gut-v1-0-1"
API_BASE = f"https://www.ebi.ac.uk/metagenomics/api/v1/genome-catalogues/{CATALOGUE_ID}/genomes"
PAGE_SIZE = 100
MAX_PAGES = 200


def load_1a1_genera():
    df = pd.read_csv(TSV_TABLE, sep="\t", comment="#", dtype=str, keep_default_na=False)
    df_1a1 = df[df["relationship"] == "1:1"].copy()
    print(f"[INFO] Generos 1:1 a cruzar: {len(df_1a1)}")
    return df_1a1


def fetch_all_genomes(session):
    seen_ids = set()
    genomes = []
    page = 0
    while page < MAX_PAGES:
        page += 1
        params = {"page": page, "page_size": PAGE_SIZE}
        print(f"[INFO] GET page={page} page_size={PAGE_SIZE}")
        r = session.get(API_BASE, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", [])
        if not items:
            print(f"[INFO] Pagina {page} vacia -> fin.")
            break
        if page == 1:
            print(f"[DEBUG] meta: {json.dumps(data.get('meta', {}))[:400]}")
            print(f"[DEBUG] items en pagina 1: {len(items)}")
        new_ids = [it["id"] for it in items if it.get("id") not in seen_ids]
        if not new_ids:
            print(f"[INFO] Pagina {page} sin novedades -> bucle detectado, fin.")
            break
        for it in items:
            gid = it.get("id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                genomes.append(it)
        print(f"[INFO] Acumulados unicos: {len(genomes)}")
        if len(items) < PAGE_SIZE:
            print(f"[INFO] Pagina {page} con {len(items)} < {PAGE_SIZE} -> fin.")
            break
    return genomes


def extract_genus(genome):
    attrs = genome.get("attributes", {})
    # MGnify usa "taxon-lineage" con guion; aceptamos variantes por robustez
    for key in ("taxon-lineage", "taxonomy", "lineage", "taxon_lineage", "taxonomy_lineage"):
        tax = attrs.get(key)
        if not tax:
            continue
        if isinstance(tax, str):
            for part in tax.split(";"):
                part = part.strip()
                if part.startswith("g__"):
                    return part
        else:
            s = json.dumps(tax).replace(";", " ")
            for token in s.replace(",", " ").split():
                token = token.strip().strip('"').strip("'")
                if token.startswith("g__"):
                    return token
    return None


def main():
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    df_1a1 = load_1a1_genera()
    try:
        genomes = fetch_all_genomes(session)
    except requests.RequestException as e:
        print(f"[ERROR] API MGnify: {e}", file=sys.stderr)
        sys.exit(1)
    if genomes:
        print("[DEBUG] Esquema del primer genoma (recortado):")
        print(json.dumps(genomes[0], indent=2)[:1500])
    generos_mgnify = {g for g in (extract_genus(x) for x in genomes) if g}
    print(f"[INFO] Generos distintos detectados en MGnify: {len(generos_mgnify)}")
    print(f"[INFO] Muestra: {sorted(generos_mgnify)[:20]}")
    rows = []
    for _, row in df_1a1.iterrows():
        gen = row["gtdb_taxon_id"]
        presente = gen in generos_mgnify
        rows.append(
            {
                "silva_taxon_id": row["silva_taxon_id"],
                "gtdb_taxon_id": gen,
                "present_in_chicken_gut_v1_0_1": "yes" if presente else "no",
                "notes": (
                    "cruce por g__ en taxonomy" if presente else "no encontrado en el catalogo"
                ),
            }
        )
    out = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, sep="\t", index=False)
    print(f"[OK] Guardado en {OUTPUT}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
