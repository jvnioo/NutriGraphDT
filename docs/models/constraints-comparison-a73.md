# Comparación con y sin restricciones bioquímicas: A73 (#272)

Registro acumulativo de A73-P1 a A73-P4. La evaluación compara los brazos `free` y
`constrained` en D1 y en la cohorte sintética, siguiendo el protocolo A55-P1
([`constraints-evaluation-protocol.md`](constraints-evaluation-protocol.md)). La etiqueta
«Factibilidad sin costo» es una categoría formal del protocolo, no una afirmación de que la
restricción haya mejorado el modelo.

## Alcance y estado

| Sub-Issue | Trabajo | Estado en este registro |
|---|---|---|
| #273 (A73-P1) | Reejecución independiente en CPU y comprobación de §1.3 y §8. | Ejecutado; 300/300 folds, sin fallos. |
| #274 (A73-P2) | Tabla única de métricas y violaciones por conjunto, variante y brazo, con desglose por día y referencias. | Pendiente. |
| #275 (A73-P3) | Inferencia pareada, incluida la comparación obligatoria contra `day_only`. | Pendiente. |
| #276 (A73-P4) | Verificación de la tabla contra métricas y metadatos de corrida. | Pendiente. |

El trabajo se entregará en un solo Pull Request contra `main`, con cierre de las Issues
correspondientes. Las secciones P2–P4 se completarán cuando se realicen esas tareas; este registro
no anticipa sus resultados.

## P1 — Reejecución independiente de D1 (#273)

### Objetivo y configuración

Se ejecutó `scripts/evaluate_constraints.py` en CPU, de forma independiente de la evaluación
versionada, con la salida y las corridas individuales fuera del repositorio. La comparación
incluyó las tres variantes, dos brazos, diez semillas y cinco folds por semilla: 300
entrenamientos en total. Los 300 terminaron correctamente, sin fallos, en 1880,1 s (31 min
20,1 s).

La corrida se generó en Windows con Python 3.14.5, PyTorch 2.14.1+cpu y PyG 2.8.0.post1. El
verificador temporal confirmó 56 animales, `k=5`, semillas 0–9, `taxon_identity=true`, λ = 0,1
para las variantes restringidas y el término bioquímico esperado.

La corrida se considera independiente respecto del entorno de la evaluación D1 versionada, que
se ejecutó en una GPU AMD con ROCm. No es una reproducción exacta de pesos ni de predicciones
entre dispositivos: el criterio de repetición es el pareamiento de los brazos, `Δ = 0`, y
`VR = 0` para la cota bioquímica.

### Preflight de cohorte e identidad taxonómica

El preflight comprobó que `load_d1_cv_inputs` obtiene los mismos 56
`sample_id` del plan de D1 y que el plan verificado corresponde a esa cohorte. La definición
versionada (`configs/cohorts/d1_holofood.json`) usa contenido cecal, los tres AGCC objetivo y
un mínimo de 1000 lecturas SSU. El `run.json` de referencia registra estos filtros:

| Paso | Muestras restantes | Excluidas en el paso |
|---|---:|---|
| Metagenoma y AGCC | 59 | Ninguna |
| Exclusiones por perfiles repetidos | 58 | `SAMEA112905124` |
| Profundidad SSU mínima | 56 | `SAMEA112905107`, `SAMEA112905331` |

El conjunto final de 56 IDs se contrastó con las asignaciones del plan; el resumen y los filtros
de cohorte coincidieron con el `run.json` versionado. En Linux, el hash de bytes versionado de la
configuración de cohorte es
`c3ef104487f224e940a3e44bcdc0447f5adec6dd3077ab1256d58b50cf4d898e`; el `run.json` creado en
Windows registra `d40db3e1c60c340813b8966b5a7a2222c13f388314909edd5cbf81fe01cceacb`, debido al
fin de línea CRLF. Al normalizar CRLF a LF, el hash del contenido coincide con el versionado.

La identidad taxonómica debe estar habilitada (`taxon_identity: true`), como en
`configs/constraints/lambda_sweep_d1.json` y en el `run.json` de referencia. La configuración
por omisión actual de `TaxonIdentityConfig` es `min_prevalence=0.1`, `min_abundance=0.0`,
`top_k=30` y `profile_block=false`; el vocabulario se ajusta con el train interno de cada fold.
El registro superior de la evaluación solo conserva el indicador booleano. Los `run.json` por
fold, que contienen la configuración completa y el vocabulario ajustado, viven bajo `runs/` y
no están versionados. Por tanto, salvo que se preserven por separado como evidencia permitida,
no se puede certificar retrospectivamente la configuración completa de identidad de los folds
GPU versionados. En los 300 `run.json` por fold de la nueva corrida, el verificador confirmó
`min_prevalence=0.1`, `min_abundance=0.0`, `top_k=30` y `profile_block=false`, además de revisar
que el vocabulario de cada corrida quedó ajustado dentro del fold. Los `run.json` por fold GPU
versionados no están disponibles, por lo que su configuración completa no puede comprobarse
retrospectivamente y no se inferirá.

### Huellas, semillas, λ y pareamiento

En el `run.json` independiente se comprobaron los dos hashes del plan, comparados también con
`reports/constraints/d1/run.json`:

| Campo | Significado | Valor versionado esperado |
|---|---|---|
| `plan_sha256` | SHA-256 de los bytes del archivo del plan en Linux/LF. | `a32a191cb6ed62bcd3f2f2d8d309fbf76615900b89d876b96ebe70f09ce34d55` |
| `plan_canonical_sha256` | SHA-256 del JSON canónico del plan. | `ea329b6a9d91d0a240844765fb6884b360e56528633cbac2c9da62e809ecc8c5` |

El hash de bytes local del plan fue `d5ce9a4bfb30021af45e92061904b49d56bdd539bf7c54d7804a0b214acabcb2`;
el hash canónico coincidió exactamente con el versionado. También se verificaron
`seeds = [0, ..., 9]`, `k = 5` en el plan, `lambdas = 0.1` para cada variante y el término
`d06.hydrogen.propionate_bound`. En `folds.csv`, `free` tiene λ = 0 y `constrained` λ = 0.1.
Para cada `(model, seed, fold)`, ambas filas existen, están completadas y comparten
`train_seed = 42000 + seed * 100 + fold`. Resultado: 300 de 300 entrenamientos completados.

La configuración base del entrenamiento puede mostrar `constraint_lambda = 0.0`: las λ
efectivas por brazo se comprueban en `folds.csv`, no se deducen de ese valor base.

### Comprobación de diferencias y violaciones

La comprobación temporal de P1 comparó `fold_metrics.csv` de la nueva corrida con el
versionado, alineando cada fila por semilla, fold, modelo, brazo, grupo y métrica. Para cada
métrica y fold calculó `CPU − GPU`, con media, desviación y diferencia absoluta máxima. Estas
diferencias entre dispositivos son descriptivas y no deben confundirse con el efecto de las
restricciones.

Dentro de la corrida CPU, se alinearon los brazos por semilla, fold, modelo, grupo y métrica.
Se comprobó `constrained − free = 0` en todas las filas comparables y en `paired.csv`. En el
subconjunto `test`, la tasa de violación (`VR`) de `d06.hydrogen.propionate_bound` fue cero en
todos los folds y brazos; también se comprobó que el resumen agregado da cero. Por tanto,
`Δ = 0` fila por fila y `VR = 0` en los 300 folds. Si `Δ` es constante cero, los estadísticos de
comparación no están definidos: no se informará `p = 1`.

Las referencias GPU existentes para `fraction_mae_pp`, grupo `all`, son:

| Variante | `free` y `constrained` (media ± desviación entre folds, pp) |
|---|---:|
| `homo_sage` | 4.1944 ± 0.7513 |
| `hetero_sage` | 4.1069 ± 0.7074 |
| `hetero_gat` | 4.0698 ± 0.7011 |

La métrica primaria `fraction_mae_pp`, grupo `all`, se resume por diferencia fold a fold
`CPU − GPU` (pp). Las cifras son iguales en ambos brazos porque la evaluación CPU también
obtuvo `Δ = 0`:

| Variante | Brazo | Media CPU−GPU | Desviación | Máx. abs. |
|---|---|---:|---:|---:|
| `homo_sage` | `free` | −0,004824 | 0,199803 | 0,526386 |
| `homo_sage` | `constrained` | −0,004824 | 0,199803 | 0,526386 |
| `hetero_sage` | `free` | −0,032074 | 0,248222 | 0,915439 |
| `hetero_sage` | `constrained` | −0,032074 | 0,248222 | 0,915439 |
| `hetero_gat` | `free` | −0,006605 | 0,325720 | 1,159730 |
| `hetero_gat` | `constrained` | −0,006605 | 0,325720 | 1,159730 |

El detalle de las diferencias por variante, brazo, día, métrica y componente está en
[`cpu_minus_gpu.md`](../../reports/constraints/reproducibility/a73_d1_cpu_independent/cpu_minus_gpu.md).
La corrida de referencia se hizo en Linux con GPU AMD Radeon RX 9060 XT, ROCm 7.1 y PyTorch
2.13.0+rocm7.1; la nueva se hizo en Windows con CPU y PyTorch 2.14.1+cpu. El dispositivo, el
backend ROCm frente a CPU, el sistema operativo y la versión de PyTorch difieren, por lo que el
camino numérico del entrenamiento puede cambiar. Se informa la diferencia observada sin
atribuirla a causalidad biológica ni exigir coincidencia de coma flotante entre dispositivos.

### Revisión del protocolo A55-P1

#### §1.3 — Protocolo estricto contra fuga de información

| Punto | Evidencia y estado |
|---|---|
| 1. Ajustes dependientes exclusivamente del `train` | **Cumplido.** La revisión del flujo confirma que identidad taxonómica, `FeatureScaler` y `CompositionalTargetTransform` se ajustan solo con `inner_train_ids`; el verificador confirmó que los IDs de train, validación interna y test son disjuntos y corresponden al plan en todos los folds. |
| 2. Detención temprana interna | **Cumplido.** `split_inner_validation` separa por corral y dieta solo dentro de `train_ids` con semilla determinista; el test se evalúa al final con el mejor estado. El verificador contrastó los subconjuntos registrados por fold con el plan y confirmó que no se solapan. |
| 3. Selección de hiperparámetros | **Cumplido.** La selección versionada registra `test_used: false`; utiliza validación interna y `val_data_loss_mean`. Los hashes de selección y configuración del barrido se verificaron normalizando finales de línea a LF. La corrida usó la λ ya seleccionada, sin optimizarla con el test. |
| 4. Pareamiento estricto | **Cumplido.** Los 300 registros corresponden a pares completos por modelo, semilla y fold; `train_seed` coincide entre brazos según `42000 + semilla * 100 + fold`. Δ fue cero en cada fila de métricas comparable. |

#### §8 — Formato de artefactos y reproducibilidad

| Punto | Evidencia y estado |
|---|---|
| 1. `report.md` | **Desviación registrada.** El reporte GPU versionado no incluye VMM en la tabla, aunque `violations_summary.csv` sí conserva `mean_magnitude`; no se editó. El reporte temporal de CPU también incluye los avisos de interpretación. No se versionó otro `report.md`; el resumen y las limitaciones constan aquí y en `cpu_minus_gpu.md`. |
| 2. `metrics.csv` | **Desviación de archivo documentada.** No se versionó; sus agregados se pueden calcular desde `fold_metrics.csv`. |
| 3. `violations.csv` | **Desviación de archivo documentada.** No se versionó el detalle por fold; el verificador temporal comprobó sus 300 filas D-06 y se conserva `violations_summary.csv`. |
| 4. `fold_metrics.csv` | **Cumplido.** Se versionó el desglose por fold y se usó para comprobar igualdad entre brazos y diferencias CPU−GPU. |
| 5. `run.json` | **Cumplido con desviaciones de portabilidad documentadas.** Se versionaron commit, hashes, versiones y entorno, semillas y duración. `k=5` se comprobó en el plan hasheado. Los hashes de bytes cambian entre CRLF y LF, según se detalla abajo; el hash canónico del plan coincide. |

#### Desviación: hashes de bytes y finales de línea

El repositorio no tiene `.gitattributes`; los JSON del checkout de Windows usan CRLF y en Linux
están en LF. Por eso los hashes SHA-256 de bytes que produjo la corrida local difieren de los
registrados en la evaluación Linux, aunque el contenido sea el mismo. El verificador confirmó
que cada SHA-256 local de bytes coincide con el `run.json` nuevo y comparó el contenido
normalizado a LF con los archivos versionados. El hash canónico del plan también coincide sin
ajuste (`ea329b6a…9ecc8c5`).

| Archivo | Hash de bytes en `run.json` Windows (CRLF) | Hash versionado Linux (LF) |
|---|---|---|
| Plan D1 | `d5ce9a4bfb30021af45e92061904b49d56bdd539bf7c54d7804a0b214acabcb2` | `a32a191cb6ed62bcd3f2f2d8d309fbf76615900b89d876b96ebe70f09ce34d55` |
| Configuración de cohorte | `d40db3e1c60c340813b8966b5a7a2222c13f388314909edd5cbf81fe01cceacb` | `c3ef104487f224e940a3e44bcdc0447f5adec6dd3077ab1256d58b50cf4d898e` |
| Selección de λ | `c3140effa104d96cb6e0b15132ae188d507a32cf6e2e29f4008f56c2b1fff6f5` | `ab1f2b1417b87f4efaa8974cc757b564338048c37d8458b2a382fb621d961ccf` |
| Configuración del barrido | `879ca6d607c0b4965f72001d4d3b9d66d984fee92002a94e1a82c5c8c12a397b` | `c3d77ffe46551839821731ad201d56abda7b3cfb607670152989603c9d5a3921` |

P4 debe evitar comparar directamente hashes de bytes entre checkouts con distintos finales de
línea: debe comparar el hash canónico apropiado o normalizar a LF antes del SHA-256, además de
verificar que el hash de bytes registrado corresponde a los bytes locales. Se propone, pero no
se crea aquí, una Issue para fijar finales de línea de `configs/**/*.json` mediante
`.gitattributes` o, alternativamente, estandarizar la comparación en hashes canónicos.

### Evidencia de la ejecución y archivos que se versionarán

La evaluación se ejecutó con `--device cpu`, escribiendo tanto `--output` como `--runs-dir`
bajo `C:\Users\joaqu\AppData\Local\Temp\a73-d1-928cea564cd142b09de2184b36913ef9`, nunca en
`reports/constraints/d1/`. El `run.json` conservado registra una ruta absoluta local en
`runs_dir` y en `argv` para `--output` y `--runs-dir`; no se editó para evitar alterar la
procedencia. Esas rutas solo existen en el equipo de la corrida y no son portables.

Tras la verificación se guardaron en
`reports/constraints/reproducibility/a73_d1_cpu_independent/` solo:

- `run.json`;
- `folds.csv`;
- `fold_metrics.csv`;
- `paired.csv`;
- `violations_summary.csv`;
- un resumen Markdown de diferencias CPU−GPU.

Esta selección implica las desviaciones de archivo de §8.1–§8.3 anotadas arriba. La salida
temporal completa se utilizó para la auditoría; los checkpoints, `predictions.csv`,
`epoch_violations.csv` y los artefactos agregados no seleccionados no se versionaron. Tampoco se
sobrescribirán ni modificarán los reportes existentes de `reports/constraints/d1/` o
`reports/constraints/synthetic/`. El README de reproducibilidad organiza reproducciones de
corridas individuales por dirección de dispositivo (`gpu_to_cpu/`, `cpu_to_cpu/`,
`gpu_to_gpu/`), con registros asociados a un `run_id`; no prescribe un esquema para reevaluar
los 300 folds completos. Por eso `a73_d1_cpu_independent/` describe una evaluación nueva y no
la presenta como una reproducción GPU→CPU de un entrenamiento concreto.

### Lectura científica y limitaciones

D-06 §6 define `d06.hydrogen.propionate_bound` como `p_p ≤ 2/3` y anticipa que no se activa en
D1. Si todas las predicciones cumplen la cota, `L_bio` y su gradiente son cero y la penalización
no modifica el entrenamiento. En ese caso, «Factibilidad sin costo» es la clasificación formal
de la regla de decisión: significa que no hubo costo porque la restricción no intervino. No
significa que haya mejorado la plausibilidad bioquímica, la predicción o el conocimiento
biológico.

El reporte generado por la corrida independiente advierte literalmente que «no costó nada porque
no hizo nada». D-06 §6 explica por qué: en D1 la cota `p_p ≤ 2/3` no se activa, así que `L_bio` y
su gradiente son cero y la penalización no altera el entrenamiento. «Factibilidad sin costo» es
la etiqueta formal de la regla aplicada, no evidencia de mejora de plausibilidad ni de beneficio
científico.

P1 verifica una comparación computacional bajo la cohorte, el grafo y la configuración
registrados; no demuestra beneficio científico de la restricción. Los `run.json` por fold GPU
con la configuración completa de `taxon_identity` no están versionados. El resumen de resultados
por fila y la verificación detallada de CPU−GPU están en
[`reports/constraints/reproducibility/a73_d1_cpu_independent/`](../../reports/constraints/reproducibility/a73_d1_cpu_independent/).

El verificador temporal usado fue `%TEMP%\a73_verify_constraints.py`; no se versionó. Comprobó
los hashes locales y canónicos, la cohorte y configuración, los 300 pares y sus semillas,
subconjuntos y taxonomía por fold, igualdad exacta de métricas entre brazos, VR de D-06 y las
diferencias CPU−GPU fila a fila. P4 reemplazará esta verificación temporal con
`scripts/compare_constraints.py --verify`.

## P2 — Tabla de métricas y violaciones (#274)

Pendiente. Registrar el comando de generación, los artefactos de entrada y salida, la prueba con
datos pequeños, el desglose por día y las referencias `dummy_mean` y `day_only`. Incluir VR,
VWM, VMM y FR sin transcribir valores a mano, y rotular explícitamente la cohorte sintética.

## P3 — Inferencia pareada (#275)

Pendiente. Registrar Δ, IC del 95 % y valores p cuando sean estimables; declarar el motivo
cuando una comparación no tenga estadístico. Incluir `free − day_only`, la decisión sobre
multiplicidad y la distinción entre significancia estadística y relevancia práctica.

## P4 — Verificación de tabla y corridas (#276)

Pendiente. Registrar la opción `--verify`, los metadatos contrastados, la salida de verificación
y la prueba que altera un valor y confirma que la validación falla.
