# Catálogo de escenarios de referencia (A93-P2, #310)

Escenarios versionados que usan la app, las pruebas E2E y la demostración. Un archivo JSON por
escenario, llamado `<id>.json`. Los lee y valida `nutrigraphdt.simulation.load_catalog`
(esquema Pydantic `CatalogScenario`, que rechaza campos no declarados). Los criterios para leer
sus resultados están en [`docs/models/scenario-comparison.md`](../../docs/models/scenario-comparison.md).

> **Datos sintéticos.** Todos los escenarios derivan de la cohorte sintética
> (`build_synthetic_cohort`) y los responde la corrida sintética congelada
> (`tests/fixtures/api/frozen_runs/synthetic`). No describen animales reales. Los targets
> sintéticos no dependen de la dieta ni del aditivo (DS-01): la diferencia entre un escenario y su
> basal describe al modelo, no un efecto de la intervención.

## Formato

| Campo | Tipo | Qué es |
|---|---|---|
| `schema_version` | `"1.0.0"` | Versión del esquema del archivo. |
| `id` | `str` (`a-z`, `0-9`, `-`) | Identificador; igual al nombre del archivo. |
| `version` | `int ≥ 1` | Versión del escenario; sube si cambia su contenido. |
| `label`, `description` | `str` | Texto para la interfaz y la demostración. |
| `run` | `"synthetic"` | Corrida que lo responde (`nutrigraphdt.api.DEMO_RUNS`). |
| `base_seed` | `int ≥ 1` | Semilla del animal base en `build_synthetic_cohort` (`synthetic:sample:<semilla>`). |
| `intervention` | lista de `{variable, value}` | Variables que cambian, con el vocabulario del contrato de la API; vacía en el basal. |
| `value_sources` | lista de `{variable, source}` | De dónde sale cada valor intervenido; una por variable. |
| `expected_status` | `estimable` \| `no_estimable` | Lo que devuelve la corrida; lo exigen las pruebas. |
| `null_intervention` | `bool` | `true` si fija variables en el valor que ya tiene el animal base. |
| `is_synthetic` | `true` | Siempre verdadero. |

## Escenarios

El animal base es `synthetic:sample:0017` (semilla 17), que está en el test de la corrida. En la
cohorte, dieta y aditivo son iguales en todos los animales (dieta basal estándar con 215 g/kg de
proteína bruta y el probiótico con 1 × 10⁹ UFC/kg): cambiarlos es extrapolar, y la respuesta lo
advierte.

| Archivo | Variable | Valor | Fuente del valor | Estado esperado |
|---|---|---|---|---|
| `basal.json` | — | — | — | `estimable` |
| `crude-protein-270.json` | `diet.composition.crude_protein` | 270 g/kg | Par de DS-04 (`INTERVENTION_INTERVENED_VALUE`) | `estimable` (con advertencia de extrapolación) |
| `crude-protein-195.json` | `diet.composition.crude_protein` | 195 g/kg | Segunda dieta del catálogo sintético (`_DIET_CATALOG`) | `estimable` (con advertencia de extrapolación) |
| `crude-protein-null.json` | `diet.composition.crude_protein` | 215 g/kg | Basal de DS-04 (`INTERVENTION_BASAL_VALUE`): intervención nula | `estimable`, igual al basal |
| `additive-dose-null.json` | `additive.dose` | 1 × 10⁹ UFC/kg | Probiótico del catálogo sintético (`_ADDITIVE_CATALOG`): intervención nula | `estimable`, igual al basal |
| `additive-dose-control.json` | `additive.dose` | 0 | Aditivo de control del catálogo sintético (`_ADDITIVE_CATALOG`) | `no_estimable` (fuera de soporte) |

Las otras dosis del catálogo de aditivos están en mg/kg y la corrida solo admite `additive.dose`
en UFC/kg (el probiótico de la cohorte), así que no se usan: la interfaz no puede cambiar la unidad.

## Agregar o cambiar un escenario

1. Tome los valores del diccionario sintético (`nutrigraphdt.data.synthetic`); no invente uno.
2. Declare su fuente en `value_sources`.
3. Corra `pytest tests/unit/test_simulation_catalog.py tests/integration/test_simulation_scenarios.py`:
   las pruebas exigen el estado esperado con la corrida congelada y la invariancia.
4. Si cambia el contenido de un escenario existente, suba `version`.
