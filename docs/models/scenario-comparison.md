# Comparación de escenarios y criterios de resultado (A93, #308)

- **Issues:** A93-P1 (#309), A93-P2 (#310), A93-P3 (#311), A93-P4 (#312).
- **Código:** `nutrigraphdt.simulation` (`catalog.py`, `compare.py`).
- **Catálogo:** [`configs/scenarios/`](../../configs/scenarios/README.md).
- **Pruebas:** `tests/unit/test_simulation_catalog.py`, `tests/unit/test_simulation_compare.py`
  y `tests/integration/test_simulation_scenarios.py`.

> **Datos sintéticos.** Todos los escenarios derivan de la cohorte sintética
> (`build_synthetic_cohort`) y los responde la corrida sintética congelada de
> `tests/fixtures/api/frozen_runs/synthetic`. Los targets sintéticos son independientes de la
> dieta y del aditivo (DS-01): una diferencia entre un escenario y su basal **describe al
> modelo, no un efecto biológico**. Ver [alcance de la etapa final](../process/final-scope.md).

## 1. Qué se compara

Un escenario es una petición del contrato de `nutrigraphdt.api` (`ScenarioRequest`): un animal
base y las variables que cambian. Su **basal** es la misma petición sin intervención, sobre el
mismo animal.

`compare_scenario(engine, request)` predice los dos con **el mismo** `ScenarioEngine`: la corrida
se carga una vez y no se entrena nada. La comparación (`ScenarioComparison`) registra la corrida
(`ModelRef`) y el SHA-256 de su `checkpoint.pt`, y se niega a construirse si las dos respuestas
informan corridas distintas. Si basal e intervenido usaran modelos distintos, la diferencia
mezclaría el cambio del escenario con el del modelo.

## 2. Diferencia por AGCC

El modelo predice la composición de AGCC con el contrato de datos v2 (`z1`, `z2` y `ln T`); el
contrato de la API la devuelve como fracciones molares y `ln T`. La comparación informa, para
cada cantidad, el valor basal, el intervenido y la diferencia `intervenido − basal`:

| Cantidad | Unidad del valor | Unidad de la diferencia |
|---|---|---|
| `acetate`, `propionate`, `butyrate` | fracción molar (adimensional; las tres suman 1) | fracción molar (adimensional; las tres diferencias suman 0) |
| `log_total` | `ln(mmol/kg de digesta fresca)` | `ln(T_int / T_basal)` (adimensional) |

La diferencia de `ln T` es el logaritmo del cociente de los totales: `0` es el mismo total y
`ln 2 ≈ 0,69` es el doble. Se informa así porque el modelo predice `ln T`, no `T`.

## 3. «No estimable»

Una predicción fuera del soporte empírico del train de la corrida es `no_estimable` y no lleva
números (D-06 §7; `nutrigraphdt.scenarios.support`). En una comparación:

- si el basal **o** el intervenido es `no_estimable`, la comparación es `no_estimable`;
- una comparación `no_estimable` no lleva ninguna diferencia numérica (`differences` vacío) y
  declara los motivos de cada lado, con el prefijo `basal:` o `intervenido:`;
- `ScenarioComparison` lo exige al validarse, así que no se puede construir una comparación que
  informe un número cuando un lado no es estimable.

## 4. Advertencias

Toda comparación lleva `CAUSAL_WARNING` (un escenario no es un efecto causal) y
`DIFFERENCE_WARNING` (la diferencia es la de dos predicciones del mismo modelo). Si la corrida es
sintética, también `SYNTHETIC_WARNING`. Las advertencias del escenario intervenido (por ejemplo,
una entrada fuera de lo observado en el train) se conservan.

## 5. Invariancia

La regla de DS-04 llevada a la simulación: el escenario intervenido difiere de su basal **solo en
las variables declaradas**. Las pruebas recorren todo el catálogo y comparan la instancia derivada
de cada escenario con la del basal del mismo animal: los nodos, las aristas, las máscaras de
faltantes y las evidencias son iguales salvo el atributo intervenido. Una intervención nula (fijar
una variable en el valor que ya tiene el animal) da la misma predicción que el basal y una
diferencia exactamente cero.

## 6. Lo que no se define

- **Umbral de «diferencia relevante».** No hay una fuente en `docs/research/` que lo fije, así que
  no se define. Queda como pregunta abierta para Investigación; mientras tanto se informa la
  diferencia sin calificarla.
- **Intervalo de la diferencia.** El contrato v1 no calcula intervalos predictivos (campo
  reservado para A75); la incertidumbre de la cohorte sintética es A101-P1 (#330).
- **Efecto esperado en las pruebas.** El alcance final (#296, sección 8) dejó para A93 decidir si
  se agrega al generador una ruta plantada con efecto conocido. **No se agrega**: cambiaría el
  contrato sintético DS-01 y exige una decisión de Investigación. Las pruebas verifican el flujo y
  los contratos (estado esperado, invariancia, mismo modelo, intervención nula), no un efecto.
