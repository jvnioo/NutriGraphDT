# Reporte de validación de los grafos reales (D1 HoloFood)

Reporte de A39-2 (#36). Aplica a los grafos construidos con `build_hetero_graph` (A39-1, #35)
las mismas herramientas usadas sobre el prototipo sintético: las reglas de integridad 1.3.0
de registro y de tensores, y los contratos Pydantic de A38-2. Es una validación estructural:
no afirma validez biológica.

Para reproducirlo:

```bash
python scripts/fetch_holofood.py
python scripts/build_graph.py --save-graphs --overwrite
```

El detalle completo queda en `artifacts/graphs/D1_holofood/report.json`.
`tests/integration/test_holofood_graph.py` comprueba los mismos resultados sobre el fixture
real de seis animales.

## Entrada

Descarga de D1 del 2026-10-07 (ver [`holofood-source.md`](../data-sources/holofood-source.md)):

| Fuente | Uso |
|---|---|
| `D1_holofood` | Abundancias SSU del contenido cecal: 185 animales y 1315 taxones. |
| `D1_holofood_metadata` | Ensayo, tratamiento, día de muestreo y peso. Se emparejaron los 185 animales; 345 animales con metadatos no tienen metagenoma. |
| `D1_holofood_scfa_content` | AGCC del contenido cecal: 454 valores medidos en los animales con metagenoma. |

## Grafos construidos

| | Mín. por grafo | Máx. por grafo | Total |
|---|---|---|---|
| Instancias | | | 185 |
| Nodos `taxon` | 1315 | 1315 | 243 275 |
| Nodos `host` | 1 | 1 | 185 |
| Nodos `diet` | 1 | 1 | 185 |
| Nodos `metabolite` (con valor en `y`) | 2 | 8 | 454 |
| Aristas `metabolite → measured_in → host` | 2 | 8 | 454 |

Columnas de `x`: `taxon` = `abundance (relative_abundance)`; `host` =
`covariates.body_weight_g (g)`; `diet` y `metabolite` no tienen columnas. 61 instancias tienen
AGCC de contenido cecal; las otras 124 no tienen nodos `metabolite` ni aristas. De las 61, 2 solo
traen lactato y ningún AGCC volátil, por eso hay 59 animales con los tres AGCC objetivo. El
conjunto supervisado es la cohorte de 56 animales de
[`holofood-source.md`](../data-sources/holofood-source.md) (#138).

## Resultado de las reglas (versión 1.3.0)

Regenerado el 2026-10-18 sobre la descarga del 2026-10-15, que reproduce los conteos de la
tabla de entrada.

**Reglas de tensores (TEN-01 a TEN-13): sin hallazgos en los 185 grafos.** Los IDs son
únicos, las dimensiones coinciden con las columnas declaradas, los tipos son correctos y no
hay `NaN` ni infinitos en `x`, `edge_attr` ni `y`.

**Reglas de registro: 124 `ERROR`; entregables a un modelo: 61 de 185.** Los 124 errores son
NOD-12: desde las reglas `1.3.0` (D-08 de la respuesta de Investigación), una instancia real
sin nodos `metabolite` no tiene objetivo y no se entrega a un modelo. Son los 124 animales con
metagenoma y sin AGCC de contenido. Sus grafos se construyen y guardan igual, y sirven para
tareas sin objetivo. Las demás reglas solo dejan advertencias, que el contrato admite y que
describen límites de la fuente:

| Regla | Severidad | Hallazgos | Causa |
|---|---|---|---|
| NOD-12 **(P)** | ERROR | 124 | Instancias sin `metabolite` (sin AGCC de contenido). |
| NOD-12 **(P)** | ADVERTENCIA | 185 | Faltan aditivo, sustrato, función y fenotipo. La falta de función será `ERROR` cuando exista la tabla de equivalencias S-04. |
| NOD-08 | ADVERTENCIA | 616 | Atributos ausentes, contados por instancia: `taxon.quantification_method`, `diet.ingredients` y `diet.composition` (185 cada uno) y `metabolite.concentration` (61; el valor vive en `y`). |
| CON-01 / CON-03 | ADVERTENCIA | 494 / 494 | Nodos sin aristas: `taxon` y `diet` en las 185 instancias (la fuente no declara relaciones taxón → función ni dieta → sustrato) y `host` en las 124 sin AGCC. |

Las aristas `metabolite → measured_in → host` son `observed` con
`evidence_method = "measurement"`, que el vocabulario cerrado de EDG-04 (`1.3.0`) admite: no
hay hallazgos EDG-04. Las instancias declaran `scenario_id = "observed"` y el dataset
`random_seed: null`. Investigación confirmó el escenario y corrigió el criterio de evidencia
([propuesta y respuesta](evidence-and-scenario-proposal.md)); `1.3.0` aplica esas
correcciones (#137). Si cambian, hay que volver a ejecutar este reporte y actualizar
`tests/integration/test_holofood_graph.py`.

## Contratos Pydantic (A38-2)

| | Revisados | No cumplen |
|---|---|---|
| Nodos | 244 099 | 0 |
| Aristas | 454 | 0 |

Los contratos aceptan un atributo `null` solo si `missing_mask` lo marca como ausente (#65),
igual que DS-01 y NOD-07. Los nodos `taxon` declaran su rango (`taxonomy_level`, #66).

## Historial

Con las reglas `1.1.0` (primera ejecución de A39-2), ningún grafo era entregable. Los bloqueaban
tres reglas pensadas para el dataset sintético:

- **EDG-04:** 454 hallazgos, por aristas `observed`.
- **INS-03:** 185 hallazgos, por `scenario_id = "unknown"`.
- **MET-01:** 1 hallazgo, por `random_seed` no entero.

Además, 243 914 nodos no cumplían los contratos porque no aceptaban atributos `null`. Cada
causa tuvo su issue de corrección (#62 a #66), resuelto en las reglas `1.2.0` y en los cambios
asociados.

Con las reglas `1.2.0`, los 185 grafos eran entregables y NOD-12 solo advertía en datos
reales. Las reglas `1.3.0` (#137) aplican los tipos obligatorios de D-08 y dejan fuera de la
entrega a un modelo los 124 grafos sin AGCC.

## Conclusión

- El constructor (A39-1) produce un `HeteroData` válido para PyG por cada animal, sin ningún
  hallazgo de tensores, con la fuente real D1 y con las tablas del dataset sintético.
- Con las reglas `1.3.0`, los 185 grafos reales cumplen los contratos y no tienen hallazgos de
  tensores ni de evidencia. Son entregables a un modelo los 61 con metabolitos; el conjunto
  supervisado es la cohorte de la fuente D1 (#138).
- Ningún grafo contiene relaciones taxón → función → metabolito: la fuente no las declara.
  Agregarlas requiere anotación funcional con evidencia `annotated`. Investigación aprobó el
  catálogo MGnify chicken-gut v1.0.1 (KEGG y CAZy), solo para taxones con enlace `1:1` en la
  tabla de equivalencias SILVA → GTDB (S-03, S-04; implementación en #137).
