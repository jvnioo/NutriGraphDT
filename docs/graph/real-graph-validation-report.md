# Reporte de validación de los grafos reales (D1 HoloFood)

Reporte de A39-2 (#36). Aplica a los grafos construidos con `build_hetero_graph` (A39-1, #35)
las mismas herramientas usadas sobre el prototipo sintético: las reglas de integridad 1.2.0
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
AGCC de contenido cecal; las otras 124 no tienen nodos `metabolite` ni aristas.

## Resultado de las reglas (versión 1.2.0)

**Reglas de tensores (TEN-01 a TEN-13): sin hallazgos en los 185 grafos.** Los IDs son
únicos, las dimensiones coinciden con las columnas declaradas, los tipos son correctos y no
hay `NaN` ni infinitos en `x`, `edge_attr` ni `y`.

**Reglas de registro: 0 `ERROR`; entregables a un modelo: 185 de 185.** Quedan solo
advertencias, que el contrato admite y que describen límites de la fuente:

| Regla | Severidad | Hallazgos | Causa |
|---|---|---|---|
| NOD-08 | ADVERTENCIA | 616 | Atributos ausentes, contados por instancia: `taxon.quantification_method`, `diet.ingredients` y `diet.composition` (185 cada uno) y `metabolite.concentration` (61; el valor vive en `y`). |
| NOD-12 **(P)** | ADVERTENCIA | 185 | Faltan tipos de nodo (aditivo, sustrato, función, fenotipo); en datos reales es advertencia. |
| CON-01 / CON-03 | ADVERTENCIA | 494 / 494 | Nodos sin aristas: `taxon` y `diet` en las 185 instancias (la fuente no declara relaciones taxón → función ni dieta → sustrato) y `host` en las 124 sin AGCC. |

Las aristas `metabolite → measured_in → host` son `observed` con
`evidence_method = "measurement"`, que la política de evidencia de las reglas `1.2.0` admite.
Las instancias declaran `scenario_id = "observed"` y el dataset `random_seed: null`. Esas tres
reglas son una [propuesta provisional](evidence-and-scenario-proposal.md) de Desarrollo,
pendiente de contraste con Investigación. Si Investigación la cambia, hay que volver a
ejecutar este reporte y actualizar `tests/integration/test_holofood_graph.py`.

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

## Conclusión

- El constructor (A39-1) produce un `HeteroData` válido para PyG por cada animal, sin ningún
  hallazgo de tensores, con la fuente real D1 y con las tablas del dataset sintético.
- Con las reglas `1.2.0`, los 185 grafos reales cumplen las reglas de integridad y los
  contratos, y son entregables a un modelo.
- Ningún grafo contiene relaciones taxón → función → metabolito: la fuente no las declara.
  Agregarlas requiere anotación funcional (KEGG, MetaCyc, CAZy) con evidencia `annotated`.
