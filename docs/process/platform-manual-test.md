# Pruebas manuales de la plataforma

Lista repetible para probar a mano la demo (`scripts/demo_app.py`) antes de entregarla. Cubre
las dos páginas y los textos que se prestan a malinterpretación (A81-P3, #289). Cada defecto
encontrado se corrige en A81-P4 (#290) o queda en una Issue.

## Cómo ejecutarla

```bash
pip install -e ".[dev,graph,baselines,demo]"
streamlit run scripts/demo_app.py
```

Abra `http://localhost:8501` y recorra los pasos en orden. En cada uno, anote el resultado
obtenido; si no coincide con el esperado, registre el defecto en la tabla del final.

## Registro de ejecución

| Campo | Valor |
|---|---|
| Fecha | 2026-11-13 |
| Versión | `nutrigraphdt 0.1.0.dev0` |
| Commit | rama `feat/a81-platform-api`, sobre `4543337` (`main`) |
| Entorno | Windows 11, Python 3.12.0, torch 2.14.1+cpu, torch-geometric 2.8.0.post1, Streamlit 1.67.0 |
| Datos | D1 completo en `data/raw/` (59 animales con los tres AGCC) y fixtures de `tests/fixtures/api/` |
| Cómo se ejecutó | `streamlit run` local (las dos rutas responden 200) y cada paso con `streamlit.testing.v1.AppTest`, que ejecuta la app completa sin dibujarla |
| Navegador | **Pendiente.** La captura con Edge 150 sin interfaz salió en blanco (Streamlit no dibuja en ese modo), así que falta una pasada en un navegador de escritorio para la columna «Navegador» |

## Página 1 · Sintético frente a D1 (`/comparacion`)

| # | Paso | Resultado esperado | Obtenido (AppTest) | Navegador |
|---|---|---|---|---|
| C1 | Abrir la app. | Abre en esta página sin excepciones; la barra lateral lista «Sintético frente a D1» y «Simulador de escenarios». | Sin excepciones; las dos páginas están en `st.navigation`. | |
| C2 | Leer las tarjetas. | «Relaciones» dice `11 → 3`: el grafo de D1 no se presenta como completo. | `11 → 3`. | |
| C3 | Revisar los selectores. | Escenario sintético (basal o intervenido) y animal de D1, con cuántos animales tienen los tres AGCC. | 2 escenarios sintéticos; «Animal de D1 (59 con los tres AGCC)». | |
| C4 | Buscar textos que presenten D1 como completo. | Ninguno; la bajada dice que D1 «solo tiene las relaciones con respaldo en esos datos». | No hay menciones de «completo»; la bajada lo dice así. | |
| C5 | Buscar textos que presenten un escenario como efecto causal. | Ninguno; la tabla de AGCC dice que el sintético es ilustrativo y no se compara con D1 como resultado. | Ninguna mención causal; la nota de AGCC está. | |
| C6 | Cambiar el animal de D1 y el control «Taxones mostrados». | La instancia y la tabla se actualizan sin errores. | Cubierto por `tests/integration/test_demo_app.py` (abre sin excepciones). | |

## Página 2 · Simulador de escenarios (`/simulador`)

| # | Paso | Resultado esperado | Obtenido (AppTest) | Navegador |
|---|---|---|---|---|
| S1 | Abrir la página. | Corrida sintética, insignia «Datos sintéticos» y la nota «Modelo de demostración, sin valor científico». | Así; ejemplo `synthetic-basal` elegido. | |
| S2 | Ejemplo «basal del animal 0017». | «Estimable»; tres fracciones en %, `Total T` en mmol/kg; advertencia causal arriba; advertencias de datos sintéticos y de escenario basal. | Estimable; acetato 61,7 %, propionato 16,2 %, n-butirato 22,0 %; T = 84,5 mmol/kg; las tres advertencias. | |
| S3 | Ejemplo «dosis del aditivo 0». | «No estimable» con los motivos; **ningún número** de fracciones ni de T; advertencia de que la dosis 0 no se observó en el train. | No estimable; motivos «acetate = 0 fuera de [0.500372, 0.734653]» y otros dos; sin tarjetas ni T; advertencia de cobertura. | |
| S4 | «Escenario propio», sin variables. | Animal base preseleccionado entre los de test, rotulado «· test»; escenario basal estimable. | `synthetic:sample:0017 · test`; estimable. | |
| S5 | Agregar `Dieta: crude_protein` con 190. | El campo se prellena con el valor observado (215); estimable, con la tabla «basal (predicho) / escenario (predicho)», la nota de que la diferencia no es un efecto y la advertencia de que 190 no se observó en el train. | Prellenado con 215; con 190, estimable, tabla, nota y advertencia de cobertura. | |
| S6 | Poner un valor negativo (por ejemplo, dosis −1). | Error del contrato: «no puede ser negativo»; sin resultado. | Así. | |
| S7 | Cambiar a «Fixture de D1 (6 animales reales)». | Insignia «Datos reales»; descripción con «3 de las 11 relaciones»; ejemplo `d1-basal` estimable con las advertencias de D1 parcial y de fixture. | Así. | |
| S8 | Ejemplo «raza Cobb». | «No estimable» con el motivo (acetato bajo el mínimo del train), sin números. | Así. | |
| S9 | Abrir «Respuesta del contrato (JSON)». | JSON con `contract_version` 1.0.0, `status`, `model`, `support` y `warnings`; en un no estimable, `fractions`, `log_total` e `interval` en `null`. | Así (`ScenarioResponse.model_dump`). | |
| S10 | Revisar el texto de toda la página. | Ningún texto presenta un escenario como efecto causal: la bajada, la advertencia y la nota de la tabla basal lo niegan. El intervalo predictivo figura como no calculado (A75). | Así. | |

Los pasos S1 a S8 también están automatizados en `tests/integration/test_demo_scenario_page.py`.

## Defectos

| ID | Severidad | Defecto | Estado |
|---|---|---|---|
| P4-1 | Alta (datos erróneos) | El motor predecía con valores imposibles por definición: composición negativa, más de 1000 g/kg, dosis o edad negativas. | Corregido en #290: `ScenarioContractError`; regresión en `test_engine_rejects_physically_impossible_values`. Repetido S6. |
| P4-2 | Media (interpretación) | Un escenario con una entrada que la corrida nunca vio (en la cohorte sintética toda la dieta es constante) salía «estimable» sin aviso. | Corregido en #290: advertencia `COVERAGE_WARNING`, que no cambia el estado (D-06 §7). Si debe dar `no_estimable` queda como pregunta abierta en `docs/architecture/api-contract.md` §8. Repetidos S3 y S5. |
| P4-3 | Baja (trazabilidad) | El `run.json` de la corrida `d1_fixture` declaraba `training_config.dataset_id = synthetic_cohort` y un `split_file` inexistente. | Corregido en #290: cada corrida registra su conjunto y su `plan.json`. Corridas regeneradas, idénticas byte a byte en checkpoint y predicciones. |
| P4-4 | Media (despliegue) | En Streamlit Community Cloud faltaba scikit-learn, que la corrida sintética necesita: el simulador no cargaría. | Corregido en #290: `scripts/requirements.txt`. No se probó en Community Cloud. |

No quedan defectos abiertos de esta ejecución. Queda pendiente la pasada en navegador.
