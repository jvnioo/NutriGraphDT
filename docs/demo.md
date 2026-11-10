# Demo en Streamlit: grafo sintético frente a D1

`scripts/demo_app.py` es una aplicación local de una sola página que compara el grafo sintético
con el grafo reconstruido con datos reales de D1 (HoloFood). Todo sale del código y de los
artefactos del repositorio; no hay cifras escritas a mano. Lo único escrito a mano es por qué
una relación del esquema no está en D1 (#256, sección 1, y #258).

| Sección | Qué muestra | Fuente |
|---|---|---|
| Selectores y tarjetas | Un escenario sintético (basal o intervenido) y un animal de D1 con los tres AGCC; tipos de nodo, relaciones, nodos y aristas de cada uno. | `generate_scenario_dataset`; registros de D1 (`records_from_tables`, agregados a género y con las aristas de #175) |
| Esquema | El esquema v1 dibujado dos veces: el sintético con sus 11 relaciones y D1 con cada relación presente, como limitación declarada o fuera de D1. El motivo aparece al pasar el cursor. | `ALLOWED_RELATIONS` y `nutrigraphdt.demo.graph_comparison` |
| Instancias | Las dos instancias dibujadas por tipo de nodo. El trazo y el color de cada arista dicen su estado de evidencia (DS-01). En D1 se elige cuántos taxones mostrar. | Registros de cada grafo; estilos en `nutrigraphdt.explainability.style` |
| Aristas por relación | Las 11 relaciones con sus aristas en cada instancia, el mínimo y el máximo por grafo en los 185 grafos de D1, la evidencia (estado · método · fuente) y el motivo. | Registros y `reports/graphs/d1_summary.json` |
| Nodos y atributos por tipo | Nodos por tipo en cada instancia y en la cohorte de D1, y las columnas numéricas de `x` que recibe el modelo en cada grafo. | `derive_schema` para el sintético; `feature_columns` del resumen de D1 |
| Instancia y AGCC objetivo | Metadatos de las dos instancias y los tres AGCC objetivo (mmol/kg), con la mediana y el rango intercuartílico de D1. | `instance_info`, `targets_of` y los cuantiles del resumen de D1 |

## Instalación y ejecución

```bash
pip install -e ".[dev,graph,demo]"
python scripts/fetch_holofood.py   # D1 en data/raw/D1_holofood/ (30 a 60 min la primera vez)
python scripts/build_graph.py      # reporte de los grafos de D1 en artifacts/graphs/D1_holofood/
python scripts/summarize_d1_graphs.py  # resumen versionado en reports/graphs/d1_summary.json
streamlit run scripts/demo_app.py
```

Streamlit abre `http://localhost:8501`. El tema está en `.streamlit/config.toml`.

Los dos últimos pasos solo hacen falta para regenerar el resumen de D1, que ya está versionado:
contiene totales, columnas de atributos y cuantiles de los AGCC, sin valores por animal. Sin la
descarga de D1, la página usa el fixture de 6 animales de `tests/fixtures/holofood/`; con la
descarga, lista los 59 animales con los tres AGCC. Sus registros se generan en unos segundos y
quedan en caché.

## Publicar en Streamlit Community Cloud

El repositorio es público, así que la app se puede desplegar sin credenciales:

1. Entrar a <https://share.streamlit.io> con la cuenta de GitHub y elegir **Create app**.
2. Repositorio `jvnioo/NutriGraphDT`, rama `main` y archivo principal `scripts/demo_app.py`.
3. En **Advanced settings**, Python 3.12.
4. **Deploy**.

Community Cloud instala `scripts/requirements.txt`, que está junto al punto de entrada:
PyTorch para CPU (sin librerías CUDA), torch-geometric, Pydantic, PyYAML, Streamlit y Plotly. El
proyecto no se instala: `demo_app.py` agrega `src/` al path. En el servidor no están
`data/raw/` ni `artifacts/`, así que la página usa el fixture de D1 para las instancias y el
resumen versionado para la cohorte.

## Pruebas

`tests/unit/test_demo_graph_comparison.py` cubre las tablas y figuras de la comparación;
`tests/unit/test_demo_data.py`, las funciones de datos (vista del grafo, AGCC, D1 con retroceso
al fixture, catálogo de reglas y resumen del reporte de D1).
`tests/integration/test_demo_app.py` dibuja la app con `streamlit.testing.v1.AppTest`, sin
navegador. Se omiten si faltan los extras.
