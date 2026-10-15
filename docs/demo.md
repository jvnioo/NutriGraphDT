# Demo de avance en Streamlit

`scripts/demo_app.py` es una aplicación local que recorre lo construido en NutriGraphDT con el
código y los artefactos reales del repositorio. Está pensada para mostrar el avance del
proyecto (por ejemplo, al profesor guía), no para publicar resultados.

## Principios

- **Todo sale del repositorio.** Cada página llama a `nutrigraphdt` o lee un reporte versionado;
  no hay cifras escritas a mano.
- **Funciona sin la descarga completa de D1.** Usa la cohorte sintética (se genera al vuelo), el
  fixture de D1 (`tests/fixtures/holofood/`, 6 animales reales), la partición versionada y los
  reportes de `reports/`.
- **Cada número dice de dónde viene.** Las insignias "Sintético" y "Real · D1" y las notas de
  cautela repiten las limitaciones de cada reporte. Lo que aún no existe (la GNN en D1, la tabla
  GNN vs. baselines) aparece como pendiente.
- **Solo lectura.** La app no modifica el repositorio. El entrenamiento en vivo escribe en
  `runs/demo/`, que Git ignora.

## Instalación y ejecución

```bash
pip install -e ".[dev,graph,baselines,demo]"
streamlit run scripts/demo_app.py
```

Streamlit abre `http://localhost:8501`. El tema está en `.streamlit/config.toml`.

**Con GPU.** Para entrenar en vivo en GPU, lance la app desde un entorno con PyTorch para CUDA o
ROCm, como el que describe [gnn-training.md](models/gnn-training.md#gpu-opcional):

```bash
~/.venvs/nutrigraphdt-rocm/bin/pip install "streamlit>=1.50" "plotly>=5"
~/.venvs/nutrigraphdt-rocm/bin/streamlit run scripts/demo_app.py
```

La página "Entrenamiento" ofrece `cuda` solo si PyTorch ve una GPU.

## Preparar la presentación

Tres comandos dejan listos los artefactos locales que la demo muestra si existen:

```bash
python scripts/export_board_snapshot.py      # foto del tablero → reports/progress/
python scripts/overfit_gnn.py                # curvas de sobreajuste → artifacts/gnn-overfit/
python scripts/train_gnn.py --model hetero_gat --dataset synthetic   # una corrida → runs/
```

`export_board_snapshot.py` usa GitHub CLI (`gh`) autenticado y guarda solo número, título,
estado, etiquetas y fechas de cada Issue: la app no necesita red ni credenciales durante la
presentación. Sin esos artefactos, las páginas correspondientes indican cómo generarlos.

## Páginas

| Página | Qué muestra | Fuente |
|---|---|---|
| Resumen | Qué es el proyecto, cifras clave, el flujo de punta a punta y qué falta. | Partición, reportes, foto del tablero |
| Datos | D1 HoloFood (diseño, variables usadas, AGCC del fixture) y la cohorte sintética con su escenario de intervención. | `d1_fixture`, `generate_scenario_dataset`, `build_synthetic_cohort` |
| Explorador del grafo | Una instancia (sintética basal o intervenida, o un animal de D1) como grafo en columnas por tipo, con atributos al pasar el cursor. | `graph_view` sobre los registros del grafo |
| Validación | Reglas de integridad y hallazgos del fixture de D1 y del sintético; catálogo completo. | `ValidationReport.to_dict()`, `graph-integrity-rules.md` |
| Partición y baselines | Partición de D1 por corral y los 5 baselines en D1 y en el sintético. | `configs/splits/`, `reports/baselines/` |
| Modelos GNN | Las tres variantes, parámetros, relaciones por capa y prueba de sobreajuste. | `build_model`, `layer_edge_types`, `artifacts/gnn-overfit/` |
| Entrenamiento | Corridas registradas (curvas, métricas, medido vs. predicho, `run.json`) y entrenamiento en vivo en CPU o GPU. | `runs/`, `run_training` |
| Proceso | Tareas por actividad, PR, tests y reglas de trabajo. | `reports/progress/board_snapshot.json` |

## Guion sugerido (10 minutos)

1. **Resumen (1 min).** El problema y el flujo; señalar que la evaluación en D1 es lo pendiente.
2. **Datos (1 min).** D1 es real pero pequeño y desbalanceado (59 animales con AGCC); el
   sintético existe para probar el flujo completo.
3. **Explorador (2 min).** Comparar el escenario basal con un animal de D1: en D1 los taxones
   están aislados porque falta la anotación taxón → función.
4. **Validación (1 min).** Ningún grafo llega al modelo sin pasar las reglas; las advertencias de
   D1 están explicadas.
5. **Baselines (1,5 min).** El piso en D1 es bajo y `val` es muy pequeño: por eso se reporta con
   cautela.
6. **Modelos (1,5 min).** Las tres variantes y la prueba de sobreajuste: pueden aprender.
7. **Entrenamiento (1,5 min).** Lanzar `hetero_gat` en GPU (unos 15 s) y recorrer la corrida
   registrada: todo queda trazable en `runs/`.
8. **Proceso (0,5 min).** Tareas cerradas, revisiones y costo cero.

## Pruebas

`tests/unit/test_demo_data.py` cubre las funciones de datos y
`tests/integration/test_demo_app.py` dibuja cada página con `streamlit.testing.v1.AppTest`
(sin navegador). Ambos se omiten si faltan los extras.
