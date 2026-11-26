# Web App en Streamlit (A88, #297)

`scripts/demo_app.py` abre la Web App de NutriGraphDT. Solo arma la navegación: las páginas, el
layout, el estado de sesión y la caché del motor están en `nutrigraphdt.demo`
(`nutrigraphdt.demo.app`).

> **Datos sintéticos.** La plataforma trabaja con la cohorte sintética y la corrida sintética
> congelada; no describe animales reales y un escenario no es un efecto causal. Todas las páginas
> lo dicen en un rótulo permanente. Ver [alcance de la etapa final](process/final-scope.md).

## Páginas

| Página | Estado | Actividad |
|---|---|---|
| Inicio | Qué es la plataforma, la corrida activa y las páginas | A88 |
| Escenario | Catálogo de referencia o formulario, y la comparación basal frente a intervenido con el mismo modelo (se describe abajo) | A90 (#302), A96 (#314) |
| Resultados | AGCC basal frente a intervenido con intervalo, calidad del modelo y exportación (se describe abajo) | A101 (#329) |
| Grafo | El grafo heterogéneo del escenario activo, con filtros y leyenda de evidencia (se describe abajo) | A97 (#320) |
| Explicación | Importancias del explicador y subgrafo de los nodos más importantes, con sus advertencias (se describe abajo) | A104 (#334) |
| Sintético frente a D1 | Por qué la plataforma usa datos sintéticos (se describe abajo) | #296 |
| Simulador (A81, demostración) | El simulador de A81 (se describe abajo); lo reemplaza la página Escenario | A81 (#286) |

**Layout y estado.** Cada página se dibuja entre un encabezado con el rótulo «Datos sintéticos: no
describen animales reales» y un pie con la versión del contrato de la API, la corrida activa y el
commit con que se entrenó. El escenario en edición, el último resultado y la corrida activa son
claves tipadas de `nutrigraphdt.demo.state` y se conservan al cambiar de página. El botón
**Reiniciar el escenario** de la barra lateral los borra.

**Corrida activa.** La elige `configs/platform.json` (clave `run`) o la variable de entorno
`NUTRIGRAPHDT_RUN`, sin tocar código; debe ser una corrida de `nutrigraphdt.api.DEMO_RUNS`. Hoy es
`synthetic`: la corrida congelada de `tests/fixtures/api/frozen_runs/synthetic` (`homo_sage`,
cohorte sintética de 20 animales, semilla 0, fold 0). La corrida de entrega se registra en A117.
El `ScenarioEngine` se carga una vez por proceso del servidor (`st.cache_resource`) y `run.json`,
las métricas y la versión del contrato se leen con `st.cache_data`.

## Escenario (A90)

El formulario (`nutrigraphdt.demo.form`) parte de un animal de la cohorte sintética y lo prellena
con sus valores. Solo ofrece lo que la corrida conoce: la especie y el segmento de su cohorte
(`chicken` y `cecum`, marcadores provisionales de DS-01), los componentes de la dieta y las
covariables numéricas del huésped de su vocabulario, y los cinco aditivos del catálogo sintético
con la unidad de dosis que fija cada uno. La corrida solo admite la dosis del probiótico de su
cohorte, en UFC/kg; elegir otro aditivo se rechaza con el motivo, porque su dosis está en mg/kg.

Solo los valores que cambian quedan declarados en `intervention`. Las reglas de validación son las
del contrato (`nutrigraphdt.api`) y del motor (`ScenarioBase.derive`); el formulario solo traduce
cada rechazo a un mensaje que nombra el campo y el motivo. Una respuesta `no_estimable` se muestra
con sus motivos y sin cifras.

## Integración con el motor (A96)

La página Escenario habla con el motor solo por `nutrigraphdt.demo.service`, que usa
`nutrigraphdt.api` y `nutrigraphdt.simulation`:

- **Corrida.** Se elige entre las dos corridas sintéticas congeladas: `synthetic` (sin
  restricciones) y `synthetic_constrained` (misma cohorte, partición y semilla, entrenada con la
  restricción D-06 `d06.hydrogen.propionate_bound` y λ = 0,1, la que eligió el barrido sintético
  para `homo_sage`). Cada motor se carga una vez por proceso.
- **Escenario.** Del catálogo de referencia (`configs/scenarios/`, A93) o del formulario (A90).
  `service.prepare` arma la instancia derivada en memoria y la valida con `validate_graph`; nada se
  escribe en disco.
- **Resultado.** `service.simulate` predice el escenario y el basal del mismo animal con
  `compare_scenario` y devuelve `SimulationResult`: la comparación con la versión del contrato, la
  corrida, el commit con que se entrenó, el `dataset_id` y el rótulo de datos sintéticos. Se
  descarga como JSON y se lee de vuelta sin pérdida (`service.from_json`); A101 exporta este mismo
  formato.
- **Errores.** Cada clase de error del motor tiene su mensaje (`service.user_message`); un error
  inesperado se informa sin traza.

**Tiempo de respuesta** (25-11-2026, Windows 11, CPU, Python 3.13, PyTorch 2.15 CPU, PyG 2.8; motor
ya cargado): un par basal / intervenido de los escenarios del catálogo toma entre 150 y 180 ms con
cualquiera de las dos corridas. Cargar el motor la primera vez toma unos segundos. No hay un tiempo
objetivo aprobado; la cifra queda como referencia.

## Resultados (A101)

La página muestra el último resultado de la sesión (`nutrigraphdt.demo.results`):

- **Gráfico.** Barras basal frente a intervenido por fracción molar y para `ln T`. Las cifras son
  las del JSON de A96. Las barras de error son el intervalo **MC-dropout sin calibrar** del modelo
  congelado (`ScenarioEngine.interval`: 30 pasadas con semilla fija, nivel 0,8, los valores de
  A75), calculado para cada predicción estimable. Si una predicción no tiene intervalo, no se
  dibuja banda y la página lo dice; un lado `no_estimable` no se dibuja. La calibración en la
  cohorte sintética queda en #391.
- **Calidad del modelo.** Métricas de test de `metrics.csv` de la corrida, λ y restricciones de su
  `run.json`, y la tasa de violación de las restricciones D-06 (A73) calculada con
  `evaluate_constraints` sobre su `predictions.csv`. Ninguna cifra está escrita a mano. Al lado,
  las advertencias: datos sintéticos, asociación no es causalidad, qué es «no estimable» y que la
  corrida es de demostración.
- **Exportación.** JSON (el `SimulationResult` de A96, se vuelve a cargar sin pérdida) y CSV con
  una fila por AGCC (y `ln T`) y escenario, con contrato, corrida, `run_id`, commit y rótulo.

## Explicación (A104)

`nutrigraphdt.demo.explanation` ejecuta GNNExplainer (30 épocas, semilla elegible) sobre la
instancia del escenario tal como la recibe el modelo congelado (`ScenarioEngine.model_input`:
alineada, codificada y escalada con el `FeatureScaler` de la corrida), con la referencia real de
la corrida, y valida la salida con el contrato de explicaciones. El resultado queda en caché por
corrida, escenario, salida y semilla.

La corrida es `homo_sage`, que convierte el grafo a homogéneo: las máscaras de aristas no llegan a
ninguna capa (`docs/models/explainers-poc.md`). Por eso se explican nodos y atributos, y la página
lo dice. Muestra la importancia por tipo de nodo en barras y el subgrafo de los 10 nodos más
importantes con el visualizador de A97; las aristas de ese subgrafo son las del grafo entre esos
nodos, con su trazo de evidencia, no aristas importantes.

Junto a la explicación, siempre: asociación no es causalidad (A71-P3), en datos sintéticos una
importancia describe al modelo y no un mecanismo biológico, cada arista conserva su evidencia y
las hipotéticas no tienen respaldo (C-03), y la importancia depende de la semilla (A71-P2).

**Tiempo** (25-11-2026, Windows 11, CPU, PyTorch 2.15, PyG 2.8; animal 0017): entre 0,2 y 0,8 s
por explicación con el motor ya cargado; la página muestra el de cada una.

## Grafo (A97)

La página dibuja la instancia derivada del escenario guardado en la sesión, o el basal del primer
animal de test si no hay uno. La arma `nutrigraphdt.demo.graph_viewer` en memoria con
`ScenarioBase.derive`, sin escribir en disco, y la dibuja `plots.graph_figure`: color por tipo de
nodo (`ui.NODE_COLORS`) y trazo por evidencia (`nutrigraphdt.explainability.style`), sin otra
definición de estilos.

- **Filtros** por tipo de nodo y por relación.
- **Leyenda** por relación: aristas, evidencia de la arista (en el grafo sintético, siempre
  «sintética») y estado estructural de la relación en el esquema (`ALLOWED_RELATIONS`). Una
  relación hipotética, como `additive → modulates → taxon`, se dibuja con el trazo «hipotética: sin
  respaldo empírico» (C-03, #243) aunque su arista sea sintética.
- **Muestreo de taxones** determinista: los de más aristas en la vista filtrada y, entre ellos, los
  más abundantes; el empate se rompe por `node_id`. La página dice «N de M taxones».

**Tiempo de dibujo** (25-11-2026, Windows 11, CPU, Python 3.13, Plotly 7.2, Streamlit 1.67; animal
`synthetic:sample:0017`, 8 tipos de nodo, 10 taxones y 81 aristas): armar la vista y la figura
toma entre 20 y 80 ms. La página muestra el tiempo de cada dibujo.

## Sintético frente a D1

La página **Sintético frente a D1** compara el grafo sintético con el grafo reconstruido con datos
reales de D1 (HoloFood). Todo sale del código y de los artefactos del repositorio; no hay cifras
escritas a mano. Lo único escrito a mano es por qué una relación del esquema no está en D1 (#256,
sección 1, y #258).

| Sección | Qué muestra | Fuente |
|---|---|---|
| Selectores y tarjetas | Un escenario sintético (basal o intervenido) y un animal de D1 con los tres AGCC; tipos de nodo, relaciones, nodos y aristas de cada uno. | `generate_scenario_dataset`; registros de D1 (`records_from_tables`, agregados a género y con las aristas de #175) |
| Esquema | El esquema v1 dibujado dos veces: el sintético con sus 11 relaciones y D1 con cada relación presente, como limitación declarada o fuera de D1. El motivo aparece al pasar el cursor. | `ALLOWED_RELATIONS` y `nutrigraphdt.demo.graph_comparison` |
| Instancias | Las dos instancias dibujadas por tipo de nodo. El trazo y el color de cada arista dicen su estado de evidencia (DS-01). En D1 se elige cuántos taxones mostrar. | Registros de cada grafo; estilos en `nutrigraphdt.explainability.style` |
| Aristas por relación | Las 11 relaciones con sus aristas en cada instancia, el mínimo y el máximo por grafo en los 185 grafos de D1, la evidencia (estado · método · fuente) y el motivo. | Registros y `reports/graphs/d1_summary.json` |
| Nodos y atributos por tipo | Nodos por tipo en cada instancia y en la cohorte de D1, y las columnas numéricas de `x` que recibe el modelo en cada grafo. | `derive_schema` para el sintético; `feature_columns` del resumen de D1 |
| Instancia y AGCC objetivo | Metadatos de las dos instancias y los tres AGCC objetivo (mmol/kg), con la mediana y el rango intercuartílico de D1. | `instance_info`, `targets_of` y los cuantiles del resumen de D1 |

### Alcance de los datos

La comparación muestra por qué la plataforma y la entrega final usan datos sintéticos: el grafo de
D1 tiene 3 de las 11 relaciones del esquema y no permite simular una dieta o un aditivo a través
del microbioma. Las páginas nuevas de la Web App (A88 a A104) trabajan con la cohorte sintética y
rotulan sus resultados como sintéticos. Ver [`process/final-scope.md`](process/final-scope.md).

## Simulador (A81, demostración)

La página pide escenarios a una corrida congelada de demostración por `nutrigraphdt.api` (A81,
#286) y no importa nada más del motor. El contrato está en
[`architecture/api-contract.md`](architecture/api-contract.md).

| Sección | Qué muestra | Fuente |
|---|---|---|
| Corrida | La corrida sintética (20 animales) o la del fixture de D1 (6 animales reales), con su rótulo de datos. | `DEMO_RUNS`; corridas de `tests/fixtures/api/frozen_runs/` |
| Escenario | Un ejemplo de `scenarios.json`, o uno propio: el animal base (con su papel en la corrida) y las variables que cambian, prellenadas con el valor observado. | `demo_scenarios`; `ScenarioEngine.variables`, `split_of` y `base.values_of` |
| Resultado | Si es estimable, las tres fracciones y `T`, y la predicción basal del mismo animal. Si no, «no estimable» con los motivos y sin números. Siempre, la advertencia de que un escenario no es un efecto causal y las demás advertencias. | `ScenarioResponse` |
| Soporte y corrida | El intervalo del soporte empírico aplicado y los datos de la corrida que predijo. El intervalo predictivo queda para A75. | `ScenarioResponse.support` y `.model` |

Las corridas son de demostración y sus predicciones no tienen valor científico. La lista de
pruebas manuales está en [`process/platform-manual-test.md`](process/platform-manual-test.md).

## Instalación y ejecución

Solo con datos sintéticos, sin red ni descarga de D1:

```bash
pip install -e ".[dev,graph,baselines,demo]"
streamlit run scripts/demo_app.py
```

Streamlit abre `http://localhost:8501`. El tema está en `.streamlit/config.toml`. La app arranca
sin `data/raw/` ni `artifacts/`: la corrida congelada y el resumen de D1 están versionados, y la
página **Sintético frente a D1** usa el fixture de 6 animales de `tests/fixtures/holofood/`.

Para cambiar de corrida sin tocar código: `NUTRIGRAPHDT_RUN=<corrida> streamlit run
scripts/demo_app.py`.

**Opcional, solo para regenerar los resultados exploratorios de D1** (no hace falta para la app):

```bash
python scripts/fetch_holofood.py   # D1 en data/raw/D1_holofood/ (30 a 60 min la primera vez)
python scripts/build_graph.py      # reporte de los grafos de D1 en artifacts/graphs/D1_holofood/
python scripts/summarize_d1_graphs.py  # resumen versionado en reports/graphs/d1_summary.json
```

Con la descarga, la página **Sintético frente a D1** lista los 59 animales con los tres AGCC.

## Publicar en Streamlit Community Cloud

El repositorio es público, así que la app se puede desplegar sin credenciales:

1. Entrar a <https://share.streamlit.io> con la cuenta de GitHub y elegir **Create app**.
2. Repositorio `jvnioo/NutriGraphDT`, rama `main` y archivo principal `scripts/demo_app.py`.
3. En **Advanced settings**, Python 3.12.
4. **Deploy**.

Community Cloud instala `scripts/requirements.txt`, que está junto al punto de entrada:
PyTorch para CPU (sin librerías CUDA), torch-geometric, Pydantic, PyYAML, scikit-learn (lo usa la
cohorte sintética del simulador), Streamlit y Plotly. El
proyecto no se instala: `demo_app.py` agrega `src/` al path. En el servidor no están
`data/raw/` ni `artifacts/`, así que la página usa el fixture de D1 para las instancias y el
resumen versionado para la cohorte.

## Pruebas

`tests/unit/test_demo_graph_comparison.py` cubre las tablas y figuras de la comparación;
`tests/unit/test_demo_data.py`, las funciones de datos (vista del grafo, AGCC, D1 con retroceso
al fixture, catálogo de reglas y resumen del reporte de D1).
`tests/integration/test_demo_app.py` dibuja la app con `streamlit.testing.v1.AppTest`, sin
navegador: abre cada página con su rótulo y su pie, comprueba que las pendientes no muestran
datos y que el estado se conserva entre páginas y se borra al reiniciar.
`tests/unit/test_demo_platform.py` cubre la corrida activa y cuenta las cargas del motor. Además, `tests/integration/test_demo_scenario_page.py` recorre el simulador (ejemplos
estimables y no estimables, escenario propio, errores de contrato y corrida de D1). El motor y el
contrato se prueban en `tests/integration/test_api_engine.py` y `tests/unit/test_api_contract.py`.
Se omiten si faltan los extras.

La suite E2E (`tests/e2e/`, A105) recorre la app completa en una sola sesión: `pytest -m e2e`.
Sus casos están en [`process/e2e-cases.md`](process/e2e-cases.md) y su registro en
[`reports/e2e/report.md`](../reports/e2e/report.md) (`python scripts/report_e2e.py`).
