# Demo de avance en Streamlit

`scripts/demo_app.py` es una aplicación local que muestra los resultados del proyecto hasta la
actividad 41: los grafos desarrollados, el resultado de construir y validar los grafos de D1 y
los baselines (con su comparación frente a las GNN sobre el grafo sintético). Todo sale del código y de los artefactos del repositorio; no hay cifras escritas
a mano.

| Página | Qué muestra | Fuente |
|---|---|---|
| Grafos | Una instancia sintética (escenario basal o intervenido) o un animal de D1, dibujada por tipo de nodo, con sus nodos por tipo, aristas por relación y AGCC. | `generate_scenario_dataset`; registros de D1 (`records_from_tables`) |
| Grafos de D1 | Grafos construidos y entregables, hallazgos de validación por regla, contratos de nodos y aristas, nodos y aristas por tipo, integración de fuentes y distribución de los AGCC medidos. | `reports/graphs/d1_summary.json` (`scripts/summarize_d1_graphs.py`, desde el reporte de `scripts/build_graph.py`) |
| Baselines | Los cinco modelos de referencia de A40 sobre la cohorte sintética: RMSE frente a la media y RMSE, MAE y R² por AGCC en validación y prueba. Debajo, la comparación con las tres GNN evaluadas sobre el grafo sintético con la misma partición. | `reports/baselines/` (`scripts/compare_baselines.py`) y `reports/gnn/synthetic/` (`scripts/report_gnn.py`) |

## Instalación y ejecución

```bash
pip install -e ".[dev,graph,baselines,demo]"
python scripts/fetch_holofood.py   # D1 en data/raw/D1_holofood/ (30 a 60 min la primera vez)
python scripts/build_graph.py      # reporte de los grafos de D1 en artifacts/graphs/D1_holofood/
python scripts/summarize_d1_graphs.py  # resumen versionado en reports/graphs/d1_summary.json
streamlit run scripts/demo_app.py
```

Streamlit abre `http://localhost:8501`. El tema está en `.streamlit/config.toml`.

Los dos últimos pasos solo hacen falta para regenerar el resumen de D1, que ya está versionado:
contiene totales y cuantiles de los AGCC, sin valores por animal. Sin la descarga de D1, la
página "Grafos" usa el fixture de 6 animales de `tests/fixtures/holofood/`. Con la
descarga, "Grafos" lista los 59 animales con los tres AGCC; sus registros se generan en unos
segundos y quedan en caché.

## Publicar en Streamlit Community Cloud

El repositorio es público, así que la app se puede desplegar sin credenciales:

1. Entrar a <https://share.streamlit.io> con la cuenta de GitHub y elegir **Create app**.
2. Repositorio `jvnioo/NutriGraphDT`, rama `main` (o la rama de la demo mientras no se fusione)
   y archivo principal `scripts/demo_app.py`.
3. En **Advanced settings**, Python 3.12.
4. **Deploy**.

Community Cloud instala `scripts/requirements.txt`, que está junto al punto de entrada:
PyTorch para CPU (sin librerías CUDA), torch-geometric, Pydantic, PyYAML, Streamlit y Plotly. El
proyecto no se instala: `demo_app.py` agrega `src/` al path. En el servidor no están
`data/raw/` ni `artifacts/`, así que "Grafos" muestra el fixture de D1 y "Grafos de D1" lee el
resumen versionado. Se verificó en un entorno nuevo de Python 3.12 instalado solo desde ese
archivo (1,3 GB, sin CUDA).

## Pruebas

`tests/unit/test_demo_data.py` cubre las funciones de datos (vista del grafo, AGCC, D1 con
retroceso al fixture, baselines, catálogo de reglas y resumen del reporte de D1).
`tests/integration/test_demo_app.py` dibuja cada página con `streamlit.testing.v1.AppTest`, sin
navegador. Ambos se omiten si faltan los extras.
