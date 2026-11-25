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
| Escenario | Pendiente: formulario y predicción basal frente a intervenido | A90 (#302), A96 (#314) |
| Resultados | Pendiente: AGCC, métricas y exportación | A101 (#329) |
| Grafo | Pendiente: visualizador del grafo heterogéneo | A97 (#320) |
| Explicación | Pendiente: subgrafo explicativo | A104 (#334) |
| Sintético frente a D1 | Por qué la plataforma usa datos sintéticos (se describe abajo) | #296 |
| Simulador (A81, demostración) | El simulador de A81 (se describe abajo); lo reemplaza la página Escenario | A81 (#286) |

Las páginas pendientes lo dicen y no muestran datos de relleno.

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
