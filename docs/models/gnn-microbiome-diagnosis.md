# Por qué la GNN no aprovecha el perfil por familia en D1 (#268)

[#266](gnn-taxon-identity.md) mostró que `ridge` con el perfil por familia mejora a `ridge` sobre el
diseño, y que la GNN con la misma información no. Este documento separa las causas posibles. El
reporte está en [`reports/gnn/d1_microbiome_diagnosis/`](../../reports/gnn/d1_microbiome_diagnosis/).

**Respuesta corta.** La señal llegaba a la lectura unas 40 veces más chica que el diseño. Corregir eso
lleva a la GNN de 4,19 a 3,92 pp y de 4,11 a 3,90 pp en las dos variantes SAGE, y deja de ser claramente
peor que `ridge` por familia (3,69 pp). Pero **la mejora no se distingue del ruido y la GNN sigue sin
superar a `ridge`**. Con 56 animales, los datos no alcanzan para separar estas causas con más precisión.
La frase de #266 sigue en pie: **en D1, el grafo no agrega capacidad predictiva demostrable.**

## 1. Método

```bash
python scripts/diagnose_gnn_microbiome.py --stage grid --device cuda
python scripts/diagnose_gnn_microbiome.py --stage evaluate --device cuda
```

1. **Diagnóstico y selección, sin el test.** Con las semillas de selección (0 y 1) del plan de #139, solo
   se lee el train de cada fold, repartido en train y val interno
   (`test_fitting_a_candidate_never_reads_the_test_of_the_fold`). La grilla se fijó antes de correrla: 24
   configuraciones por variante, 720 entrenamientos, sin fallos. Se elige la menor `val_data_loss` media.
2. **Evaluación única.** La elección de cada variante se evalúa una vez en el test de los 50 folds. La
   repetí con el mismo código y `fold_metrics.csv` salió idéntico byte a byte.

## 2. Hipótesis

| Hipótesis | Evidencia (solo train y val interno) | Conclusión |
|---|---|---|
| **Escala.** El perfil llega muy chico a la lectura. | Desviación entre animales: 0,026 en `taxon` frente a 1,01 en `host` y `diet`. Con `profile_block`, la mejor configuración usa el bloque en dos de tres variantes, aunque promediado sobre la grilla el factor casi no mueve la pérdida. | **Confirmada como defecto; su efecto no es concluyente.** |
| **Arquitectura.** La cabeza MLP estorba. | La cabeza lineal es algo peor en las tres variantes (de 0,012 a 0,017). | **Descartada** en esta forma. No se probaron otras lecturas. |
| **Ajuste: pocas épocas.** | La pérdida de train baja de 1,1 a cerca de 0,1 en 200 épocas, y la de validación deja de mejorar antes de la época 21. | **Descartada.** El modelo aprende de sobra. |
| **Ajuste: sobreajuste.** | En esas curvas, la validación empeora mientras el train sigue bajando. Sin embargo, `weight_decay` más alto casi no mueve la pérdida promedio (a lo sumo 0,013), y `hidden = 64` es mejor que 16 (de 0,026 a 0,034). | **Confirmado el sobreajuste; regularizar más no lo resuelve** dentro de esta grilla. |

**La incertidumbre manda.** La pérdida varía cerca de 0,35 entre folds, y las configuraciones solo
difieren de 0,85 a 0,95: con unos 9 animales de val interno, la selección es ruidosa. Por eso, que una
configuración gane no prueba que sea mejor.

## 3. Evaluación en el test

| Variante | Configuración elegida | Antes (pp) | Ahora (pp) | Δ frente a antes | Δ frente a `ridge_family` | Δ frente a `ridge_design` |
|---|---|---:|---:|---|---|---|
| `homo_sage` | bloque de perfil, `weight_decay` 0,1 | 4,19 | 3,92 | −0,27 [−0,65; +0,11] | +0,24 [−0,13; +0,60] | −0,05 [−0,44; +0,34] |
| `hetero_sage` | bloque de perfil, `weight_decay` 0,01 | 4,11 | 3,90 | −0,21 [−0,68; +0,26] | +0,21 [−0,15; +0,57] | −0,08 [−0,45; +0,29] |
| `hetero_gat` | La actual | 4,07 | 4,07 | 0 | +0,38 [−0,01; +0,78] | +0,09 [−0,35; +0,53] |

`fraction_mae_pp`, IC 95 % con el t corregido de Nadeau y Bengio. Referencias de #266: `ridge_family`
3,69 y `ridge_design` 3,98.

**Lectura:**

- En `homo_sage` y `hetero_sage`, la GNN ya no es claramente peor que `ridge` por familia, como lo era en
  #266. Eso no es lo mismo que igualarla: los intervalos son anchos.
- Ninguna variante supera a `ridge` por familia, ni se distingue de `ridge` sobre el diseño.
- **La señal de `ridge` por familia también es acotada.** Mejora las fracciones (`fraction_mae_pp` −0,29
  [−0,51; −0,07]; `fraction_r2` +0,13 [+0,03; +0,23]), pero no el total (`log_total_mae` −0,00 [−0,04;
  +0,04]) ni las concentraciones reconstruidas (−0,05 [−1,06; +0,96]), y esas comparaciones no se
  corrigieron por multiplicidad. Los animales son pocos y el resultado puede no replicarse.

## 4. Qué se decide

- **La configuración por omisión no cambia.** Ninguna mejora se distingue del ruido, y elegir por variante
  con esta selección sería sobreinterpretarla. `profile_block` y `linear_head` quedan como opciones
  (`TaxonIdentityConfig`, `configs/models/`), y la elección queda en `selection.json`.
- **#266 no se repite,** porque lo que recibe el modelo por omisión es el mismo. Sus resultados siguen
  vigentes.
- **#185 no cambia.** Con las configuraciones elegidas, ningún fold de los 150 viola la cota de D-06 en el
  test, así que la penalización seguiría inactiva y los dos brazos serían idénticos.

## 5. Qué se puede afirmar

| Se puede afirmar | No se puede afirmar |
|---|---|
| El perfil por familia, en un modelo lineal, mejora las fracciones frente al diseño, sin corregir por multiplicidad. | Que el grafo o la GNN mejoren la predicción en D1. |
| La escala de la lectura era un defecto real, y corregirlo acerca a la GNN a `ridge`, sin diferencia demostrable. | Que la escala sea la causa de toda la diferencia. |
| La GNN sobreajusta en D1. | Que más datos o una búsqueda más amplia cambien el resultado; no se probó. |

Para el informe, conviene presentar a `ridge` por familia como el mejor modelo de D1 y a la GNN como una
arquitectura validada estructuralmente y útil para la explicabilidad, sin ventaja predictiva demostrada.

## 6. Limitaciones

- Es un análisis exploratorio motivado por #266. La evaluación es única, pero los mismos folds de test ya
  se habían visto, así que no es independiente.
- La mejor época de cada fold vuelve optimista la `val_data_loss`, por lo que no se compara con `ridge`.
- La grilla cubre cuatro factores. No prueba otras lecturas (suma, atención), otras tasas de aprendizaje
  ni otros rangos de linaje.
- Ninguna evaluación de D1 se llama «mecanística» (#256).
