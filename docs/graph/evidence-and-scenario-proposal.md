# Propuesta: evidencia de aristas y escenario de instancias reales

- **Estado:** propuesta **provisional** de Desarrollo, aplicada en las reglas de integridad
  `1.2.0`. Investigación aún no entrega su definición (Esquema General §6.1-ii y §6.1-v);
  esta propuesta debe contrastarse con ella y corregirse donde difiera.
- **Issues:** #62 (EDG-04), #63 (INS-03) y #64 (MET-01).
- **Alcance:** solo instancias reales (`is_synthetic = false`). Las reglas para el dataset
  sintético no cambian.

## Por qué hacía falta decidir algo ahora

Los primeros grafos reales (D1 HoloFood; ver el
[reporte de validación](real-graph-validation-report.md)) eran estructuralmente correctos,
pero ninguno se podía entregar a un modelo. Lo impedían tres reglas escritas para el dataset
sintético:

- **EDG-04:** exigía `evidence_status = "synthetic"` en toda arista.
- **INS-03:** solo admitía escenarios `basal` o `intervention`.
- **MET-01:** exigía una semilla aleatoria entera.

Sin una regla para datos reales, no se puede avanzar a modelos (F4). La propuesta fija el
criterio mínimo y conservador que el Esquema General ya permite deducir, y deja explícito qué
debe confirmar Investigación.

## 1. Criterio de evidencia de aristas (EDG-04, #62)

### Qué dice el proyecto

El Esquema General (§2.2) ya fija tres principios:

- **Qué debe declarar una arista:** "fuente, método, nivel de evidencia y estado observado /
  anotado / inferido / hipotético".
- **Qué afirma cada relación:**
  - «taxón → función» expresa una capacidad anotada, no una actividad demostrada;
  - «función → metabolito» es una transformación candidata;
  - «metabolito → huésped» es una exposición o asociación contextual;
  - «aditivo → taxón / función» sigue siendo hipotética mientras no haya contraste
    experimental.
- **Qué está prohibido:** crear aristas «taxón produce metabolito» por mera coocurrencia, o
  unir individuos o estudios distintos como si fueran mediciones pareadas.

El esquema v1 (`nutrigraphdt.graph.schema`) marca cada relación como `approved_structure`,
`provisional` o `hypothetical`.

### Referencias externas

- **Biolink Model** separa el nivel de conocimiento de una afirmación (`knowledge_level`) del
  tipo de agente que la produjo (`agent_type`). Una *observation* es "un fenómeno que se
  observó"; una *knowledge_assertion* es una afirmación que un agente presenta como cierta; una
  *prediction* sale de razonamiento probabilístico. El agente puede ser, por ejemplo, un
  `manual_agent` o un `data_analysis_pipeline`.
- **Evidence and Conclusion Ontology (ECO)** distingue la evidencia experimental de la
  computacional (por ejemplo, la similitud de secuencia) y de la inferencia de un curador. Es
  la base de los códigos de evidencia de las anotaciones GO.

Los cuatro estados de DS-01 corresponden a esas categorías:

| DS-01 | Biolink `knowledge_level` | Ejemplo en el proyecto |
|---|---|---|
| `observed` | `observation` | AGCC medidos en el contenido cecal de un animal |
| `annotated` | `knowledge_assertion` (agente manual o base curada) | KEGG asigna una ruta a un taxón; una tabla de composición asigna sustratos a una dieta |
| `inferred` | `prediction` / `statistical_association` | Un modelo predice qué taxón consume un sustrato |
| `hypothetical` | (afirmación no respaldada) | Un aditivo modula un taxón, sin contraste experimental |

### Propuesta

Un estado de evidencia solo se admite en las relaciones cuya semántica lo permite:

| Estado | Relaciones | Severidad | Razón |
|---|---|---|---|
| `observed` | `measured_in`, `exhibits`; con `evidence_method = "measurement"` | — | Son las únicas relaciones que el Esquema describe como medición u observación del animal. |
| `annotated` | `provides`, `has_capacity` | — | Composición tabulada y capacidad anotada (§2.2). |
| `inferred` | `available_to`, `has_capacity`, `produces`, `provides` | ADVERTENCIA | Se acepta como estructura para el modelo, pero no es un hecho. |
| `hypothetical` | relaciones `hypothetical` del esquema v1 | ADVERTENCIA | El Esquema las mantiene como hipótesis. |
| `synthetic` | ninguna | ERROR | Una arista generada no puede presentarse como dato real. |

Cualquier otra combinación es `ERROR`. En particular:

- `taxon → produces → metabolite` no existe en el esquema, y `function → produces → metabolite`
  nunca puede ser `observed`: no se mide la transformación, solo el metabolito.
- `observed` exige un método de medición: no se acepta coocurrencia.

### Qué debe confirmar Investigación

1. Si `exhibits` puede ser `observed` cuando el fenotipo se mide a nivel de corral y no de
   animal. Hoy D1 no exporta fenotipos de corral.
2. Qué bases o tablas cuentan como `annotated` (KEGG, MetaCyc, CAZy, Feedtables, FooDB) y con
   qué versión.
3. Si las aristas `inferred` deben llegar al modelo o quedar solo para exploración.
4. Si hace falta un vocabulario cerrado de `evidence_method`; hoy solo se fija
   `measurement`.

## 2. Escenario de una instancia real (INS-03, #63)

### Qué dice el proyecto

El Esquema General (§5) define un escenario como una de dos instancias comparables de **la
misma muestra**, basal e intervenida, de las que solo cambian las variables de intervención.
Ambas se predicen con el mismo modelo, y "se conservan por separado las observaciones reales y
los contrafactuales modelados". INS-05 a INS-07 comparan los escenarios que comparten
`sample_id`.

### Qué es D1

Según el resumen de diseño experimental del portal HoloFood, el ensayo de pollo es un diseño
de bloques completos aleatorizados, factorial 2 × 2 × 3 (línea, sexo y dieta). Se repitió en
tres ensayos estacionales (`CA`, `CB`, `CC`), con el tratamiento asignado al azar por corral y
sacrificios en los días 7, 21 y 35. Las dietas son:

- **Control:** dieta basal de trigo y soya.
- **Probiótico:** *Bacillus subtilis* DSM 32324 y DSM 32325, y *B. amyloliquefaciens*
  DSM 25840.
- **Fitobiótico:** extracto de uva blanca. La API lo nombra "Prebiotic", código `CE`.

Cada animal se observa una sola vez. Un animal Control es un **brazo control real**, no el
escenario basal contrafactual de un animal tratado: son individuos distintos.

### Alternativas

| Opción | Problema |
|---|---|
| Control → `basal`, tratados → `intervention` | Presenta individuos distintos como escenarios de la misma muestra, que es lo que el Esquema prohíbe (§3.1: no inventar emparejamientos). |
| `unknown` | Bloquea todas las instancias reales y no dice nada. |
| **`observed`** (propuesta) | Separa observaciones de contrafactuales, como pide §5. El brazo de tratamiento queda en `diet_treatment`. |

### Propuesta

- En una instancia real, `scenario_id = "observed"`; en una sintética, sigue siendo `basal` o
  `intervention`. El preprocesamiento asigna `observed` a toda fuente real.
- El tratamiento del animal va en `diet_treatment` (`Control`, `Probiotic`, `Prebiotic` en D1).
- INS-05 a INS-07 no cambian: solo emparejan instancias que comparten `sample_id`, y dos
  animales reales no lo comparten.
- Una simulación sobre un animal real producirá después sus escenarios `basal` e
  `intervention` como instancias **sintéticas** derivadas, con el animal observado como
  referencia.

### Qué debe confirmar Investigación

1. Si `observed` es el nombre adecuado o si conviene distinguir brazo control y brazo tratado.
2. Cómo se declara la relación entre una instancia observada y sus escenarios simulados (por
   ejemplo, un campo `derived_from`).
3. El criterio de partición entrenamiento/prueba. Como el tratamiento se asignó por corral, la
   unidad experimental es el corral (`pen_code`), y particionar por animal filtraría
   información entre conjuntos.

## 3. Semilla de datasets reales (MET-01, #64)

Un dataset real no se genera, se observa: no tiene semilla. Inventar una para cumplir MET-01
falsearía su procedencia. Desde `1.2.0`, `random_seed` puede ser `null` si
`is_synthetic = false`; un dataset sintético sigue exigiendo un entero. Este cambio no depende
de Investigación.

## Efecto en D1

Con las reglas `1.2.0`, los grafos de D1 quedan sin `ERROR` y son entregables. Siguen las
advertencias de atributos ausentes y de nodos aislados (ver el
[reporte de validación](real-graph-validation-report.md)).

## Fuentes

- Esquema General del proyecto, §2.2, §3.1, §5 y §6.1
  ([documento](../research/Esquema_General_del_proyecto_Microbioma_Digital.md)).
- Contrato DS-01 ([`synthetic-dataset-spec.md`](../synthetic-dataset/synthetic-dataset-spec.md)), contrato de arista.
- Biolink Model, [`KnowledgeLevelEnum`](https://biolink.github.io/biolink-model/KnowledgeLevelEnum/)
  y [`AgentTypeEnum`](https://biolink.github.io/biolink-model/AgentTypeEnum/).
- Giglio, M. et al. (2019). ECO, the Evidence & Conclusion Ontology: community standard for
  evidence information. *Nucleic Acids Research*, 47(D1), D1186–D1194.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6323956
- HoloFood Data Portal, [*HoloFood Chicken Experimental Design*](https://www.holofooddata.org/analysis-summary/holofood-chicken-experimental-design).
