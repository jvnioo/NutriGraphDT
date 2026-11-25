# Contrato de la capa `nutrigraphdt.api` (v1.0.0)

- **Módulo:** `nutrigraphdt.api` (`src/nutrigraphdt/api/`)
- **Versión del contrato:** `1.0.0` (`API_CONTRACT_VERSION`)
- **Origen:** A81-P1 (#287), actividad A81 (#286)
- **Consumidores:** la página «Simulador de escenarios» de la demo
  (`nutrigraphdt.demo.pages.scenario_simulator`) y cualquier interfaz futura

## 1. Propósito y límites

La capa separa la interfaz del motor. La interfaz envía un `ScenarioRequest` y recibe un
`ScenarioResponse`: no ve tensores, grafos, corridas ni el soporte por dentro. La interfaz no
importa nada del motor fuera de `nutrigraphdt.api`; lo exige
`tests/unit/test_api_contract.py::test_simulator_page_only_reaches_the_engine_through_the_api`.

Límites que el contrato hace cumplir:

1. **Fuera de soporte no hay números.** Una predicción fuera del soporte empírico de la corrida
   se devuelve como `no_estimable` con sus motivos, sin fracciones, sin `ln T` y sin intervalo
   (D-06 §7). El validador de `ScenarioResponse` rechaza una respuesta que lo viole.
2. **Un escenario no es un efecto causal.** Toda respuesta lleva `CAUSAL_WARNING` en
   `warnings`; el validador lo exige.
3. **Sin aristas `hypothetical`.** Si la instancia base tiene una, el motor rechaza el escenario
   (#256, sección 3).
4. **Solo variables declaradas.** El motor rechaza toda variable que no sea una entrada del
   modelo en nodos `diet`, `additive` o `host` de la corrida (§3).

`contract.py` no depende de PyTorch. El motor (`engine.py`) y el catálogo de demostración
(`demo.py`) se importan al usarlos, así que `import nutrigraphdt.api` no carga los extras `graph`
ni `baselines`.

## 2. Entrada: `ScenarioRequest`

| Campo | Tipo | Regla |
|---|---|---|
| `contract_version` | `"1.0.0"` | Obligatorio. Otra versión se rechaza. |
| `base_instance` | texto no vacío | `sample_id` del animal observado del que se deriva el escenario. Debe existir en la base de la corrida. |
| `intervention` | lista de `InterventionItem` | Variables que cambian. Vacía: escenario basal (control de calidad). |

`InterventionItem` es `{variable, value}`, como un elemento de `intervention` en las instancias
derivadas (contrato de datos v2 §7, #151):

- `variable` usa la ruta `<tipo de nodo>.<ruta del atributo>` de `nutrigraphdt.data.derived`;
  por ejemplo, `diet.composition.crude_protein`, `diet.name`, `additive.dose` o
  `host.covariates.sex`. Una variable no se repite.
- `value` es un booleano, entero, real finito o texto; no puede ser `null` (un valor ausente no
  es una intervención).

Todos los modelos son estrictos (`extra="forbid"`): un campo no declarado se rechaza.

## 3. Vocabulario: qué se puede intervenir

`ScenarioEngine.variables` lista las variables que admite una corrida (`ScenarioVariable`:
ruta, tipo de nodo, `numeric` o `categorical`, unidad, categorías y rótulo). Sale del
`FeatureSchema` del conjunto con que se entrenó la corrida: solo las columnas que el modelo lee
como entrada en `diet`, `additive` y `host`. Una variable que el modelo no lee no puede cambiar
la predicción, y aceptarla haría creer que sí.

Los nodos del microbioma (taxones, funciones y sustratos) no se intervienen: una variable se
aplica a todos los nodos de su tipo (#151), y darles la misma abundancia a todos los taxones no
describe ningún escenario.

Validación de valores en el motor:

- Una variable numérica recibe un número; una categórica, una de sus categorías.
- Las magnitudes en `g_kg`, `MJ_kg`, `CFU_kg`, `d` y `g` no pueden ser negativas, y un componente
  de la dieta en g/kg no supera 1000 g/kg. Son cotas de la unidad, no umbrales científicos
  (A81-P4, #290).

INS-05 a INS-07 comparan la instancia derivada de un animal real con su origen; cualquier
hallazgo detiene la predicción, porque significaría que cambió algo no declarado.

## 4. Salida: `ScenarioResponse`

| Campo | Contenido |
|---|---|
| `contract_version` | `"1.0.0"` |
| `request` | La petición validada. |
| `status` | `estimable` o `no_estimable`, según `EmpiricalSupport.check` (#245). |
| `fractions` | Fracciones molares de acetato, propionato y n-butirato (suman 1), o `null` si no es estimable. |
| `log_total` | `ln T`, con `T` la suma de los tres AGCC en mmol/kg de digesta fresca, o `null` si no es estimable. |
| `reasons` | Por qué no es estimable: qué fracción, con qué valor y fuera de qué intervalo. Vacío si es estimable. |
| `interval` | Intervalo predictivo opcional (`PredictionInterval`). El motor v1 no lo calcula: queda `null` para A75. |
| `model` | Corrida que predijo (`ModelRef`): `run_id`, variante, brazo de aristas, conjunto, semilla, fold, versiones de formato y objetivo, commit. |
| `support` | Soporte aplicado (`SupportRef`): versión, subconjunto fuente, número de animales, intervalo por fracción y método. |
| `is_synthetic` | `true` si la base y la corrida vienen de datos sintéticos. |
| `warnings` | Advertencias de interpretación (§5). |

## 5. Advertencias

| Constante | Cuándo |
|---|---|
| `CAUSAL_WARNING` | Siempre. |
| `SYNTHETIC_WARNING` | Base sintética. |
| `D1_PARTIAL_WARNING` | Base de D1: el grafo tiene 3 de las 11 relaciones del esquema v1. |
| `D1_FIXTURE_WARNING` | Fixture de seis animales de D1: modelo de demostración. |
| `BASAL_WARNING` | `intervention` vacía. |
| `IN_TRAIN_WARNING` | El animal base está en el train de la corrida. |
| `COVERAGE_WARNING` | Un valor intervenido no se observó en el train de la corrida (fuera de `[mín, máx]` o categoría no vista). |

`COVERAGE_WARNING` no cambia el estado: D-06 §7 define `no_estimable` por las fracciones
predichas, no por las entradas. Una predicción puede caer dentro del soporte con una entrada que
el modelo nunca vio (en la cohorte sintética de demostración, toda la dieta es constante), y
la advertencia lo dice. Si una entrada fuera de lo observado debe ser `no_estimable` es una
pregunta abierta para Investigación (§8).

## 6. Uso

```python
from nutrigraphdt.api import DEMO_RUNS, ScenarioRequest

engine = DEMO_RUNS["d1_fixture"].engine()  # cárguelo una vez
response = engine.predict(
    ScenarioRequest(
        contract_version="1.0.0",
        base_instance="SAMEA112904810",
        intervention=({"variable": "diet.name", "value": "Probiotic"},),
    )
)
```

`predict_scenario(request, run_dir=..., base=...)` hace lo mismo en una llamada, pero carga la
corrida y calcula el soporte cada vez. `ScenarioEngine` también expone `split_of(sample_id)`
(papel del animal en la corrida), `train_coverage` y `base.values_of(sample_id, variable)` (valor
observado), que la interfaz usa para rotular y prellenar. Un error de contrato se informa como
`ScenarioContractError`, con la lista `problems`.

Las corridas y escenarios de demostración (`DEMO_RUNS`, `demo_scenarios`) están en
`tests/fixtures/api/`; ver su README.

## 7. Versionado

El contrato sigue SemVer. Cambia el mayor si una interfaz anterior deja de ser compatible
(un campo obligatorio nuevo, un campo eliminado, un cambio de significado); el menor, si se
agrega algo opcional. Hoy `ScenarioRequest` y `ScenarioResponse` aceptan solo `"1.0.0"`. Llenar
`interval` (A75) no cambia la versión: el campo ya existe y es opcional.

## 8. Preguntas abiertas y limitaciones

- **Cobertura de las entradas.** ¿Una entrada fuera de lo observado en el train debe dar
  `no_estimable`, además de la advertencia? D-06 §7 solo habla de las fracciones. Pregunta para
  Investigación.
- **Covariables de lote.** En D1, `trial_code` y `sampling_day` son entradas del modelo y por eso
  se pueden intervenir. Cambiarlas no describe una intervención nutricional; la interfaz las
  muestra como entradas del modelo, sin más. Pregunta para Investigación: ¿se excluyen del
  vocabulario?
- **Soporte global.** El soporte usa el mínimo y el máximo del train de la corrida, no por día:
  con pocos animales por día, el intervalo diario sería casi un punto.
- **Corridas de demostración.** Las corridas de `tests/fixtures/api/` no tienen valor científico.
  Conectar la plataforma a una corrida de D1 completa queda fuera de A81.
