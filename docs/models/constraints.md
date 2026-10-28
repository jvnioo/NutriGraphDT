# Interfaz de restricciones y registro de violaciones (A57-P1, #163)

`nutrigraphdt.constraints` define operadores tensoriales diferenciables, penalizaciones
independientes de la pérdida de datos y registros por muestra. El contrato de metadatos está
versionado con `CONSTRAINTS_CONTRACT_VERSION = "1.0.0"` para incluirse en `run.json`.

## Alcance y estado científico

Esta primera versión activa solo restricciones estructurales:

- No negatividad de las fracciones molares de acetato, propionato y butirato.
- No negatividad de las concentraciones correspondientes en `mmol/kg`.
- Cierre simplex de las fracciones: `sum(p) = 1`, con tolerancia numérica adimensional
  `STRUCTURAL_CLOSURE_TOLERANCE = 1e-6`.

La tolerancia de cierre es una decisión numérica explícita para la precisión de los tensores,
no una tolerancia fisiológica. No se asigna tolerancia a las desigualdades: su operador usa
`h <= 0`. Las ecuaciones bioquímicas, balances y rangos fisiológicos de D-06 no se implementan.
`ConstraintStatus.PENDING_D06` está disponible como valor de metadatos, pero no se crean clases
ni operadores ficticios para esas restricciones. El estado pendiente de D-06 y la limitación
estructural siguen siendo los descritos en el [protocolo de evaluación](constraints-evaluation-protocol.md#3-taxonomía-de-restricciones-y-métricas-de-violaciones-f5--d-06)
y la observación [P-07](explanations-protocol-review.md#31-protocolo-de-evaluación-a55-p1).

Para salidas composicionales `(z1, z2, ln T)`, la no negatividad es una garantía matemática de
la inversa `softmax · exp(ln T)`. En coma flotante, una fracción puede subdesbordarse a cero y
una concentración puede ser cero; valores no representables pueden producir overflow o `NaN`
(por ejemplo, `inf · 0`). Las dos inversas rechazan entradas no finitas y concentraciones
reconstruidas no finitas con `CompositionalReconstructionError`, una subclase de `ValueError`,
para que la evaluación registre el fold fallido en vez de aceptar una predicción inválida.

La política versionada en `models.composition` es `NONNEGATIVITY_POLICY_VERSION = "1.0.0"`,
`NONNEGATIVITY_POLICY = "intrinsic_softmax"` y `UNREPRESENTABLE_OUTPUT = "fail_fold"`. Las
ejecuciones futuras la registran en `run.json`; los reportes históricos no se regeneran ni
modifican. No se aplica una salida acotada ni una penalización redundante: las restricciones de
no negatividad sobre estas concentraciones reconstruidas no pueden violarse para resultados
finitos, por lo que su VR cero no constituye evidencia de mejora del modelo. Baselines que
predicen concentraciones directamente pueden seguir teniendo violaciones. No hay cambio de
geometría del modelo.

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
las siete restricciones estructurales. `valid_mask`, si se proporciona, debe tener forma `[B]`
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

## Penalización independiente de la pérdida de datos

`constraint_penalty(results, weights)` calcula:

```text
sum(lambda[name] * mean(v[name] ** 2) for each active constraint)
```

`weights` es obligatorio y debe contener exactamente un lambda por cada restricción evaluada.
Un peso faltante, desconocido, negativo, booleano o no finito produce `ConstraintEvaluationError`.
La penalización es diferenciable y puede sumarse desde el consumidor a la pérdida de datos; no
se integra en `train_compositional_model` ni en las GNN en este Issue. **La elección y ajuste de
los valores lambda queda fuera del alcance de #163**.

Ejemplo de uso:

```python
inputs = compositional_constraint_inputs(output_descaled)
evaluation = evaluate_constraints(inputs, sample_ids, valid_mask=valid_samples)
penalty = constraint_penalty(
    evaluation.results,
    {result.metadata.name: chosen_weight for result in evaluation.results},
)
loss_total = loss_data + penalty
run_metadata["constraints"] = evaluation.summary.to_dict()
```

Los pesos del ejemplo son proporcionados explícitamente por quien integra el término; no existen
valores predeterminados en el paquete.

## Dependencia y verificación

La evaluación requiere Torch; la adaptación composicional utiliza `models.gnn.target` y por ello
el extra opcional `graph`. El paquete no depende de `models.training`. Las pruebas cubren
fronteras, máscaras, métricas/serialización, validaciones de peso y gradientes. El cumplimiento
matemático estructural no constituye validación de ecuaciones ni evidencia biológica.
