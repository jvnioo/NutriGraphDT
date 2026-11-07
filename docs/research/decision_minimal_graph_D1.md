# Decisión: grafo mínimo de D1 y alcance de la ruta mecanística este semestre

**Emite:** Investigación. **Estado:** versión 1.0, pendiente de emisión por el sublíder (#256).
**Fecha:** 2026-11-07.
**Issues:** #256. Reúne las decisiones de #236 (tabla S-04), #239 (identidad de los taxones),
#257 (`produces`) y #258 (dieta y sustratos), cada una en su PR. Contraparte: #185, #175, #173 y
#174.

**Respuesta corta.** El grafo mínimo de D1 de este semestre tiene **cinco tipos de nodo**
(`host`, `diet`, `taxon`, `function` y `metabolite`) y **tres relaciones**: `measured_in`, que ya
existe, más `has_capacity` y `produces`, que se implementan. Cubre el tramo
`taxón → función → metabolito → huésped` de la ruta mecanística. El tramo inicial
`dieta → sustrato → taxón` se **declara como limitación**, y las seis relaciones restantes quedan
fuera de D1. Con ese grafo, D1 puede preguntar si la abundancia de los géneros con capacidad
anotada mejora la predicción de la composición de AGCC por sobre el diseño. No puede decir nada del
efecto de la dieta a través del microbioma. **Ninguna evaluación de D1 se llamará «mecanística»**:
no hay un umbral con fuente, y la cobertura real es baja, sobre todo para el propionato (0,9 % del
total de lecturas). La exclusión de las aristas `hypothetical` **rige también en F5 a F7**. #185
debe esperar a #175 y a la identidad de los taxones, no a lo demás.

## 1. Decisión por relación

Estado de partida, medido por Desarrollo el 04-11-2026 en los 185 grafos de `main` (`c016a82`):
1 de las 11 relaciones y 4 de los 8 tipos de nodo.

| Relación | Decisión | Justificación | Dónde se decide |
|---|---|---|---|
| `metabolite → measured_in → host` | **Se mantiene** | Ya implementada; es `observed`. | — |
| `taxon → has_capacity → function` | **Implementar este semestre** | 46 géneros `1:1` con el catálogo (37,0 % de las lecturas a género) hacia 9 KO. | #236, #257 → #175 |
| `function → produces → metabolite` | **Implementar este semestre** | 9 relaciones anotadas en KEGG Release 120.0, iguales en todos los grafos. | #257 |
| `diet → provides → substrate` | **Limitación declarada** | La dieta basal es común a los tratamientos y repite las covariables (LIM-4). | #258 |
| `substrate → available_to → taxon` | **Limitación declarada** | Solo admite `inferred` y no tiene fuente que no use los datos de evaluación. | #258 |
| `host → exhibits → phenotype` | **Fuera de D1** (ya decidida) | Los promedios de corral no son fenotipo del animal (V-04). | 16-10-2026 |
| `additive → modulates → taxon` | **Fuera de D1** | `hypothetical`; ver sección 3. | 16-10-2026 y esta decisión |
| `additive → modulates → function` | **Fuera de D1** | Ídem. | Ídem |
| `metabolite → associated_with → phenotype` | **Fuera de D1** | Ídem; además no hay nodos `phenotype` (V-04). | Ídem |
| `taxon → interacts_with → taxon` | **Fuera de D1** | Ídem; una interacción inferida por coocurrencia está prohibida (Esquema §2.2). | Ídem |
| `function → cross_feeds → function` | **Fuera de D1** | Ídem. El intercambio de lactato queda como limitación (#257, sección 3). | Ídem |

**«Fuera de D1»** quiere decir que la relación no se construye en ningún grafo real ni derivado de
uno real. Las once siguen en el grafo sintético.

## 2. Grafo mínimo de D1

| Tipo de nodo | Contenido | Atributos que entran a `x` |
|---|---|---|
| `host` | Un nodo por animal | Covariables de entrada del contrato v2 §3 |
| `diet` | Un nodo por animal | Tratamiento (#176) |
| `taxon` | Géneros y residuales del rango más profundo (contrato v2 §6) | Abundancia combinada con la familia (#239) |
| `function` | Hasta 9 KO (#257) | Los fija Desarrollo; sin valores medidos |
| `metabolite` | Los tres AGCC objetivo; los demás medidos, sin aristas `produces` | Sin el valor medido (contrato v2 §1) |

| Relación | Origen de las aristas |
|---|---|
| `metabolite → measured_in → host` | Medición del animal (`observed`) |
| `taxon → has_capacity → function` | Tabla S-04 de #236 y anotación del catálogo (`annotated`) |
| `function → produces → metabolite` | `configs/functions/scfa_produces_d1.tsv` (`annotated`) |

**Requisitos que el grafo mínimo da por cumplidos:**

1. **Rango de género.** Los grafos guardados tienen hoy 472 nodos de especie, 467 de género y 378
   de rangos superiores (#256). El contrato v2 §6 fija el género como rango de trabajo. Las
   especies se agregan a su género antes de crear las aristas. Desarrollo revisa la configuración.
2. **La identidad de los taxones se combina con su abundancia** antes de la lectura (#239). Si no,
   el bloque `taxon` vuelve a ser constante entre animales.
3. **Los residuales no reciben aristas funcionales** (contrato v2 §6).

## 3. Las aristas `hypothetical` después de F4

**Decisión: la exclusión rige en F5, F6 y F7.** Ningún grafo real, ni ninguna instancia derivada
de uno real (V-02), lleva aristas `hypothetical`. Siguen permitidas solo en el grafo sintético.

- **F5 (entrenamiento con restricciones):** el motivo de F4 sigue igual. Una arista sin respaldo
  empírico le daría al modelo una estructura que se aprende como si fuera cierta.
- **F6 (escenarios):** las instancias derivadas se evalúan con el modelo entrenado en D1, así que
  deben tener los mismos tipos de arista que su origen. INS-06 e INS-07 solo admiten cambios en las
  variables declaradas.
- **F7 (explicabilidad):** en D1 no habrá aristas `hypothetical` que explicar. La regla C-03 de la
  respuesta a A55 (estilo propio y leyenda «hipotética») se aplica cuando existen, es decir, en el
  grafo sintético.

Reabrir esta decisión exigiría evidencia nueva para alguna de esas relaciones, no un cambio de fase.

## 4. Qué se puede y qué no se puede afirmar

**Pregunta que el grafo mínimo puede responder:** ¿la abundancia de los géneros con capacidad
anotada para liberar cada AGCC, junto con el perfil por familia, mejora la predicción de la
composición de AGCC del ciego por sobre el diseño (día, ensayo, sexo, línea y tratamiento)?

| Se puede afirmar | No se puede afirmar |
|---|---|
| Si el modelo con microbioma supera a `ridge_design` y a `ridge` con la tabla por familia, con la dispersión entre folds y semillas | Que la dieta o los aditivos actúen a través del microbioma (#258) |
| Qué géneros y qué KO pesan en la predicción, con estado `annotated` en la ruta | Que una función esté activa o tenga un flujo: `has_capacity` es capacidad anotada |
| Asociaciones del perfil por familia con la composición de AGCC | Un mecanismo para el propionato: solo el 2,1 % de las lecturas a género tiene ruta hacia él |
| Diferencias entre tratamientos, como exploratorias (L1) | Una causa: D1 es observacional dentro de cada tratamiento |

## 5. Criterio de suficiencia

**No hay un umbral con fuente** de cobertura a partir del cual una evaluación pueda llamarse
«mecanística», ni en la literatura revisada para S-04 y #257 ni en las decisiones previas del
proyecto. Fijarlo ahora sería inventar un valor. Por eso:

1. **Ninguna evaluación de D1 se llama «mecanística».** Se usa «con estructura funcional
   anotada».
2. **Toda evaluación y toda explicación de D1 informan la cobertura** de la ruta por AGCC, como
   fracción de las lecturas a género y del total:

   | AGCC | Géneros con ruta | % lecturas a género | % del total de lecturas |
   |---|---:|---:|---:|
   | Acetato | 35 | 36,1 | 16,1 |
   | n-Butirato | 14 | 35,8 | 16,0 |
   | Propionato | 7 | 2,1 | 0,9 |

   Calculada con la tabla de #236 y la vista previa de #257. *Faecalibacterium* aporta 28,0 puntos
   en acetato y en butirato.
3. Si una versión futura del grafo cambia mucho la cobertura, por ejemplo con el perfilado contra
   el catálogo del piloto de R-03, el criterio se revisa con esa evidencia.

## 6. #185 y el orden del trabajo

**#185 debe esperar al grafo mínimo, pero solo a dos partes de él:**

| Dependencia | ¿Bloquea la corrida de D1 de #185? | Motivo |
|---|---|---|
| #175: `has_capacity` hacia los 9 KO | **Sí** | Sin ella, los nodos `function` no existen. |
| Identidad de los taxones (#239, implementación) | **Sí** | Sin ella, el bloque `taxon` es constante y la corrida mide solo las covariables, que es lo que motivó la pausa del 02-11-2026. |
| `produces` (#257) | No | Solo llega a la predicción con 3 capas. Conviene incluirlo en la misma reconstrucción para no repetir corridas. |
| Dieta y sustratos (#258) | No | Declarado como limitación. |

Con las decisiones de Investigación emitidas, #185 deja de esperar a Investigación: #236 y #239
quedan resueltas, y el bloqueo pasa a ser la implementación de Desarrollo. Se sugiere a Desarrollo:

1. **#175**: usar la tabla de #236, los 9 KO y la regla de agregación de #257. Admitir
   `mgnify-chicken-gut` como base de `has_capacity` en las reglas (#236, sección 7).
2. **Issue nueva**: identidad de los taxones (#239, sección 4) con la comparación técnica de cinco
   brazos. Bloquea a #185.
3. **Issue nueva o dentro de #175**: cargar las 9 aristas `produces`.
4. **#173**: regenerar el reporte una sola vez, con las aristas y la agregación a género.
5. **#174**: revisión de procedencia por Investigación sobre ese reporte.
6. **Corregir `docs/models/gnn-d1-composition.md`**, que dice que la GNN usa los taxones «como un
   baseline tabular» (#239, sección 1).
7. **Guía del informe y demo:** declarar que el grafo sintético tiene las 11 relaciones y el de D1,
   las 3 de este documento. Así la demo no da a entender que el grafo real está completo (#256).

## 7. Supuestos y limitaciones

1. Las cifras de cobertura dependen de la tabla de #236 y de la anotación de #257, que aún no
   están en `main`. Si cambian, la sección 5 se recalcula con sus scripts.
2. La cobertura se mide sobre los 185 animales con metagenoma. En la cohorte de 56 puede variar
   algunos puntos.
3. Las limitaciones de cada decisión siguen vigentes: L2 (residuales sin ruta funcional), la
   cobertura del propionato y *but* sin KO (#257), y LIM-1 y LIM-4 (#258).
4. No se usa ningún servicio de pago.

## Emisión y control de versiones

**Tabla A.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | Decisión: grafo mínimo de D1 y alcance de la ruta mecanística este semestre |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | Issue #256 |
| Versión | 1.0 |
| Estado | **Pendiente de emisión.** El sublíder confirma las secciones 1, 3, 5 y 6. |

**Tabla B.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 1.0 | 07-11-2026 | Decisión por relación, grafo mínimo, `hypothetical` después de F4, criterio de suficiencia y dependencias de #185. | Investigación, para emisión del sublíder |
