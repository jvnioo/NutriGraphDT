# Reproducibilidad independiente de una corrida con restricciones (A68-P4, #182)

Corrida elegida: `20261102-041750_hetero_sage_constrained_s0_f0`. Es la evaluación pareada de la
cohorte sintética (#185): `hetero_sage`, brazo restringido (λ = 0,1, cota de D-06), semilla 0 del
plan, fold 0, en GPU (AMD RX 9060 XT, ROCm 7.1, PyTorch 2.13.0), commit `c8e8059` sin cambios
sin confirmar. La cohorte es sintética para que la verificación no dependa de datos descargados.

Se reentrenó con `scripts/reproduce_compositional_run.py` **solo desde archivos versionados**:
el `run.json` original, el plan `configs/splits/synthetic_cohort_cv.json` (verificado por su
SHA-256 canónico, #133) y el generador sintético. No se copió ningún resultado de la corrida
original. Las tolerancias son las de A45-8 y se fijaron antes de comparar: 1e-4 en
`(z_1, z_2, ln T)`, el historial y las violaciones; 1e-5 en `metrics.csv`; 1e-6 relativa en el
escalado; 1e-5 en la recarga del checkpoint (`RELOAD_ATOL`).

| Reproducción | Resultado | Detalle |
|---|---|---|
| [GPU → misma GPU](gpu_to_gpu/) | **Se reproduce** | Historial, predicciones, métricas y violaciones idénticos (diferencia 0). |
| [GPU → CPU](gpu_to_cpu/) | **No se reproduce** | La configuración, los animales, el escalado y la mejor época coinciden, y el checkpoint original recargado en CPU reproduce sus predicciones (1,2·10⁻⁷). Pero el reentrenamiento diverge desde la época 1: hasta 0,15 en `val_loss`, 0,095 en las predicciones y 0,26 pp en el MAE de fracciones. |
| [CPU → misma CPU](cpu_to_cpu/) | **Se reproduce** | Una corrida entrenada en CPU (la de la fila anterior) se reproduce en CPU con diferencia 0. |

**Lectura.** En el mismo dispositivo y con las mismas versiones, la corrida se reproduce
exactamente. Entre CPU y GPU no: el orden de las reducciones en GPU, el generador aleatorio del
dropout en cada dispositivo y la versión de PyTorch (2.13.0 ROCm frente a 2.14.0 CPU) cambian el
camino de la optimización desde la primera época. La recarga del checkpoint sí es portable. Por
eso cada corrida registra su dispositivo y sus versiones en `run.json` (`environment`), y una
verificación debe usar el mismo dispositivo que la original. Esto es reproducibilidad numérica,
no validez científica.

Los `run_id` reproducidos y sus checkpoints quedan en `runs/`, que Git ignora. Las carpetas `gpu/` y `cpu/`
que cita la línea «Generado con» de cada reporte se renombraron a `gpu_to_gpu/` y `gpu_to_cpu/`
después de generarlos.
