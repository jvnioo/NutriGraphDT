# Demo de avance en Streamlit

`scripts/demo_app.py` es una aplicación local que muestra los resultados del proyecto hasta la
actividad 41: los grafos desarrollados, el resultado de construir y validar los grafos de D1 y
los baselines. Todo sale del código y de los artefactos del repositorio; no hay cifras escritas
a mano.

| Página | Qué muestra | Fuente |
|---|---|---|
| Grafos | Una instancia sintética (escenario basal o intervenido) o un animal de D1, dibujada por tipo de nodo, con sus nodos por tipo, aristas por relación y AGCC. | `generate_scenario_dataset`; registros de D1 (`records_from_tables`) |
| Grafos de D1 | Grafos construidos y entregables, hallazgos de validación por regla, contratos de nodos y aristas, nodos y aristas por tipo, integración de fuentes y distribución de los AGCC medidos. | `artifacts/graphs/D1_holofood/report.json` (`scripts/build_graph.py`) |
| Baselines | Los cinco modelos de referencia de A40 sobre la cohorte sintética: RMSE frente a la media y RMSE, MAE y R² por AGCC en validación y prueba. | `reports/baselines/` (`scripts/compare_baselines.py`) |

## Instalación y ejecución

```bash
pip install -e ".[dev,graph,baselines,demo]"
python scripts/fetch_holofood.py   # D1 en data/raw/D1_holofood/ (30 a 60 min la primera vez)
python scripts/build_graph.py      # reporte de los grafos de D1 en artifacts/graphs/D1_holofood/
streamlit run scripts/demo_app.py
```

Streamlit abre `http://localhost:8501`. El tema está en `.streamlit/config.toml`.

Sin la descarga de D1, la página "Grafos" usa el fixture de 6 animales de
`tests/fixtures/holofood/` y la página "Grafos de D1" indica cómo generar el reporte. Con la
descarga, "Grafos" lista los 59 animales con los tres AGCC; sus registros se generan en unos
segundos y quedan en caché.

## Pruebas

`tests/unit/test_demo_data.py` cubre las funciones de datos (vista del grafo, AGCC, D1 con
retroceso al fixture, baselines, catálogo de reglas y resumen del reporte de D1).
`tests/integration/test_demo_app.py` dibuja cada página con `streamlit.testing.v1.AppTest`, sin
navegador. Ambos se omiten si faltan los extras.
