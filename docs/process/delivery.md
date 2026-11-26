# Validación del sistema completo con la configuración de entrega (A117, #347)

- **Comando:** `python scripts/run_delivery.py` (sin red ni `data/raw/`; unos 10 s en CPU).
- **Configuración:** [`configs/delivery.json`](../../configs/delivery.json).
- **Reporte:** [`reports/delivery/report.md`](../../reports/delivery/report.md) y `results.json`.
- **Código:** `nutrigraphdt.delivery`; prueba en `tests/integration/test_delivery_pipeline.py`.

> **Datos sintéticos.** Los «datos de referencia» del sistema completo son la cohorte sintética y
> el catálogo de escenarios (A93). D1 no lo es, porque su grafo no tiene el flujo completo (#256,
> [alcance](final-scope.md)). Los targets sintéticos no dependen de la dieta ni del aditivo: el
> pipeline demuestra que el flujo funciona y se reproduce, no efectos biológicos.

## Qué corre

1. **Datos.** `build_synthetic_cohort(20, first_seed=1)` y `validate_graph`.
2. **Grafo.** Los `HeteroData` de los 20 animales con la base de escenarios de la plataforma.
3. **Modelo.** `homo_sage` sin restricciones (`configs/training/api_fixture.json`) y con la
   restricción D-06 `d06.hydrogen.propionate_bound` y λ = 0,1
   (`configs/training/api_fixture_constrained.json`; λ del barrido sintético). Test: los 4 últimos
   animales. Las corridas nuevas quedan en `artifacts/delivery/` (sin versionar).
4. **Reproducibilidad.** Las predicciones de cada corrida nueva se comparan con las de la corrida
   congelada que usa la plataforma (`tests/fixtures/api/frozen_runs/`), con tolerancia
   `reproducibility_atol`.
5. **Simulación.** Cada escenario de `configs/scenarios/` con `compare_scenario`, contra su estado
   esperado.
6. **Explicación.** GNNExplainer sobre `crude-protein-270`, validado con el contrato.

**La corrida de entrega es la corrida congelada de la plataforma**: el pipeline la vuelve a
entrenar desde cero y verifica que sale igual. Por eso la Web App (`configs/platform.json`) no
cambia de corrida.

## Comparación con las corridas sintéticas previas (A117-P2)

El reporte compara las métricas de test de la entrega con A68-P2 (#185, CV de 10 semillas × 5
folds con 60 animales) y cita A45-3 (#103) como contexto, porque usaba otro objetivo. La tasa de
violación de D-06 (A73, #272) se calcula sobre las predicciones de cada corrida. Cada diferencia
lleva su explicación en la sección 5 del reporte; una desviación sin explicar (por ejemplo, una
corrida que no se reproduce o un escenario con otro estado) hace que el comando termine con código
1 y debe registrarse como Issue (A117-P3).
