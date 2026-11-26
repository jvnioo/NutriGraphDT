# Casos de prueba E2E de la Web App (A105, #338)

- **Suite:** `tests/e2e/test_web_app_flow.py`, marcador `e2e` (`pytest -m e2e`).
- **Reporte:** `python scripts/report_e2e.py` → [`reports/e2e/report.md`](../../reports/e2e/report.md).
- **Datos:** cohorte sintética y corridas sintéticas congeladas (`tests/fixtures/api/frozen_runs/`);
  escenarios del catálogo [`configs/scenarios/`](../../configs/scenarios/README.md). Sin red ni
  navegador.

Cada caso es una prueba cuyo nombre empieza por su identificador (`test_e2e_NN_…`). El recorrido
usa una sola sesión de Streamlit: lo que una página guarda lo leen las siguientes.

| Caso | Escenario | Pasos | Resultado esperado |
|---|---|---|---|
| E2E-01 | `crude-protein-270` | Inicio → Escenario (catálogo, simular) → Resultados → exportar JSON y CSV → Grafo → Explicación | Estimable; resultados con intervalo «calibrado» (#391) y advertencias; JSON vuelve a cargarse sin pérdida; CSV con 8 filas rotuladas; el grafo es el del escenario y dice «N de 10 taxones»; la explicación se muestra con sus advertencias. |
| E2E-02 | Todo el catálogo | Escenario (catálogo, simular) → Resultados | Cada escenario da su `expected_status`; uno no estimable lo dice en Resultados. |
| E2E-03 | Dosis 0 (formulario) | Escenario (formulario, dosis 0, simular) → Resultados | No estimable; sin cifras del intervenido ni «Total T». |
| E2E-04 | Proteína 195 y 270 g/kg (extremos del diccionario sintético) | Escenario (formulario) | Estimable, con la advertencia de que el valor no se observó en el train. |
| E2E-05 | `additive-dose-control` (fuera de soporte) | Escenario (catálogo) | No estimable, sin diferencias numéricas; motivos del lado intervenido. |
| E2E-06 | Entrada inválida (dosis −1) después de un basal | Escenario (catálogo basal) → formulario con dosis −1 | Error que nombra «Dosis del aditivo», sin traza; el resultado anterior no cambia. |
| E2E-07 | Intervención vacía | Escenario (formulario sin cambios) | Basal: intervención vacía y diferencia cero exacta. |
| E2E-08 | `crude-protein-195` | Simular → Resultados → recargar → volver a Escenario | El escenario y el resultado se conservan. |
| E2E-09 | `crude-protein-270` | Simular → cambiar a la corrida con restricciones | Se vuelve a calcular con `synthetic_constrained` y da el estado esperado. |
| E2E-10 | `crude-protein-270` | Simular → Reiniciar → Resultados | La sesión queda vacía y Resultados dice que no hay resultado. |
| E2E-11 | Sin escenario | Abrir cada página | Ninguna falla; todas llevan el rótulo de datos sintéticos. |

## Defectos encontrados (A105-P3)

| Defecto | Severidad | Caso | Corrección |
|---|---|---|---|
| Al volver a la página Escenario, Streamlit reinicia el selector del catálogo y la página simulaba el primer escenario, pisando el de la sesión. Resultados y Grafo pasaban a mostrar otro escenario. | P0: muestra datos erróneos | E2E-08 | El catálogo simula solo al enviar («Simular escenario») y el selector y el modo se inicializan con el escenario de la sesión. |
| «Reiniciar el escenario» no dejaba la sesión vacía: la página Escenario volvía a simular el escenario por omisión. | P1 | E2E-10 | Igual que el anterior: sin envío no se simula. |

No quedan defectos pendientes de la suite.
