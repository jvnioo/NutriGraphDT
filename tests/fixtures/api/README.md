# Fixtures de la plataforma (`nutrigraphdt.api`)

Corridas congeladas y escenarios de ejemplo para probar la plataforma de simulación sin red ni la
descarga completa de D1 (A81-P2, #288). Las usan `nutrigraphdt.api.demo` (`DEMO_RUNS` y
`demo_scenarios`), la página **Simulador de escenarios** de la demo y
`tests/integration/test_api_engine.py`.

> **Son corridas de demostración.** Se entrenaron con pocos animales y un máximo de 30 épocas.
> Sus predicciones sirven para probar la plataforma y **no tienen valor científico**.

## Contenido

| Ruta | Datos | Qué es |
|---|---|---|
| `frozen_runs/synthetic/` | **Sintéticos** | Corrida `homo_sage` (`with_inferred`), semilla 0, fold 0, entrenada con la cohorte sintética de 20 animales de `build_synthetic_cohort` (semillas 1 a 20; `dataset_id = synthetic_cohort`). Train: 12 animales; val interno: 4; test: los 4 últimos (`synthetic:sample:0017` a `0020`). |
| `frozen_runs/d1_fixture/` | **Reales** (D1, HoloFood) | Corrida `homo_sage` (`with_inferred`), semilla 0, fold 0, entrenada con los seis animales de `tests/fixtures/holofood/` (`dataset_id = D1_holofood_fixture`). Train: 4; val interno: 1; test: `SAMEA112904810` (Control). |
| `scenarios.json` | Mixto, rotulado por escenario | Seis escenarios de ejemplo, tres por corrida, con el estado que devuelve la corrida: en cada una, un basal y una intervención `estimable`, y una intervención `no_estimable`. |

Cada corrida tiene el formato de `save_compositional_run` (#180): `run.json`, `checkpoint.pt`
(unos 180 KB), `history.csv`, `metrics.csv` y `predictions.csv`, más `plan.json` con la
partición del fold. `run.json` registra la configuración de entrenamiento
(`configs/training/api_fixture.json`, con el `dataset_id` y el `split_file` de esa corrida), el
commit de git y las versiones de Python, PyTorch y PyG.

## Rótulos de los datos

- La corrida `synthetic` y la cohorte de donde salen sus instancias son **sintéticas**: no
  describen animales reales. En esa cohorte, dieta, aditivo y edad son iguales en todos los
  animales; solo varían el peso y el sexo. Por eso cambiar una variable de la dieta o del aditivo
  es extrapolar, y la respuesta lo advierte.
- La corrida `d1_fixture` se entrenó con **animales reales** de D1. Un escenario derivado de uno
  de ellos es una instancia **sintética** (`is_synthetic = true`, `derived_from`, contrato de
  datos v2 §7). El grafo de D1 tiene 3 de las 11 relaciones del esquema v1.
- La respuesta del motor lleva `is_synthetic` y estas advertencias en `warnings`.

## Regenerar

```bash
pip install -e ".[graph,baselines]"
python scripts/build_api_fixtures.py
```

No usa red ni `data/raw/`. Entrena en CPU en unos segundos y es determinista: con el mismo
entorno, el checkpoint y las predicciones salen iguales byte a byte. Solo cambian `run_id`,
`created_at`, `duration_seconds` y el commit registrado. Si cambian las salidas del motor,
actualice `expected_status` en `scenarios.json` y vuelva a correr las pruebas.

No se versionan `data/raw/` ni checkpoints grandes: las dos corridas suman unos 400 KB.
