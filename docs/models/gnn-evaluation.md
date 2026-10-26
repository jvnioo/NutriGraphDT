# Comparación GNN frente a baselines (A45-6)

Esta página interpreta la tabla comparativa del avance 2. La tabla se genera con un comando a
partir de los reportes ya versionados, sin entrenar modelos:

```powershell
python .\scripts\compare_models.py
```

El comando escribe `reports/comparison/model_comparison.md` y `reports/comparison/model_comparison.csv`.
La lógica está en `nutrigraphdt.models.comparison` y no requiere PyTorch ni scikit-learn.

## Qué se compara

| Dataset | Baselines (A40-4, A40-5, A45-2) | GNN (A45-3, A45-4) |
|---|---|---|
| Cohorte sintética | `reports/baselines/` | `reports/gnn/synthetic/` |
| D1 HoloFood | `reports/baselines/d1/` | `reports/gnn/d1/` |

- **Modelos.** Los cinco baselines (`dummy_mean`, `ridge`, `elasticnet`, `random_forest`,
  `hist_gradient_boosting`) y las tres variantes GNN (`homo_sage`, `hetero_sage`, `hetero_gat`).
- **Subconjuntos.** `val` y `test`.
- **Métricas.** Las de A40-2 ([metrics.md](metrics.md)): MAE, RMSE, R² y % de predicciones
  negativas, por AGCC (acetato, propionato, butirato) y su promedio sin ponderar.
- **Filas.** Se unen con `combine_reports`, así que el detalle por AGCC tiene el formato de
  `EvaluationReport`.
- **Variantes pendientes.** Una variante GNN sin `run_<variante>.json` o sin filas en
  `report.csv` aparece como `pendiente` en ambas tablas, en lugar de omitirse. Hoy no hay
  pendientes.

## Mismas muestras y misma partición

Antes de comparar, el script verifica con los `run.json` que cada variante GNN use las mismas
muestras y la misma partición que los baselines de su dataset. Si algo no coincide, termina con
código 2 y no escribe la tabla.

- **En ambos datasets** compara el `dataset_id` y los tamaños de subconjunto (`subset_sizes` de
  los baselines).
- **Cohorte sintética.** Compara la misma cohorte (`n_samples`, `first_seed`), la misma semilla
  de partición y los mismos conteos por subconjunto (30/10/10).
- **D1.** Compara el archivo de partición (`configs/splits/d1_holofood.json`, versión 2.0.0,
  agrupada por corral), su SHA-256 y los animales con los tres AGCC por subconjunto (31/7/21).
  Es la misma partición que usa `compare_baselines.py --dataset d1`.

El `run.json` registra el SHA-256 de los bytes del archivo de partición (A44-5). En Windows,
Git deja los archivos versionados con fines de línea CRLF (`core.autocrlf`), así que el mismo
archivo tiene otro hash que en Linux. Las corridas D1 de A45-4 se hicieron en Windows. Por eso
la verificación acepta el hash del archivo con fines de línea LF o CRLF: el contenido es el
mismo, y cualquier otro cambio se rechaza.

## Resultados

RMSE promedio de los tres AGCC (menor es mejor), una corrida por modelo con semilla 42. El
detalle está en `reports/comparison/model_comparison.md`.

| Modelo | Sintético val | Sintético test | D1 val | D1 test |
|---|---:|---:|---:|---:|
| `dummy_mean` | 8.36 | 7.25 | 10.93 | 9.75 |
| `ridge` | 8.37 | 7.26 | 10.57 | 9.01 |
| `elasticnet` | 8.36 | 7.25 | 11.71 | 11.00 |
| `random_forest` | 8.76 | 7.33 | 11.86 | 9.56 |
| `hist_gradient_boosting` | 10.37 | 8.66 | 13.50 | 10.01 |
| `homo_sage` | 8.27 | 7.14 | 9.52 | 8.80 |
| `hetero_sage` | 8.27 | 7.06 | 9.61 | 8.75 |
| `hetero_gat` | 8.20 | 7.17 | 9.61 | 8.83 |

Ningún modelo predice valores negativos (`negative_pct` = 0 en todas las filas). Las métricas
están en mmol/kg; en D1, de digesta fresca (base húmeda), según V-06 de la respuesta de
Investigación.

## Criterio de salida de F4 (provisional)

El criterio de F4 pide que una GNN iguale o supere al menos un baseline en un escenario. La
tabla lo evalúa con el RMSE promedio de `test`: una GNN iguala o supera un baseline si su RMSE
es menor o igual.

**Se cumple en D1 HoloFood, de forma provisional.** Vale solo para esta evaluación: la
partición 2.0.0, un único `test` fijo de 21 animales de 10 corrales y el objetivo en
concentración. No es un resultado firme para el avance 2. La sección
[Respuesta de Investigación](#respuesta-de-investigación-16-10-2026) explica por qué y qué
cambia.

- Las tres variantes GNN tienen menor RMSE de `test` que los cinco baselines. La mejor,
  `hetero_sage`, obtiene 8.75; el mejor baseline, `ridge`, obtiene 9.01, con R² de 0.22
  frente a 0.18.
- **La diferencia con `ridge`, de 0.18 a 0.26 según la variante, no es concluyente.**
  - No se midió la incertidumbre de muestreo de esos 21 animales, que es la que importa para
    afirmar que un modelo supera a otro.
  - La variabilidad por semilla de A45-5 (#105) no sirve para eso: solo mide el ruido de
    optimización de la GNN con los mismos animales, y no incluye la variabilidad de `ridge`.
  - Una medida adecuada sería, por ejemplo, un bootstrap por corral de la diferencia pareada
    de RMSE (GNN − `ridge`) en `test`. Queda para la reevaluación con validación cruzada.
- La diferencia viene sobre todo de acetato y butirato. En propionato, GNN y `ridge` quedan
  prácticamente iguales (3.61 a 3.67 frente a 3.63).
- También en `val` las tres GNN tienen el menor RMSE (9.52 a 9.61 frente a 10.57 de `ridge`),
  pero `val` tiene solo 7 animales.

**En la cohorte sintética el criterio también se cumple numéricamente, pero no es
interpretable.** En el generador actual los AGCC no dependen de las entradas (ver
`reports/gnn/synthetic/report.md`). Los mejores baselines en `test` son `dummy_mean` y `elasticnet`,
empatados en 7.25: ningún baseline aprende algo más que la media. Las GNN quedan entre 0.08 y 0.19 por debajo, una diferencia del orden
de la variabilidad por semilla (≈ 0.1 a 0.2 en A45-5). El sintético sirve para verificar el
procedimiento, no la capacidad predictiva.

## Respuesta de Investigación (16-10-2026)

La [respuesta de la Célula de Investigación a la solicitud de revisión v1.1](<../research/Respuesta de Investigación a la Solicitud de revisión v1.1.md>)
llegó después de esta tabla y cambia cómo debe leerse D1:

- **Cohorte.**
  - Esta tabla usa los 59 animales con metagenoma y los tres AGCC.
  - Investigación excluye SAMEA112905124 (`train`), cuyo perfil de AGCC repite el de otro
    animal: la cohorte queda en 58 (D-03). No hay fuga entre subconjuntos: los otros siete
    animales con perfiles repetidos no tienen metagenoma.
  - La cohorte oficial de `main` (`reports/cohort/d1_holofood.md`, versión 1.0.0) además exige
    al menos 1000 lecturas SSU (S-05) y quita SAMEA112905331 (`val`) y SAMEA112905107
    (`test`). Queda en 56 animales.
- **Evaluación.**
  - La evaluación principal pasa a ser validación cruzada agrupada por corral y estratificada
    por dieta (StratifiedGroupKFold, k = 5, al menos 10 semillas), en lugar de un único `test`
    fijo (D-07).
  - Pide métricas por día de muestreo, porque la dieta está confundida con el día: en el
    día 35 hay 26 Control, 3 Probiótico y 2 Prebiótico.
- **Objetivo.**
  - El objetivo cambia a la composición de los tres AGCC (dos log-razones respecto del
    acetato), con log T como salida aparte (D-03).
  - El acetato domina el RMSE de esta tabla, y el 95 % de la varianza de su logaritmo es la del
    total, que no se predice fuera del corral: R² de log T de −0.14 en la cohorte (Tabla 5).
- **Unidad.** mmol/kg de digesta fresca (base húmeda) (V-06): las tablas descargadas no
  traen materia seca.

El reanálisis con este marco (cohorte oficial, validación cruzada por corral y objetivo
composicional) está en los Issues #138, #139, #140 y #142. Esta tabla no se rehízo.

## Advertencias

Estas advertencias deben acompañar cualquier lectura de la tabla en el avance 2:

- **D1 tiene pocas muestras.**
  - Hay 59 animales con los tres AGCC: 31 en `train`, 7 en `val` y 21 en `test`.
  - Las métricas de `val` se calculan sobre 7 animales, y las de `test` sobre 21 animales de 10
    corrales.
  - Las diferencias entre modelos son de pocas décimas de RMSE, y el R² más alto es 0.22. Ningún
    modelo explica la mayor parte de la variación.
- **Los baselines usan el tratamiento dietario y la GNN no** (§7 de
  [gnn-architecture.md](gnn-architecture.md)).
  - En D1, el nodo `diet` no tiene columnas en `x`, mientras que la tabla de atributos de los
    baselines incluye `diet:treatment` ([tabular-features.md](tabular-features.md)).
  - La GNN supera a los baselines con menos información de entrada. Codificar el tratamiento en
    el grafo podría cambiar la comparación en cualquier sentido.
- **Las variantes GNN no se distinguen entre sí.**
  - En D1 los taxones están aislados, así que las tres variantes se reducen a encoders más
    lectura sobre los mismos nodos (§7 del diseño).
  - Sus diferencias (≈ 0.08 de RMSE en `test`) son menores que la variabilidad por semilla.
  - La tabla no permite elegir una variante ni atribuir la mejora a la estructura del grafo.
- **Hay una corrida por modelo.**
  - Los baselines y las GNN de esta tabla usan una sola semilla (42).
  - A45-5 (#105) midió la variabilidad por semilla de las GNN, pero no la de los baselines.
  - Los baselines con componente aleatorio (`random_forest`, `hist_gradient_boosting`) también
    pueden variar.
- **Los hiperparámetros no se ajustaron igual.**
  - Los baselines eligen hiperparámetros con validación cruzada agrupada sobre `train`
    ([baselines.md](baselines.md)).
  - Las GNN usan la configuración inicial del §6 del diseño, con detención temprana sobre `val`.
  - La búsqueda de A45-5 no mejoró `test` frente a esa configuración inicial.
- **Otras limitaciones del §7** siguen abiertas: muchos nodos por grafo frente a pocas muestras
  con target, y la falta de la ruta mecanística taxón → función en D1.

## Reproducir

1. Regenere los reportes de entrada, si cambiaron, con los comandos de [baselines.md](baselines.md)
   y de `scripts/README.md` (`report_gnn.py`).
2. Corra `python scripts/compare_models.py`.
3. Confirme los cambios de `reports/comparison/`.

Una prueba de integración falla si los archivos versionados de `reports/comparison/` no
coinciden con lo que genera el script.
