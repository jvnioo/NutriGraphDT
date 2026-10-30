# Interfaz de restricciones y registro de violaciones (A57-P1, #163)

`nutrigraphdt.constraints` define operadores tensoriales diferenciables, penalizaciones
independientes de la pérdida de datos y registros por muestra. El contrato de metadatos está
versionado con `CONSTRAINTS_CONTRACT_VERSION = "1.0.0"` para incluirse en `run.json`.

## Alcance y estado científico

El catálogo de restricciones activas contiene las restricciones estructurales y una restricción
bioquímica aprobada en D-06 v1:

- No negatividad de las fracciones molares de acetato, propionato y butirato.
- No negatividad de las concentraciones correspondientes en `mmol/kg`.
- Cierre simplex de las fracciones: `sum(p) = 1`, con tolerancia numérica adimensional
  `STRUCTURAL_CLOSURE_TOLERANCE = 1e-6`.
- Cota de propionato de D-06: `d06.hydrogen.propionate_bound`, definida en el espacio `fractions`.

La tolerancia de cierre es una decisión numérica explícita para la precisión de los tensores,
no una tolerancia fisiológica. Las desigualdades usan tolerancia cero y su operador debe cumplir
`h <= 0`. La restricción de D-06 tiene unidad `1`, tolerancia `0.0` y versión individual `1.0.0`,
conforme al contrato `CONSTRAINTS_CONTRACT_VERSION = "1.0.0"`.

### Cota de hidrógeno para propionato (D-06 v1)

La restricción calcula sobre fracciones molares en el orden acetato, propionato y butirato:

```text
h(p) = p_p - 2(p_a + p_b)
     = values[:, 1] - 2.0 * (values[:, 0] + values[:, 2])
h(p) <= 0
```

Con el cierre simplex equivale a `p_p <= 2/3`. La implementación y sus metadatos proceden de
[D-06, versión 1.0, emitida el 29-10-2026, sección 3.5](../research/D-06%20%E2%80%94%20Restricciones%20bioqu%C3%ADmicas%20para%20D1.md).
Las constantes de procedencia están en `nutrigraphdt.constraints.d06`; los tests comprueban que
la ruta registrada existe y que el documento contiene el nombre de la restricción.

La derivación es condicional a los supuestos declarados por Investigación:

- **S1:** no hay aporte externo neto de H₂ al ciego; no hay fuente específica para el ciego de aves.
- **S2:** solo acetato y butirato liberan H₂, hasta 2 mol por mol; el apoyo es parcial y no se
  conoce la magnitud general de otras fuentes.
- **S3:** la formación de propionato consume al menos 1 mol de H₂ por mol; se desconoce la
  proporción de propionato de origen no carbohidrato en el ciego de aves.

D-06 §6 indica que la cota no se activa por defecto. Puede seleccionarse explícitamente en cualquier
flujo. En D1 se espera `VR = 0`, como indica D-06 §6; el reporte de F5 debe confirmarlo. Su efecto
solo puede observarse en el dataset sintético o en baselines que predicen en `R³`. La cota no es el
balance completo de Wolin: no se implementan balances absolutos, restricciones por día,
restricciones en concentraciones, el control de soporte de F6 ni elementos propuestos para D-06 v2.
`ConstraintStatus.PENDING_D06` se conserva para restricciones de investigación aún no aprobadas.

Para salidas composicionales `(z1, z2, ln T)`, la no negatividad es una garantía matemática de
la inversa `softmax · exp(ln T)`. En coma flotante, una fracción puede subdesbordarse a cero y
una concentración puede ser cero; valores no representables pueden producir overflow o `NaN`
(por ejemplo, `inf · 0`). Las dos inversas rechazan entradas no finitas y concentraciones
reconstruidas no finitas con `CompositionalReconstructionError`, una subclase de `ValueError`,
para que la evaluación registre el fold fallido en vez de aceptar una predicción inválida.

La política versionada en `models.composition` es `NONNEGATIVITY_POLICY_VERSION = "1.0.0"`,
`NONNEGATIVITY_POLICY = "intrinsic_softmax"` y `UNREPRESENTABLE_OUTPUT = "fail_fold"`. Las
ejecuciones de evaluación composicional la registran en `run.json`; no aplica al pipeline clásico,
que predice concentraciones directamente. Los reportes históricos no se regeneran ni modifican.
No se aplica una salida acotada ni una penalización redundante: las restricciones de no
negatividad sobre estas concentraciones reconstruidas no pueden violarse para resultados finitos,
por lo que su VR cero no constituye evidencia de mejora del modelo. Baselines que predicen
concentraciones directamente pueden seguir teniendo violaciones. No hay cambio de geometría del
modelo.

## Contrato y entradas

`ConstraintMetadata` registra nombre estable, tipo (`inequality`/`equality`), espacio
(`fractions`/`concentrations`), unidad, tolerancia, versión individual y estado. Cada
`FunctionalConstraint` asocia esos metadatos con un operador que devuelve un escalar por muestra.
Las restricciones de igualdad usan `epsilon` como tolerancia; las desigualdades requieren
tolerancia cero.

`ConstraintInputs` transporta tensores en unidades reales. Para salidas composicionales,
`compositional_constraint_inputs(output)` recibe el tensor **ya des-escalado** `[B, 3]` en el
orden `(z1, z2, ln T)`. Usa la inversa tensorial canónica de `models.gnn.target` y produce
fracciones y concentraciones en `mmol/kg`. El módulo no importa `models.training`, no accede al
escalador y no acepta targets estandarizados como si fueran magnitudes físicas. La conversión no
altera la pérdida ni el bucle de entrenamiento.

Los operadores devuelven un valor `h` o `g` por muestra. La magnitud se calcula como:

```text
v = relu(h)                 para h <= 0
v = relu(abs(g) - epsilon)  para |g| <= epsilon
```

La magnitud conserva el grafo de Torch para la optimización. Una muestra se considera violada
solo cuando `v > 0`; la frontera exacta de la tolerancia no cuenta como violación.

## Evaluación, registros y resumen

`evaluate_constraints(inputs, sample_ids, constraints=None, valid_mask=None)` evalúa por defecto
exactamente las siete restricciones estructurales; D-06 solo se evalúa si se incluye explícitamente
en `constraints`. `valid_mask`, si se proporciona, debe tener forma `[B]`
y ser booleana. Las muestras excluidas no producen registros ni contribuyen a VR, VMM, VMM
condicional, VWM, P95 o FR; `excluded_sample_count` queda registrado en el resumen. Se requiere
al menos una muestra válida.

Cada `ViolationRecord` identifica `sample_id`, restricción, tipo, valor firmado del operador,
magnitud, indicador `violated` y unidad. El resumen por restricción contiene:

- `VR_percent`: porcentaje de magnitudes estrictamente mayores que cero.
- `VMM`: media de magnitud sobre todas las muestras válidas.
- `VMM_conditional`: media solo entre violaciones; `null` si ninguna muestra viola.
- `VWM`: máxima magnitud.
- `P95`: percentil 95 con cuantil lineal, equivalente al predeterminado de `numpy.quantile` y
  `torch.quantile`.
- `FR_percent`: porcentaje que satisface simultáneamente todas las restricciones activas.

Las predicciones no finitas en muestras incluidas, o una salida no válida de un operador, causan
`ConstraintEvaluationError`; no se sustituyen ni se omiten silenciosamente. El evaluador de
validación cruzada es responsable de clasificar un fold fallido; esa integración queda fuera de
#163. Las muestras excluidas no se evalúan, incluso si sus tensores contienen valores no finitos.

Los metadatos y resúmenes proporcionan `to_dict()` con valores serializables a JSON para
incorporarlos en `run.json` según §8 del protocolo.

## Penalización y objetivo de entrenamiento composicional

`constraint_penalty(results, weights)` calcula:

```text
sum(lambda[name] * mean(v[name] ** 2) for each active constraint)
```

`weights` es obligatorio y debe contener exactamente un peso por cada restricción evaluada.
Un peso faltante, desconocido, negativo, booleano o no finito produce `ConstraintEvaluationError`.
La penalización es diferenciable y se integra en el entrenamiento composicional como
`L_total = L_datos + constraint_lambda * L_bio`. `constraint_lambda` es configurable en
`TrainingConfig` y su valor por defecto es `0.0`; con cero, el entrenamiento no des-escala la
salida ni reconstruye o evalúa restricciones.

Para el objetivo de entrenamiento, `L_bio` es la suma de las medias de `magnitudes**2` de los
términos seleccionados. El mapa que se pasa a `constraint_penalty` asigna explícitamente el peso
unitario a cada término; es una convención de agregación técnica, no un peso científico ni una
afirmación de importancia equivalente entre restricciones con unidades o escalas distintas. El
lambda global configurable se aplica una sola vez sobre esa suma. No se asignan valores
predeterminados ni se recomienda un valor de lambda distinto de cero.

`constraint_terms` acepta nombres únicos del catálogo compartido `constraint_catalog()`, que
contiene las siete restricciones estructurales y la cota D-06. Si `constraint_lambda > 0`, debe
contener al menos un término. La salida composicional se
des-escala de manera diferenciable, reconstruye fracciones/concentraciones y pasa la máscara de
animales válidos a `evaluate_constraints`; los animales enmascarados no aportan a la penalización.
Si un lote no tiene animales válidos, su penalización es cero conectada al grafo de cómputo. Una
`CompositionalReconstructionError` se propaga para que el fold quede registrado como fallido,
nunca se reemplaza por una penalización de cero.

La detención temprana composicional usa `val_total_loss` en el val interno del train del fold.
Este subconjunto no es el test externo; la selección de lambda con datos externos queda fuera de
alcance y corresponde a A68-P1. Las restricciones estructurales disponibles son redundantes con
la reconstrucción composicional (su penalización normalmente es cero); la cota de D-06 no es
redundante y puede violarse con una salida composicional.

Los nombres estructurales disponibles actualmente son:

```text
structural.non_negative.fractions.acetate
structural.non_negative.fractions.propionate
structural.non_negative.fractions.butyrate
structural.non_negative.concentrations.acetate
structural.non_negative.concentrations.propionate
structural.non_negative.concentrations.butyrate
structural.simplex_closure
```

La restricción bioquímica activa es:

```text
d06.hydrogen.propionate_bound
```

Ejemplo de uso:

```python
inputs = compositional_constraint_inputs(output_descaled)
evaluation = evaluate_constraints(inputs, sample_ids, valid_mask=valid_samples)
penalty = constraint_penalty(
    evaluation.results,
    {result.metadata.name: 1.0 for result in evaluation.results},
)
loss_bio = penalty
loss_total = loss_data + constraint_lambda * loss_bio
run_metadata["constraints"] = evaluation.summary.to_dict()
```

Los pesos unitarios por término son la convención de agregación descrita arriba. El lambda global
se conserva junto con los términos seleccionados en la configuración completa de `run.json`;
`run.json` también conserva la procedencia D-06 si se selecciona esta restricción. `history.csv` o
`training_history.csv` registran pérdidas de datos, bio y total por época y subconjunto. Los
artefactos incluyen también `CONSTRAINTS_CONTRACT_VERSION` y la política versionada de no
negatividad.

## Dependencia y verificación

La evaluación requiere Torch; la adaptación composicional utiliza `models.gnn.target` y por ello
el extra opcional `graph`. El paquete no depende de `models.training`. Las pruebas cubren
fronteras, máscaras, métricas/serialización, validaciones de peso, gradientes y la procedencia
aprobada de D-06. No entrenan una GNN ni leen datos reales o artefactos.

### Política numérica de las pruebas

Las tolerancias de estas pruebas verifican redondeo de coma flotante; no cambian las tolerancias
de los metadatos ni el criterio científico de violación:

- Para expresiones aritméticas binarias con valores representables exactamente (por ejemplo,
  `0.125`, `0.25` y `0.5`), los tests comparan valores y gradientes con igualdad exacta.
- Para resultados de `log`, `exp` y `softmax` en `float32`, se usa `rtol=1e-6` y `atol=1e-8`.
  La tolerancia relativa cubre el error proporcional a la magnitud (por ejemplo, unas `5e-5`
  alrededor de `50`); la tolerancia absoluta pequeña cubre resultados cercanos a cero.
- Para las mismas operaciones en `float64`, se usa `rtol=1e-12` y `atol=1e-12`.
- Las comparaciones existentes que usan `pytest.approx` especifican como máximo la tolerancia
  predeterminada de pytest (`rel=1e-6`, `abs=1e-12`), salvo la tabla 6 de D-06: sus valores
  publicados redondean el operador a dos decimales y las fracciones a tres, por lo que su test
  declara `rel=0`, `abs=0.0051` y explica esa procedencia junto a la aserción.
- Para el cierre simplex fuera de tolerancia, el test compara la magnitud `0.25 - 1e-6` con
  `rel=1e-12`, `abs=1e-12`; el booleano de violación se verifica por separado. La cota D-06 y
  las desigualdades estructurales conservan tolerancia contractual cero.

La ida y vuelta escalar sigue usando `ROUND_TRIP_RTOL = 1e-9` documentado por
`models.composition`; no se sustituye por una comparación más laxa.

### Ejecución sin omisiones silenciosas

Sin `NUTRIGRAPHDT_REQUIRE_GRAPH=1`, se conserva el comportamiento opcional existente:
`pytest.importorskip` puede omitir pruebas que necesitan Torch o PyTorch Geometric. Para exigir
el extra, `tests/conftest.py` importa ambos paquetes durante la configuración de pytest y aborta
con `UsageError` si alguno no se puede importar; así, esas pruebas no pueden convertirse en skips
por falta del extra. Ejecutar y revisar el resumen de skips con:

```bash
NUTRIGRAPHDT_REQUIRE_GRAPH=1 python -m pytest -ra
```

En ese modo, las pruebas de restricciones y reconstrucción no deberían omitirse; cualquier skip
restante debe ser de pruebas de gráficos no disponibles en el entorno y su razón debe aparecer en
el resumen `-ra`.

El cumplimiento matemático no valida por sí mismo los supuestos biológicos.
