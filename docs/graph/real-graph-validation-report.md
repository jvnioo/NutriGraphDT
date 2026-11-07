# Reporte de validación de los grafos reales (D1 HoloFood)

Reporte de A39-2 (#36). Aplica a los grafos construidos con `build_hetero_graph` (A39-1, #35)
las mismas herramientas usadas sobre el prototipo sintético: las reglas de integridad 1.6.0
de registro y de tensores, y los contratos Pydantic de A38-2. Es una validación estructural:
no afirma validez biológica.

Para reproducirlo:

```bash
python scripts/fetch_holofood.py
python scripts/build_capacity_table.py   # solo si cambia la tabla S-04 o las relaciones aprobadas
python scripts/build_graph.py --save-graphs --overwrite
python scripts/summarize_d1_graphs.py
```

El detalle completo queda en `artifacts/graphs/D1_holofood/report.json`.
`tests/integration/test_holofood_graph.py` comprueba los mismos resultados sobre el fixture
real de seis animales.

## Entrada

Regenerado el 2026-11-07 (#173) con las reglas `1.6.0`, sobre la descarga de D1 del 2026-10-15
(ver [`holofood-source.md`](../data-sources/holofood-source.md)):

| Fuente | Uso | SHA-256 del archivo (`manifest.json`) |
|---|---|---|
| `D1_holofood` | Abundancias SSU del contenido cecal: 185 animales y 1317 linajes. | `9d70fb53…` |
| `D1_holofood_metadata` | Ensayo, tratamiento, día de muestreo, sexo, línea y peso. Se emparejaron los 185 animales; 345 animales con metadatos no tienen metagenoma. | `432dfa90…` |
| `D1_holofood_scfa_content` | AGCC del contenido cecal: 454 valores medidos en los animales con metagenoma. | `f983d489…` |
| `configs/taxonomy/s04_silva132_gtdb_r207.tsv` | Tabla S-04, decisión de Investigación v2.0 (#236): 498 géneros, 118 con enlace `1:1`. | Versionada |
| `configs/functions/has_capacity_d1.tsv` | KO aprobados por género `1:1`, desde MGnify chicken-gut v1.0.1 (#175): 62 filas. | Versionada |
| `configs/functions/scfa_produces_d1.tsv` | Relaciones `produces` aprobadas, KEGG Release 120.0 (#257): 9 filas. | Versionada |

## Grafos construidos

Las abundancias se agregan a género con nodos residuales (contrato v2 §6).

| | Mín. por grafo | Máx. por grafo | Total |
|---|---:|---:|---:|
| Instancias | | | 185 |
| Nodos `taxon` (498 géneros y 378 residuales) | 876 | 876 | 162 060 |
| Nodos `function` (KO) | 7 | 7 | 1295 |
| Nodos `host` | 1 | 1 | 185 |
| Nodos `diet` | 1 | 1 | 185 |
| Nodos `metabolite` (con valor en `y`) | 2 | 8 | 454 |
| Aristas `taxon → has_capacity → function` | 62 | 62 | 11 470 |
| Aristas `function → produces → metabolite` | 7 | 7 | 413 |
| Aristas `metabolite → measured_in → host` | 2 | 8 | 454 |

Columnas de `x`: `taxon` = `abundance (relative_abundance)`; `diet` = tratamiento one-hot (3);
`host` = ensayo, día, sexo y línea one-hot (10); `function` y `metabolite` no tienen columnas. 61
instancias tienen AGCC de contenido cecal; las otras 124 no tienen nodos `metabolite` ni aristas
hacia ellos. De las 61, 2 solo traen lactato: son las únicas sin `produces`, y por eso hay 59
animales con los tres AGCC (413 = 59 × 7). El conjunto supervisado es la cohorte de 56 animales
de [`holofood-source.md`](../data-sources/holofood-source.md) (#138).

**Qué parte de la ruta cubre.** De las 11 relaciones del esquema, D1 tiene 3, frente a las 11 del
grafo sintético. 38 de los 876 taxones tienen aristas funcionales, hacia 7 de los 9 KO aprobados:
*pduW* y *ydiF* no tienen portador entre los géneros enlazados. Con la tabla de S-04, la ruta llega
al 36,1 % de las lecturas a género para acetato, al 35,8 % para butirato y al 2,1 % para propionato
([decisión de #256](../research/decision_minimal_graph_D1.md), sección 5).

## Resultado de las reglas (versión 1.6.0)

**Reglas de tensores (TEN-01 a TEN-13): sin hallazgos en los 185 grafos.** Los IDs son únicos, las
dimensiones coinciden con las columnas declaradas, los tipos son correctos y no hay `NaN` ni
infinitos en `x`, `edge_attr` ni `y`.

**Reglas de registro: 124 `ERROR` y 2100 `ADVERTENCIA`; entregables a un modelo: 61 de 185.** Los
124 errores son NOD-12: una instancia real sin nodos `metabolite` no tiene objetivo y no se entrega
a un modelo (reglas `1.3.0`, D-08). Son los 124 animales con metagenoma y sin AGCC de contenido.

| Regla | Severidad | Hallazgos | Causa |
|---|---|---:|---|
| NOD-12 **(P)** | ERROR | 124 | Instancias sin `metabolite` (sin AGCC de contenido). |
| NOD-12 **(P)** | ADVERTENCIA | 185 | Faltan aditivo, sustrato y fenotipo. `function` ya no falta: con la tabla S-04 declarada, su falta sería `ERROR`. |
| NOD-08 | ADVERTENCIA | 1110 | Atributos ausentes en las 185 instancias: `taxon.quantification_method`, `diet.ingredients` y `diet.composition`, y `function.annotation_value`, `annotation_value_type` y `unit` (la capacidad es una anotación de presencia, sin valor). |
| CON-01 | ADVERTENCIA | 494 | Nodos sin aristas: `taxon` y `diet` en las 185 instancias (838 de los 876 taxones no tienen enlace funcional) y `host` en las 124 sin AGCC. |
| CON-03 | ADVERTENCIA | 309 | Tipos que ninguna arista referencia: `diet` en las 185 instancias y `host` en las 124 sin AGCC. |
| CON-04 | ADVERTENCIA | 2 | Las 2 instancias que solo traen lactato: `taxon`–`function` y `metabolite`–`host` quedan como componentes separados. |

No hay hallazgos EDG: las aristas `measured_in` son `observed` / `measurement`; `has_capacity` es
`annotated` / `database_annotation` / `mgnify-chicken-gut@v1.0.1` y parte siempre de un taxón con
enlace `1:1`, y `produces` es `annotated` / `database_annotation` / `KEGG@120.0`. Las instancias
declaran `scenario_id = "observed"` y el dataset `random_seed: null`
([propuesta y respuesta](evidence-and-scenario-proposal.md)). Si cambian estas reglas, hay que volver
a ejecutar este reporte y actualizar `tests/integration/test_holofood_graph.py`.

## Contratos Pydantic (A38-2)

| | Revisados | No cumplen |
|---|---:|---:|
| Nodos | 164 179 | 0 |
| Aristas | 12 337 | 0 |

Los contratos aceptan un atributo `null` solo si `missing_mask` lo marca como ausente (#65), igual
que DS-01 y NOD-07. Los nodos `taxon` declaran su rango (`taxonomy_level`, #66) y su linaje hasta
el rango de trabajo (`taxonomy_id`, #175).

## Comparación con la ejecución anterior

La ejecución anterior es la del 01-11-2026 (reglas `1.5.0`, misma descarga, con la dieta codificada
por #176 y sin agregar a género). Las diferencias se explican por #175:

| Medida | Antes | Ahora | Por qué |
|---|---:|---:|---|
| Nodos `taxon` por grafo | 1317 | 876 | Agregación a género: 472 especies y 467 géneros pasan a 498 géneros, y los rangos superiores a 378 residuales. |
| Nodos `function` por grafo | 0 | 7 | KO con portador entre los géneros enlazados (#257). |
| Aristas por grafo, sin `measured_in` | 0 | 62 + 7 | `has_capacity` y `produces`. |
| Nodos revisados por los contratos | 244 469 | 164 179 | Menos taxones (−81 585) y nodos de función (+1295). |
| Aristas revisadas por los contratos | 454 | 12 337 | +11 470 `has_capacity` y +413 `produces`. |
| Entregables | 61 | 61 | No cambia: depende de `metabolite`. |
| NOD-12 `ERROR` | 124 | 124 | No cambia. |
| NOD-12 `ADVERTENCIA` | 185 | 185 | Igual cantidad, sin `function` entre los tipos faltantes. |
| NOD-08 | 555 | 1110 | +555: tres atributos ausentes de `function` en las 185 instancias. |
| CON-01 | 494 | 494 | No cambia: los taxones sin enlace siguen aislados en cada instancia. |
| CON-03 | 494 | 309 | −185: el tipo `taxon` ya tiene aristas. |
| CON-04 | 0 | 2 | Nueva: las 2 instancias con solo lactato. |
| Versión de las reglas | `1.5.0` | `1.6.0` | EDG-04 admite `mgnify-chicken-gut` como base de `has_capacity`. |

Los datos crudos no cambiaron. **Los resultados de los modelos anteriores a esta fecha se obtuvieron
con el grafo sin agregar y sin aristas funcionales**, en el que el bloque `taxon` de la lectura es
constante entre animales ([decisión de #239](../research/decision_taxon_identity_D1.md)).

## Historial

- **`1.1.0`** (primera ejecución de A39-2): ningún grafo era entregable. Bloqueaban EDG-04 (454, por
  aristas `observed`), INS-03 (185, por `scenario_id = "unknown"`) y MET-01 (1, por `random_seed` no
  entero), y 243 914 nodos no cumplían los contratos porque no aceptaban `null`. Cada causa tuvo su
  issue de corrección (#62 a #66), resuelto en `1.2.0`.
- **`1.2.0`:** los 185 grafos eran entregables y NOD-12 solo advertía en datos reales.
- **`1.3.0`** (#137): aplica los tipos obligatorios de D-08 y deja fuera de la entrega a un modelo los
  124 grafos sin AGCC.
- **`1.5.0`** (#176): la dieta se codifica en `x`.
- **`1.6.0`** (#175): esta ejecución.

## Conclusión

- El constructor produce un `HeteroData` válido para PyG por cada animal, sin hallazgos de tensores,
  con la fuente real D1 y con las tablas del dataset sintético.
- Con las reglas `1.6.0`, los 185 grafos reales cumplen los contratos y no tienen hallazgos de
  tensores ni de evidencia. Son entregables a un modelo los 61 con metabolitos; el conjunto
  supervisado es la cohorte de la fuente D1 (#138).
- El grafo contiene la parte `taxón → función → metabolito` de la ruta, solo con enlaces `1:1` y sin
  uniones por nombre. Es capacidad **anotada**, no actividad demostrada, y este reporte es una
  validación estructural: **no afirma validez biológica**.
- La mitad inicial de la ruta (`dieta → sustrato → taxón`) es una limitación declarada
  ([decisión de #258](../research/decision_diet_substrate_D1.md)), y el 55,3 % de las lecturas que no
  llega a género queda sin camino funcional.
- La cohorte supervisada y sus exclusiones están en
  [`reports/cohort/d1_holofood.md`](../../reports/cohort/d1_holofood.md).
- La procedencia se auditó en [`real-graph-provenance-audit.md`](real-graph-provenance-audit.md) (#174). Es
  una auditoría de Desarrollo: Investigación no respondió antes del cierre.
