# Alcance de la etapa final: plataforma, simulación y entrega con datos sintéticos

- **Emite:** Desarrollo. **Vigente desde:** 18-11-2026. **Issue:** #296.
- **Base:** la decisión de Investigación sobre el grafo mínimo de D1
  ([#256](../research/decision_minimal_graph_D1.md)). Este documento aplica esa decisión a la
  etapa final; no es una decisión nueva de Investigación ni se le atribuye su aprobación.
- **Actividades afectadas:** A88 a A139 (#297 a #384), listadas en la [sección 7](#7-actividades-restantes).

**Respuesta corta.** Los datos públicos disponibles no permiten reconstruir el flujo completo del
grafo, así que la plataforma web, la simulación de escenarios, la validación del sistema y la
entrega final usan **datos sintéticos**. El grafo de D1 (HoloFood) tiene 3 de las 11 relaciones del
esquema. No tiene ni el tramo `dieta → sustrato → taxón` ni ninguna arista de aditivos, que es
justamente lo que la plataforma debe simular. El dataset sintético tiene los 8 tipos de nodo y las
11 relaciones. El trabajo sobre D1 no se borra: queda como **resultado exploratorio** de lo que
permiten los datos públicos. Con datos sintéticos se puede demostrar que el flujo funciona de punta
a punta, pero no se puede afirmar ningún efecto biológico.

## 1. Decisión

1. La Web App (A88, A90, A97, A101 y A104), la simulación (A93 y A96) y las pruebas E2E (A105) usan
   la cohorte sintética (`build_synthetic_cohort`) y escenarios sintéticos
   (`generate_scenario_dataset` y el catálogo de `configs/scenarios/` de A93).
2. La validación del sistema completo (A117), la reproducibilidad (A115 y A120) y los artefactos
   de entrega (A124 a A139) usan la misma configuración sintética. Se reproducen sin descargar D1.
3. D1 no es fuente de la plataforma ni de la entrega. Sus resultados se citan como exploratorios.
4. Toda salida de la plataforma lleva el rótulo de datos sintéticos (sección 6).

## 2. Por qué

### 2.1 Qué relaciones tiene cada grafo

Tramos de la ruta mecanística del Esquema General y su estado en cada grafo. Las cifras de D1 vienen
de #256, sección 1, y del reporte de los grafos reales.

| Relación | D1 (HoloFood) | Sintético |
|---|---|---|
| `diet → provides → substrate` | Limitación declarada (#258) | Sí |
| `substrate → available_to → taxon` | Limitación declarada (#258) | Sí |
| `additive → modulates → taxon` | Fuera de D1 | Sí (relación hipotética) |
| `additive → modulates → function` | Fuera de D1 | Sí (relación hipotética) |
| `taxon → has_capacity → function` | Sí: 62 aristas de 38 géneros hacia 7 KO | Sí |
| `function → produces → metabolite` | Sí: 7 aristas | Sí |
| `metabolite → measured_in → host` | Sí (`observed`) | Sí |
| `host → exhibits → phenotype` | Fuera de D1 | Sí |
| `metabolite → associated_with → phenotype` | Fuera de D1 | Sí (relación hipotética) |
| `taxon → interacts_with → taxon` | Fuera de D1 | Sí (relación hipotética) |
| `function → cross_feeds → function` | Fuera de D1 | Sí (relación hipotética) |

«Fuera de D1» quiere decir que la relación no se construye en ningún grafo real ni derivado de uno
real (#256, sección 3). En el grafo sintético todas las aristas tienen `evidence_status: synthetic`;
«hipotética» es el estado estructural de la relación en el contrato
([diccionario sintético](../synthetic-dataset/synthetic-dataset-dictionary.md)), no una evidencia.

### 2.2 Qué no se puede hacer con D1

- **Simular una dieta o un aditivo a través del microbioma.** Sin `provides`, `available_to` ni
  `modulates`, un cambio de dieta o de aditivo solo llega al modelo como atributo del nodo `diet`
  o `host`, no por la ruta mecanística. Investigación lo dice en #256: con ese grafo, D1 «no puede
  decir nada del efecto de la dieta a través del microbioma».
- **Mostrar el grafo completo.** La plataforma, el visualizador y la explicabilidad mostrarían un
  grafo con 3 de 11 relaciones.
- **Apoyarse en la capacidad predictiva del grafo.** En D1 el grafo no agrega capacidad predictiva
  demostrable frente a `ridge` sobre el diseño (#266 y #268, con 56 animales).

La página **Sintético frente a D1** de la demo (`scripts/demo_app.py`, [`docs/demo.md`](../demo.md))
muestra estas diferencias desde el código y queda como evidencia de esta decisión.

## 3. Qué cambia

| Frente | Antes | Desde esta decisión |
|---|---|---|
| Corrida de la plataforma | Corridas de demostración sintética y del fixture de D1 (A81, #286) | La corrida sintética de entrega (A117). El fixture de D1 queda como prueba del contrato. |
| Escenarios | Pares de DS-04 y ejemplos de `tests/fixtures/api/scenarios.json` | Catálogo versionado de `configs/scenarios/` (A93), sobre la cohorte sintética |
| Incertidumbre | Estimada en D1 (A75, #282) | Se extiende a la cohorte sintética para la plataforma (A101-P1, #330) |
| Validación del sistema | — | Pipeline sintético completo con configuración de entrega (A117) |
| Reproducibilidad | La guía requería descargar D1 | Clon limpio sin descarga; D1 queda como anexo opcional (A120) |
| Informe final | — | Sección de datos: por qué sintéticos, qué cubre D1 y qué no se puede afirmar (A133) |

## 4. Qué queda de D1

- **Código.** Los loaders, el constructor del grafo, la cohorte, la validación cruzada por corral y
  los scripts de D1 siguen en `main`, con sus pruebas sobre el fixture de `tests/fixtures/holofood/`.
- **Resultados.** Los documentos y reportes de D1 (`docs/models/*d1*`, `docs/models/uncertainty.md`,
  `reports/*/d1/` y similares) quedan como resultados exploratorios. No se borran ni se reescriben;
  llevan un aviso que remite a este documento.
- **Decisiones de Investigación.** Siguen vigentes para todo grafo real. Este documento no las
  modifica.
- **Descarga.** `scripts/fetch_holofood.py` deja de ser necesario para la entrega y solo hace falta
  para regenerar los resultados exploratorios.

## 5. Qué se puede afirmar y qué no

**Se puede afirmar**, con datos sintéticos:

- el flujo completo funciona de punta a punta sobre un grafo con el esquema completo: datos, grafo,
  modelo con restricciones, simulación, explicación e interfaz;
- se cumplen los contratos: invariancia de los escenarios, respuesta «no estimable» fuera de soporte
  (D-06 §7) y rótulos de evidencia;
- las corridas se reproducen desde un clon limpio.

**No se puede afirmar:**

- ningún efecto biológico de una dieta o un aditivo. Los targets sintéticos son independientes de
  la dieta y del aditivo: la especificación DS-01 no valida efectos de intervenciones, rangos
  fisiológicos ni causalidad. Una diferencia entre basal e intervenido describe al modelo;
- que las métricas sintéticas estimen el desempeño en animales reales;
- que una importancia del explicador sea un mecanismo biológico;
- que la plataforma recomiende una dieta o un aditivo. El README ya lo excluye.

## 6. Cómo se rotula

- **Interfaz:** rótulo permanente en todas las páginas, «Datos sintéticos: no describen animales
  reales», y la advertencia de que un escenario no es un efecto causal (`CAUSAL_WARNING` de A81).
- **Exportaciones y reportes:** `dataset_id = synthetic_cohort` y el rótulo en el encabezado.
- **Textos:** «datos sintéticos» o «cohorte sintética». No se usa «pollos simulados» ni otra
  expresión que sugiera animales reales.
- **Especie y segmento:** `chicken` y `cecum` son marcadores provisionales del generador
  ([diccionario](../synthetic-dataset/synthetic-dataset-dictionary.md)), no una población.

## 7. Actividades restantes

Cada actividad es una Issue con sus tareas como sub-Issues y se cierra con un solo PR contra `main`.
Las dependencias son nativas de GitHub. Estado inicial: `Blocked` si solo espera a #286 (A81, PR #295
en revisión) y `Backlog` si espera a otra actividad.

| Actividad | Issue | Tareas | Bloqueada por | Fase |
|---|---|---|---|---|
| A88 · Entorno Streamlit y estructura base de la Web App | #297 | #298 a #301 | #286 | F8 |
| A90 · Formulario de dieta, aditivos y parámetros | #302 | #303 a #307 | A88 | F8 |
| A93 · Escenarios de referencia y criterios de resultado | #308 | #309 a #313 | #286 | F6 |
| A96 · Integración en memoria del motor con Streamlit | #314 | #315 a #319 | A90, A93 | F8 |
| A97 · Visualizador del grafo heterogéneo | #320 | #321 a #324 | A88 | F8 |
| A100 · Prueba de usabilidad con Investigación | #325 | #326 a #328 | A101, A104 | F8 |
| A101 · Dashboard de resultados y métricas AGCC | #329 | #330 a #333 | A96 | F8 |
| A104 · Visualizador de explicabilidad | #334 | #335 a #337 | A96, A97 | F8 |
| A105 · Pruebas E2E de simulación e integración web | #338 | #339 a #342 | A101, A104 | F8 |
| A115 · Reproducibilidad y soporte de la entrega | #343 | #344 a #346 | A117 | F9 |
| A117 · Validación del sistema completo | #347 | #348 a #350 | A105 | F9 |
| A120 · Documentación técnica y guía de reproducibilidad | #351 | #352 a #355 | A115 | F9 |
| A123 · Demostración preliminar | #356 | #357 | A101, A104 | F9 |
| A124 · Artefactos de entrega | #358 | #359 a #361 | A120 | F9 |
| A125 · E2E y defectos críticos | #362 | #363 y #364 | A136 | F9 |
| A127 · Congelamiento y revisión final | #365 | #366 y #367 | A125 | F9 |
| A132 · Revisión interna y respuestas técnicas | #368 | #369 | A117 | F9 |
| A133 · Informe final y documentación técnica | #370 | #371 a #373 | A120, A132 | F9 |
| A134 · Ambiente de demostración | #374 | #375 a #377 | A123, A127 | F9 |
| A136 · Integración final | #378 | #379 y #380 | A124 | F9 |
| A139 · Ensayo y respaldo para la defensa | #381 | #382 a #384 | A132, A134 | F9 |

Orden resultante:

```text
#286 (A81) → A88 → A90, A97
#286 (A81) → A93
A90 + A93  → A96 → A101
A96 + A97  → A104
A101 + A104 → A100, A105, A123
A105 → A117 → A115 → A120 → A124 → A136 → A125 → A127
A117 → A132
A120 + A132 → A133
A123 + A127 → A134
A132 + A134 → A139
```

Dos decisiones de orden que no están en el plan original:

- **La «rama de entrega» es `main`.** No se crea una rama paralela: los PR de las actividades se
  fusionan en `main` (AGENTS.md). Por eso la integración final (A136) va antes de las pruebas E2E
  sobre la entrega (A125) y del congelamiento con etiqueta (A127).
- **«GNN/PINNs» (A96)** se refiere a la GNN entrenada con restricciones bioquímicas
  (`L_datos + λ·L_bio`, A57 y A68). No hay una red PINN aparte.

## 8. Preguntas abiertas

- **Efecto esperado en las pruebas.** Como los targets sintéticos no dependen de la intervención,
  las pruebas E2E pueden comprobar el flujo y los contratos, pero no un efecto esperado. Una ruta
  plantada como la de las pruebas de explicabilidad (`tests/integration/test_planted_route_recovery.py`,
  A60-P4) permitiría verificar un efecto conocido. Agregarla al generador cambia el contrato
  sintético y se decide en A93; no se adopta aquí.
- **Especie y segmento.** `chicken` y `cecum` siguen siendo marcadores provisionales de DS-01.
- **Vocabulario intervenible.** Las preguntas de A81 sobre qué variables se pueden intervenir
  (`docs/architecture/api-contract.md`, PR #295) se resuelven ahora sobre la cohorte sintética.
