# Reporte de validación de los grafos reales (D1 HoloFood)

Reporte de A39-2 (#36). Aplica a los grafos construidos con `build_hetero_graph` (A39-1, #35)
las mismas herramientas usadas sobre el prototipo sintético: las reglas de integridad 1.1.0
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

Descarga de D1 del 2026-10-07 (ver [`holofood-source.md`](holofood-source.md)):

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
AGCC de contenido cecal; las otras 124 no tienen nodos `metabolite` ni aristas.

## Resultado de las reglas

**Reglas de tensores (TEN-01 a TEN-13): sin hallazgos en los 185 grafos.** Los IDs son
únicos, las dimensiones coinciden con las columnas declaradas, los tipos son correctos y no
hay `NaN` ni infinitos en `x`, `edge_attr` ni `y`.

Reglas de registro:

| Regla | Severidad | Hallazgos | Causa | Issue |
|---|---|---|---|---|
| EDG-04 **(P)** | ERROR | 454 | Las aristas `measured_in` son `observed`. La regla exige `synthetic` mientras Investigación no apruebe criterios de evidencia (§6.1-v). | #62 |
| INS-03 | ERROR | 185 | `scenario_id = "unknown"`: una observación real no es un escenario basal ni intervenido. | #63 |
| MET-01 | ERROR | 1 (dataset) | `random_seed` no es entero: un dataset real no tiene semilla. | #64 |
| NOD-08 | ADVERTENCIA | 801 | Atributos ausentes, contados por instancia: `taxon.taxonomy_level` y `taxon.quantification_method` (185 cada uno), `diet.ingredients` y `diet.composition` (185 cada uno) y `metabolite.concentration` (61; el valor vive en `y`). | #65, #66 |
| NOD-12 **(P)** | ADVERTENCIA | 185 | Faltan tipos de nodo (aditivo, sustrato, función, fenotipo); en datos reales es advertencia. | — |
| CON-01 / CON-03 | ADVERTENCIA | 494 / 494 | Nodos sin aristas: `taxon` y `diet` en las 185 instancias (la fuente no declara relaciones taxón → función ni dieta → sustrato) y `host` en las 124 sin AGCC. | — |

**Entregables a un modelo: 0 de 185.** Los tres `ERROR` vienen de reglas provisionales
pensadas para el dataset sintético, no de defectos de los grafos. Cada uno tiene su issue de
corrección: dos esperan una decisión de Investigación (#62, #63) y uno es un cambio de reglas
de Desarrollo (#64).

## Contratos Pydantic (A38-2)

| | Revisados | No cumplen |
|---|---|---|
| Nodos | 244 099 | 243 914 |
| Aristas | 454 | 0 |

Todos los incumplimientos de nodos tienen la misma causa. Los contratos exigen un valor en
cada atributo, mientras DS-01 admite `null` con `missing_mask: true`, y las reglas NOD lo
aceptan. Afecta a `taxon.taxonomy_level` (243 275), `metabolite.concentration` (454) y
`diet.ingredients` (185). Corrección en #65; el rango taxonómico en sí, en #66.

## Conclusión para A39-1 y A39-2

- El constructor produce un `HeteroData` válido para PyG (`validate(raise_on_error=True)`) por
  cada animal, sin ningún hallazgo de tensores, tanto con la fuente real D1 como con las
  tablas del dataset sintético.
- La entrega a un modelo queda bloqueada solo por EDG-04, INS-03 y MET-01. Cuando se cierren
  #62 a #64, hay que volver a ejecutar este reporte y actualizar `KNOWN_BLOCKING_RULES` en
  `tests/integration/test_holofood_graph.py`.
