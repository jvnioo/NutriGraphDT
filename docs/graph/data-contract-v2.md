# Contrato de datos v2 (REMIX): objetivo composicional, covariables y unidades

- **Estado:** **aprobado** por el sublíder de Investigación (Vicente Fuentes) el 25-10-2026,
  sobre el commit que incorpora los cambios pedidos en su respuesta. La implementación corre
  por los Issues de la sección 8; hasta que entren, el código sigue el contrato v1 (DS-01 y el
  [esquema v1](graph-schema-v1.md)).
- **Issue:** #136 (Actividad 31). Responsables según la Tabla 7 de la respuesta: Vicente
  Fuentes (Investigación) y Julio Provoste (Desarrollo).
- **Origen:** [respuesta de Investigación a la solicitud de revisión v1.1](<../research/Respuesta de Investigación a la Solicitud de revisión v1.1.md>)
  (16-10-2026): D-03 (variable objetivo), S-07 (diccionario de datos), V-02 (instancias
  derivadas), V-06 (unidades), D-04 y S-04 (taxonomía) y la Tabla 6; y la
  [respuesta de Investigación a la respuesta de Desarrollo](<../research/Respuesta de Investigación a la Respuesta de Desarrollo.md>)
  (25-10-2026), que responde las cinco preguntas de la sección 9 y fija los cambios
  previos a la aprobación (R-01 a R-09).
- **Alcance:** D1 HoloFood en F4. Las reglas para el dataset sintético no cambian, salvo que
  una sección lo diga.

Cada sección indica qué cambia frente a v1, la propuesta y su impacto. Las respuestas de
Investigación a las preguntas de este borrador están al final (sección 9).

## 1. Variable objetivo: composición de los AGCC y total aparte (D-03)

**v1.** El objetivo es la concentración de acetato, propionato y butirato en mmol/kg:
`y` de los nodos `metabolite` y `y_graph = [acetato, propionato, butirato]` por grafo.

**v2.** El objetivo principal es la **composición** de los tres AGCC principales. El total es
una salida secundaria, con pérdida y métricas propias.

| Magnitud | Definición | Unidad |
|---|---|---|
| Total | `T = acetato + propionato + n-butirato`, calculado por Desarrollo con los tres valores medidos. No se usa el «AGCC totales» del portal. | mmol/kg de digesta fresca |
| Fracción molar | `p_i = c_i / T`, para `i` en acetato, propionato y n-butirato. | adimensional; se informa en % |
| Log-razones (salida del modelo) | `z_1 = ln(propionato / acetato)`, `z_2 = ln(n-butirato / acetato)`. Equivale a una salida softmax de tres componentes. | adimensional |
| Total (salida del modelo) | `ln T` | ln(mmol/kg) |
| Cantidad reconstruida | `c_i = T · p_i`, para comparar con A45-2 y con estudios que informan cantidades. | mmol/kg de digesta fresca |

- **Una sola fuente de verdad.** El grafo sigue guardando las concentraciones medidas
  (`y` de `metabolite` y las salidas DS-01, en mmol/kg). La composición, las log-razones y
  `ln T` se derivan con una transformación versionada del módulo de modelos, que usan por igual
  la GNN y los baselines. Así no se guardan dos versiones del mismo dato que puedan divergir.
- **Ceros.** Una log-razón no admite ceros. Un animal con algún AGCC objetivo igual a cero no
  tiene objetivo composicional: queda con la máscara en `False`, como un valor ausente. No se
  agrega un pseudoconteo: Investigación confirmó la exclusión el 25-10-2026 (R-01, pregunta 1).
  Si aparecen ceros al incorporar datos nuevos, la pregunta se reabre con el límite de
  detección del ensayo (S-02). En la cohorte de D1 no hay ceros; el único caso conocido,
  SAMEA112904762, no tiene metagenoma.
- **Lactatos y AGCC menores** (D- y L-lactato, i-butirato, n- e i-valerato): no son objetivo
  y se informan aparte. No entran a `x` en ningún escenario (R-01, pregunta 2): son mediciones
  de la misma muestra y el mismo momento que el objetivo, y como entrada le entregarían al
  modelo información que no existe en el uso real. Pueden existir como nodos del grafo sin su
  valor medido: el lactato, por ejemplo, lo producen unas bacterias y lo consumen otras para
  formar butirato y propionato.
- **Métricas** (D-03):
  - R² y MAE de cada fracción, en puntos porcentuales, y su promedio macro;
  - R² y MAE de `ln T`;
  - R² y MAE en mmol/kg reconstruidos;
  - todas globales y por día de muestreo (D-07), con media y dispersión entre folds y
    semillas.

**Impacto:**

- `models/gnn/target.py` (`y_graph`): agregar la transformación y las máscaras derivadas;
- `models/metrics.py`: métricas composicionales;
- `models/tabular.py`: objetivos de los baselines;
- NOD-08 (Tabla 6, N° 5): hoy cuenta `metabolite.concentration` como ausente en 61 instancias
  porque el valor vive en `y`. En v2, la concentración de un metabolito objetivo se declara como
  salida y no como atributo de nodo, y no se cuenta como ausencia.

## 2. Cohorte supervisada

El conjunto supervisado es la cohorte de `configs/cohorts/d1_holofood.json` (#138): 56 animales
con metagenoma y los tres AGCC, sin los 8 perfiles repetidos y con al menos 1000 lecturas SSU.
Los demás grafos **no se entregan a ningún modelo en F4**: quedan construidos y validados, y la
decisión se reabre solo si se define una tarea sin objetivo (R-02, que corrige la Tabla 6, N° 7).
El contrato remite a esa configuración y no repite la lista.

## 3. Covariables del huésped (S-07)

**v1.** `host.covariates` es un objeto libre. En D1 solo trae `body_weight_g`.

**v2.** `host.covariates` declara, con nombre, tipo y vocabulario fijos:

| Covariable | Tipo | Vocabulario o unidad en D1 | Uso en F4 |
|---|---|---|---|
| `trial_code` | `str` | `CA`, `CB`, `CC` | Entrada del modelo. El ensayo aporta 13 puntos de R² a ln(propionato/acetato) sin que cambie la dieta (sección 6 de la respuesta), así que en F4 entra como covariable, no como nodo. |
| `pen_code` | `str` | código del corral | **No es entrada.** Solo agrupa la partición y la validación cruzada (D-07). Como entrada, filtraría la identidad del corral. |
| `sampling_day` | `int` | 7, 21, 35 (día de muestreo del ensayo) | Entrada, y estrato de las métricas por día. La dieta está confundida con el día (día 35: 26 Control, 3 Probiótico, 2 Fitobiótico). |
| `sex` | `str` | `female`, `male` | Entrada. |
| `breed` | `str` | `Ross`, `Cobb` | Entrada. |
| `body_weight_g` | `number` | g | **Informado, no es entrada.** Depende en parte del tratamiento y crece junto al día; como entrada, el modelo podría aprender el efecto de la dieta a través del peso (R-01, pregunta 3). |

Un valor ausente se declara con `missing_mask`, como en v1.

`CC` tiene dos significados en D1: un ensayo (`CA`, `CB`, `CC` en `trial_code`) y el tratamiento
Control (`CC`, `CO`, `CE`). En los reportes, el código se califica siempre con el campo al que
pertenece (observación de Investigación, 25-10-2026).

**Implementación (#147).** `nutrigraphdt.data.covariates` declara la tabla; `MetadataLoader`
carga `pen_code`; `attach_sample_context` lleva las cinco covariables de contexto a
`host_covariates` de la instancia; el constructor las une a `body_weight_g` en
`host.covariates` y declara sus vocabularios en `metadata.json` para NOD-11; `x` del host y la
tabla de atributos usan solo las de entrada, en one-hot.

**Impacto:**

- `data/integration.py` y `graph/builder.py` (host);
- `models/tabular.py` (atributos de los baselines);
- codificación de categorías en `x` del host, que hoy no existe (§7 de `gnn-architecture.md`).

## 4. Unidades y matriz (V-06, S-07)

- **Notación canónica de máquina:** la de `data.schema.CANONICAL_UNITS`, en minúsculas y con
  guion bajo (`mmol_kg`, `g_kg`, `mg_kg`, `CFU_kg`). La etiqueta de presentación (`mmol/kg`,
  `g/kg`) solo se usa en reportes y figuras. Hoy conviven `g_kg` y `g/kg`: el diccionario
  sintético pasa a la notación canónica en la columna de máquina y conserva la etiqueta para
  lectura.
- **Base de la medición:** un atributo nuevo `basis` en los nodos `metabolite` y en las
  salidas, con el vocabulario `wet` o `dry`. En D1 es `wet`: las tablas del portal no traen
  materia seca. Una conversión entre bases exige la materia seca y queda fuera de F4.
- **`sample_matrix`:** vocabulario cerrado. En F4, el único valor admitido es
  `caecum_content`. `caecum_tissue` queda reservado y no se admite hasta que S-02 aclare la
  naturaleza de esas muestras (V-03).

**Implementación (#148).** `data.schema` declara `CANONICAL_UNITS` (con `MJ_kg` y `ug_mL`),
`UNIT_LABELS`/`unit_label` para la presentación, `MEASUREMENT_BASES` y `F4_SAMPLE_MATRICES`.
`attach_sample_context` declara en D1 `sample_matrix = caecum_content` (antes `cecal_content`) y
`basis = wet`; el constructor lleva `basis` al nodo `metabolite` y a la salida, y declara en
`metadata.json` los vocabularios de `sample_matrix` y `basis`, que NOD-11 evalúa (una muestra
`caecum_tissue` se informa). OUT-04 rechaza una `basis` fuera de `wet`/`dry`; una salida sin
`basis` (anterior a #148) sigue siendo válida. El sintético pasa a la notación de máquina en
todas sus unidades y declara `basis = wet` como convención; su `sample_matrix` (`cecal_content`)
no cambia, porque el vocabulario cerrado rige para D1 en F4.

**Impacto:**

- `data/schema.py` y `MetaboliteLoader` (`basis`);
- contratos Pydantic de `metabolite`;
- una regla de vocabulario para `sample_matrix` (hoy NOD-11 solo cubre los vocabularios
  sintéticos).

## 5. Estados y métodos de evidencia (V-01, S-07)

- **Estados:** los cinco de DS-01 (`synthetic`, `observed`, `annotated`, `inferred`,
  `hypothetical`).
- **Del esquema tabular:** `experimental` y `literature` de `data.schema` dejan de ser
  estados y pasan a ser métodos. `experimental` equivale a `observed` con
  `evidence_method = "measurement"`, y `literature` a `annotated` con
  `evidence_method = "literature_curation"`.
- **`evidence_method`:** el vocabulario cerrado de la Tabla 4 de la respuesta.
- **`evidence_source`:** la procedencia (`<base>@<versión>` o `doi:…`). Investigación confirmó
  (25-10-2026, pregunta 5) que ambos formatos son suficientes: el identificador de la ruta KEGG
  no va en este campo, sino en el identificador del nodo de función.

Las reglas de integridad `1.3.0` (#137) ya aplican el vocabulario y la procedencia en el
validador y el constructor, y #149 retiró `experimental` y `literature` de los estados
tabulares (esquema tabular `1.1.0`).

## 6. Taxonomía (D-04, S-04)

- **Rango de trabajo: género.** Los nombres se puentean de SILVA 132 a GTDB r207 con la tabla
  de equivalencias versionada de S-04. No se une HoloFood con el catálogo por nombre sin esa
  tabla.
- **`taxon_id` lleva el prefijo de rango.** Por ejemplo, `g__Lactobacillus`, o
  `p__Actinobacteria` frente a `c__Actinobacteria`. Las dos colisiones de nombre dejan de
  sumarse: son nodos distintos.
- **Lecturas sin género.** El 55 % de las lecturas no llega a género. Toda lectura que no alcanza
  género se agrega en un **nodo residual del rango más profundo que alcance** (por ejemplo,
  `f__Lachnospiraceae;g__` u `o__X;f__`), para que las abundancias relativas sigan sumando 1.
  Esos nodos no reciben aristas funcionales. Investigación confirmó la regla, generalizada, el
  25-10-2026 (R-01, pregunta 4) y declara como limitación que cerca del 55 % de la abundancia
  queda sin camino taxón → función → metabolito.
- **Enlace al catálogo.** Solo los taxones con enlace `1:1` reciben `has_capacity` anotada
  (reglas `1.3.0`).

**Impacto:**

- `AbundanceLoader` (prefijo de rango, sin sumar colisiones);
- un paso nuevo de agregación a género, que depende de la tabla de S-04.

## 7. Instancias derivadas (V-02)

- **Instancia real:** `scenario_id = "observed"`, como en v1.
- **Instancia simulada desde un animal real:** es sintética y declara:
  - `derived_from`: el `sample_id` (BioSample) del animal observado;
  - `intervention`: un objeto `{variable, value}` con cada variable que cambia y su nuevo
    valor.
- **Validación:** INS-06 e INS-07 comparan la instancia derivada con su origen y comprueban
  que solo cambian las variables declaradas.
- **Control de calidad del simulador:** el escenario `basal` simulado de un animal Control
  debería reproducir su propia observación.

**Implementación (#151).** `nutrigraphdt.data.derived` define el formato: `intervention` es una
lista de `{variable, value}`, con la ruta `<tipo de nodo>.<ruta del atributo>`
(`host.covariates.body_weight_g`; un componente de la dieta es `diet.composition.<component_id>`).
`InstanceRecord` y `NormalizedInstanceRecord` aceptan `derived_from` e `intervention` (se omiten
del JSON cuando no se declaran); una instancia tabular real con esos campos se rechaza al crearla.
Reglas de integridad `1.4.0`: INS-08 valida los campos (una instancia real con `derived_from` es
`ERROR`), e INS-05 a INS-07 comparan cada derivada con la observación de su origen y solo admiten
las variables declaradas; INS-06 informa además una derivada que no tiene el valor declarado.
**Decisión de Desarrollo:** una derivada reutiliza los identificadores de su origen (sin prefijo
`synthetic:`; NOD-04 no se le aplica y NOD-12 la evalúa como real), para poder compararla nodo
por nodo.

**Impacto:**

- `NormalizedInstanceRecord`, `InstanceRecord` y los contratos de instancia;
- INS-06 e INS-07 pasan a comparar por `derived_from` además de por `sample_id`.

## 8. Implementación derivada

Cada sección con impacto en el código tiene su Issue, bloqueado hasta la aprobación escrita de
este contrato:

| Sección | Issue | Trabajo |
|---|---|---|
| 1 | #146 | Transformación del objetivo composicional y métricas de D-03 (también bloquea #140 y #142). |
| 3 | #147 | Covariables del huésped en registros, grafo y tabla de atributos. |
| 4 | #148 | `basis`, vocabulario de `sample_matrix` y notación canónica de unidades. |
| 5 | #149 | Retirar `experimental` y `literature` de los estados tabulares (después de #137). |
| 6 | #150 | `taxon_id` con prefijo de rango, agregación a género con la tabla S-04 y nodos residuales del rango más profundo. |
| 7 | #151 | `derived_from` e `intervention` en las instancias derivadas. |

## 9. Respuestas de Investigación (25-10-2026)

Investigación respondió las cinco preguntas de este borrador en su
[respuesta a la respuesta de Desarrollo](<../research/Respuesta de Investigación a la Respuesta de Desarrollo.md>)
(R-01), y este contrato ya incorpora los tres cambios previos a la firma que pidió (secciones
2, 3 y 6):

1. **Ceros en la composición.** Se confirma la propuesta: un animal con algún AGCC objetivo
   igual a cero queda sin objetivo composicional (máscara en `False`), sin pseudoconteo. Si
   aparecen ceros al incorporar datos nuevos, la pregunta se reabre con el límite de detección
   del ensayo (S-02).
2. **Metabolitos que no son objetivo.** Lactatos y AGCC menores no entran a `x` en ningún
   escenario; pueden existir como nodos del grafo sin su valor medido.
3. **Peso corporal.** `body_weight_g` no es entrada: depende en parte del tratamiento y está
   ligado al día. `sampling_day` se mantiene como entrada obligatoria.
4. **Nodos residuales.** Se confirma, generalizada: toda lectura que no alcanza género se
   agrega en un residual del rango más profundo que alcance, sin aristas funcionales.
5. **Formato de `evidence_source`.** `<base>@<versión>` y `doi:10.…` son suficientes; el ID de
   la ruta KEGG corresponde al identificador del nodo de función.

## Aprobación

| Rol | Nombre | Decisión | Fecha |
|---|---|---|---|
| Sublíder de Investigación | Vicente Fuentes Rodríguez | aprueba | 25-10-2026 |
| Sublíder de Desarrollo | Julio Provoste Palacios | aprueba | 25-10-2026 |

Investigación aprobó el contrato sobre el PR que incorpora los cambios pedidos en su respuesta
del 25-10-2026 (Anexo A.1 de esa respuesta), con dos observaciones no bloqueantes ya aplicadas y
una tercera (formato de la copia versionada de la respuesta) que se resuelve con el markdown
limpio que enviará Investigación. Con la aprobación, el [esquema v1](graph-schema-v1.md) y el
[diccionario del grafo](graph-data-dictionary.md) enlazan este documento como su versión
siguiente, y los Issues de la sección 8 pasan a `Ready`.
