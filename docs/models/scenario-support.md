# Control de soporte empírico de las predicciones de escenarios (F6, #245)

Los escenarios de F6 extrapolan, así que un modelo puede predecir una composición de AGCC que
nunca vio. D-06 §7 recomienda que esas predicciones se informen como **«no estimable»**, con su
motivo, en vez de como un número. `nutrigraphdt.scenarios.support` implementa ese control.

## Cómo funciona

- **Soporte (`EmpiricalSupport.fit`).** Para cada fracción molar $p_k$ (acetato, propionato y
  n-butirato), el soporte es $[L_k, U_k]$: el mínimo y el máximo de $p_k$ **en el conjunto con
  que se entrenó el modelo congelado**. Se usan el mínimo y el máximo para no introducir un
  percentil sin fuente (D-06 §7). Con días de muestreo se calcula, además, un intervalo por día.
- **Desde una corrida (`support_from_run`).** Toma los animales de `sample_ids.train` del
  `run.json` de la corrida (#180): el train interno con que se ajustaron los pesos. El val
  interno y el test del fold no entran (`test_run_support_uses_only_the_training_animals`).
- **Control (`EmpiricalSupport.check`).** Una predicción es `estimable` si todas sus fracciones
  caen en $[L_k, U_k]$, con los extremos incluidos. Si alguna queda fuera, es `no_estimable`:
  `fractions` vale `None`, para que no se informe como número, y `reasons` dice qué fracción,
  con qué valor y fuera de qué intervalo. Con soporte por día, un día sin animales de
  entrenamiento también es `no_estimable`.
- **Registro.** Cada resultado lleva el intervalo aplicado y el subconjunto fuente (`source`), y
  `EmpiricalSupport.to_dict()` da el soporte con su método y su versión.

## Qué no es

No es una restricción bioquímica ni entra en la pérdida, en la decisión de F5 ni en las
restricciones de D-06. Es un control de cobertura. No fija ningún umbral: los límites salen de
los datos de entrenamiento.

## Pendiente

Integrarlo con el motor de escenarios de F6 cuando exista: cada escenario calcula el soporte del
modelo que usa y lo aplica a sus predicciones antes de informarlas.
