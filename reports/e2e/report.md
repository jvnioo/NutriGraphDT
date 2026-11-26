# Registro de la suite E2E de la Web App (A105-P4, #342)

> **Datos sintéticos.** La suite recorre la app con la cohorte sintética y las corridas sintéticas congeladas. Comprueba el flujo y los contratos, no efectos biológicos.

- **Commit:** `4ddc0e71b21c99a66bf6d93fbe536bfb3282a731`
- **Fecha:** 2026-11-26T00:48:20+00:00
- **Comando:** `pytest -m e2e tests/e2e` (16.0 s)
- **Entorno:** python 3.13.17, platform Windows-11-10.0.26300-SP0, torch 2.15.0+cpu, torch_geometric 2.8.1, streamlit 1.67.0, plotly 7.2.0, pydantic 2.14.4
- **Totales:** 17 pruebas; 17 pasan, 0 fallan, 0 omitidas.

## Casos

| Caso | Pruebas | Pasan | Fallan | Detalle |
|---|---:|---:|---:|---|
| E2E-01 | 1 | 1 | 0 | — |
| E2E-02 | 6 | 6 | 0 | — |
| E2E-03 | 1 | 1 | 0 | — |
| E2E-04 | 2 | 2 | 0 | — |
| E2E-05 | 1 | 1 | 0 | — |
| E2E-06 | 1 | 1 | 0 | — |
| E2E-07 | 1 | 1 | 0 | — |
| E2E-08 | 1 | 1 | 0 | — |
| E2E-09 | 1 | 1 | 0 | — |
| E2E-10 | 1 | 1 | 0 | — |
| E2E-11 | 1 | 1 | 0 | — |

Qué prueba cada caso y los defectos encontrados y corregidos: [`docs/process/e2e-cases.md`](../../docs/process/e2e-cases.md).

Regenerar: `python scripts/report_e2e.py`.
