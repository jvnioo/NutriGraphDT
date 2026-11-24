# Catálogo de escenarios de referencia (A93-P2, #310)

Este directorio contiene los archivos de configuración versionados para los escenarios
de referencia sintéticos de NutriGraphDT.

## Formato

Cada escenario se describe en un archivo JSON con los campos:

| Campo | Tipo | Descripción |
|---|---|---|
| `schema_version` | `str` | Versión del esquema de configuración (`"1.0.0"`). |
| `scenario_id` | `str` | Identificador canónico del escenario. |
| `label` | `str` | Nombre corto legible. |
| `description` | `str` | Descripción del escenario. |
| `intervention_variable` | `str \| null` | Variable intervenida (`null` para el basal). |
| `intervention_basal_value` | `number \| null` | Valor basal de la variable. |
| `intervention_intervened_value` | `number \| null` | Valor intervenido de la variable. |
| `intervention_unit` | `str \| null` | Unidad de la variable intervenida. |
| `is_synthetic` | `bool` | Siempre `true` para los escenarios de referencia. |
| `synthetic_data_warning` | `str` | Advertencia de datos sintéticos (D-06 §7). |
| `source` | `str` | Módulo generador. |

## Escenarios disponibles

| Archivo | `scenario_id` | Descripción |
|---|---|---|
| `basal_v1.json` | `synthetic:scenario:basal:0001` | Escenario basal (proteína bruta 215 g/kg). |
| `intervened_v1.json` | `synthetic:scenario:intervened:0001` | Escenario intervenido (proteína bruta 270 g/kg). |

## Notas

- Los escenarios son **sintéticos**. No representan observaciones reales ni efectos biológicos.
- Los targets de los escenarios son independientes de la dieta y del aditivo (DS-01): una
  diferencia entre escenarios describe el comportamiento del modelo, no un efecto biológico.
- Una predicción fuera del soporte empírico del train se devuelve como **«no estimable»** y
  no como número (D-06 §7, `nutrigraphdt.scenarios.EmpiricalSupport`).
