# **Respuesta de Investigación a la Respuesta de Desarrollo v1.0**

Oct 25, 2026

**PIA-2 · Microbioma Digital — Gemelo Digital Nutricional basado en GNN y PINNs.** Proyecto NutriGraphDT · De: Célula de Investigación · Para: Célula de Desarrollo (sublíder Julio Provoste Palacios) · Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II. Responde a la *Respuesta de Desarrollo a la respuesta de Investigación*, versión 1.0, del 18-10-2026.

**Respuesta corta.** Investigación responde las nueve peticiones (R-01 a R-09). Aprueba el contrato de datos v2 con tres cambios previos: el peso corporal deja de ser entrada, los grafos sin AGCC no se entregan a ningún modelo en F4 y la regla de nodos residuales se generaliza. Confirma la cohorte de 56 animales y acepta evaluar el perfilado de los 107 animales adicionales con un piloto fuera de la ruta crítica de F4. Cada decisión se tomó con un mismo criterio: desbloquear F4 cuanto antes sin crear trabajo que no tenga beneficio claro dentro del semestre.

## **1\. Propósito, alcance y fuentes revisadas**

Este documento responde formalmente las peticiones R-01 a R-09 y deja registro de cómo se llegó a cada decisión. Para cada punto indica el antecedente, la evidencia revisada, las opciones consideradas, la decisión y su justificación. Las respuestas que tienen un lugar en GitHub se publican también allí (Anexo A), porque Desarrollo pidió registro durable en cada PR o Issue.

**Tabla 1\.** Fuentes revisadas

| N° | Fuente | Versión o fecha | Uso en esta respuesta |
| :---- | :---- | :---- | :---- |
| 1 | Respuesta de Desarrollo a la respuesta de Investigación | v1.0, 18-10-2026 | Hallazgos H-01 a H-07 y peticiones R-01 a R-09 |
| 2 | docs/graph/data-contract-v2.md (PR \#152) | Commit 157e706 | Las cinco preguntas de la sección 9 y las secciones 1 a 8 |
| 3 | docs/data-sources/holofood-source.md | Rama main, consultada el 25-10-2026 | Diseño experimental de D1, decisiones y cautelas, conteos de H-04 |
| 4 | reports/cohort/d1\_holofood.md | Versión 1.0.0, descarga del 15-10-2026 | Pasos de la cohorte, exclusiones y umbrales de 1000 y 5000 lecturas |
| 5 | Respuesta de Investigación a la Solicitud de revisión v1.1 | v1.0, 16-10-2026 | Decisiones previas: D-03, D-07, D-08, S-05, Tabla 6 y Tabla 7 |
| 6 | Cronograma del área de Investigación (GPI-302) | Última actualización disponible | Fecha de término del área (16-10-2026) y estado de avance registrado |
| 7 | Imputación de horas del equipo (hoja «Parámetros») | Vigente | Capacidad semanal del equipo para asignar compromisos nuevos |

El alcance es D1 HoloFood en F4. No se revisan el dataset sintético ni las fases posteriores, salvo cuando una decisión las afecta.

## **2\. Método de evaluación y criterio de viabilidad**

Todas las decisiones se evaluaron con un único criterio: la viabilidad del proyecto dentro del semestre 2026-II. La evaluación siguió cinco pasos.

1. **Lectura y clasificación.** Se leyó la respuesta de Desarrollo completa y se separó lo que bloquea F4 (solo R-01) de lo que puede avanzar en paralelo (R-02 a R-09).  
2. **Contraste con nuestras propias decisiones.** Cada hallazgo y petición se comparó con la respuesta de Investigación del 16-10-2026, buscando contradicciones internas antes que errores ajenos.  
3. **Verificación en el repositorio.** Se leyeron el contrato v2, la documentación de D1 y el reporte de cohorte, para confirmar cifras y despejar dudas con evidencia y no con supuestos (sección 3).  
4. **Evaluación de opciones.** Para cada pregunta se identificaron las alternativas razonables y se compararon con los cuatro criterios de la Tabla 2\.  
5. **Decisión y registro.** Se eligió la opción que mejor cumple los criterios, se anotó su justificación y se preparó el texto para el PR o Issue correspondiente (Anexo A).

**Tabla 2\.** Criterios de viabilidad

| N° | Criterio | Pregunta que responde | Por qué importa ahora |
| :---- | :---- | :---- | :---- |
| C1 | Desbloquear F4 | ¿La decisión permite que Desarrollo avance sin esperar más? | R-01 lleva bloqueando F4 desde el 18-10-2026. |
| C2 | No crear trabajo sin beneficio claro | ¿El trabajo nuevo produce algo que se use este semestre? | El cronograma del área terminó el 16-10-2026 y la capacidad del equipo es de 92,5 horas semanales en total. |
| C3 | Nada incierto en la ruta crítica | ¿La decisión depende de algo cuyo resultado o duración se desconoce? | Una tarea incierta en la ruta crítica puede atrasar el cierre completo. |
| C4 | Declarar en vez de arreglar | ¿La limitación se puede informar con honestidad en lugar de corregirla ahora? | Una limitación declarada no resta validez; una oculta, sí. |

Cuando dos criterios chocaban, se priorizó C1 sobre los demás, siempre que la decisión no comprometiera la validez científica de la evaluación de F4.

## **3\. Verificaciones propias sobre el repositorio**

Cuatro dudas se resolvieron leyendo el repositorio antes de decidir; una de ellas (VR-1) cambió la evaluación inicial. Se numeran VR para no confundirlas con los puntos V-01 a V-06 de la solicitud de Desarrollo.

**Tabla 3\.** Verificaciones realizadas

| N° | Duda | Dónde se verificó | Resultado | Efecto en la respuesta |
| :---- | :---- | :---- | :---- | :---- |
| VR-1 | ¿La raza (breed) duplica al ensayo (trial\_code)? | holofood-source.md, «Decisiones y cautelas» | No. El ensayo es de bloques completos aleatorizados, factorial línea × sexo × dieta. La raza es un factor del diseño. | Sin cambios al contrato: breed puede quedarse como entrada. |
| VR-2 | ¿El código CC tiene dos significados? | holofood-source.md, «Diseño experimental» | Sí. CC es un ensayo (CA, CB, CC) y también el tratamiento Control (CC, CO, CE). | Observación no bloqueante en R-01. |
| VR-3 | ¿Hay ceros en los AGCC de la cohorte? | Contrato v2, sección 1 (dato informado por Desarrollo) | No. El único caso conocido, SAMEA112904762, no tiene metagenoma. | La pregunta 1 de R-01 no afecta hoy a ningún animal. |
| VR-4 | ¿El contrato v2 sigue sin fusionar? | Rama main y commit 157e706 | El archivo está en main con contenido idéntico al commit, pero su encabezado dice «borrador, pendiente de aprobación». | Se pide a Desarrollo confirmar el estado del PR \#152. |

Las cifras de cohorte usadas en este documento (59, 58, 56 y 50 animales) coinciden con el reporte d1\_holofood.md v1.0.0, generado sobre la descarga del 15-10-2026.

## **4\. Evaluación de los hallazgos H-01 a H-07**

Investigación acepta los siete hallazgos. Dos de ellos (H-01 y H-05) exponen contradicciones de nuestra propia respuesta del 16-10-2026, que se corrigen aquí.

**Tabla 4\.** Evaluación de los hallazgos

| Hallazgo | Qué dice Desarrollo | Evaluación de Investigación | Consecuencia |
| :---- | :---- | :---- | :---- |
| H-01 | La cohorte baja de 58 a 56 al aplicar el umbral de 1000 lecturas. | **Error nuestro.** Fijamos 58 animales (D-03) y propusimos el umbral (S-05), pero no aplicamos ambos a la vez. | Se confirma la cohorte de 56 (R-04). |
| H-02 | Solo SAMEA112905124 afecta a la cohorte; no hubo fuga de objetivo en la partición 2.0.0. | Correcto: el reporte de cohorte confirma que es el único de los ocho con metagenoma. | Sin acción. |
| H-03 | Las matrices de contenido y «tissue» son de animales distintos. | Correcto. Comparar matrices no permite detectar un error de rótulo. | V-03 sigue dependiendo de S-02 (método analítico del ensayo). |
| H-04 | 107 animales con AGCC tienen lecturas crudas sin perfilar. | Es la mejor oportunidad del proyecto, pero su costo y duración son inciertos. | Piloto fuera de la ruta crítica (R-03). |
| H-05 | D-08 deja 124 de 185 grafos fuera de toda entrega a un modelo. | **Contradicción nuestra.** D-08 y la Tabla 6, N° 7 no pueden cumplirse a la vez. | Se resuelve en R-02. |
| H-06 | La GNN supera a ridge (RMSE 8,75 frente a 9,01), pero el criterio es provisional. | De acuerdo. La diferencia es pequeña y se comparó solo con la variación entre semillas. | No se citará como resultado en el artículo (actividad 146\) hasta la reevaluación de \#142. |
| H-07 | La GNN predice el acetato casi constante (R² de 0,05 a 0,07). | Coherente con D-03: el día y el ensayo explican buena parte de la composición. | Refuerza agregar las covariables del contrato v2 (\#147). |

## **5\. R-01: contrato de datos v2**

Investigación aprueba el contrato v2 con tres cambios previos a la firma. La revisión se registra en el PR \#152 como *Request changes*; la aprobación formal se emite sobre el commit que incorpore los cambios.

### **5.1 Pregunta 1: ceros en la composición**

**Antecedente.** Una log-razón no admite ceros. El borrador propone excluir al animal del objetivo composicional, sin pseudoconteo.

| Opción | C1 | C2 | C3 | Evaluación |
| :---- | :---- | :---- | :---- | :---- |
| **A. Excluir al animal (borrador)** | Sí | Sin trabajo nuevo | Sin incertidumbre | Hoy no afecta a ningún animal (VR-3). |
| B. Pseudoconteo fijado por Investigación | Sí | Requiere fijar un valor | Depende del límite de detección, desconocido hasta S-02 | Un valor elegido sin ese dato sería arbitrario. |
| C. Pérdida que no use logaritmos | No | Reescribe la salida del modelo (sección 1 del contrato) | Cambio de diseño | Desproporcionado para un caso que no existe. |

**Decisión: opción A.** Un cero medido casi seguro significa «bajo el límite de detección», no ausencia real. Si aparecen ceros al incorporar datos nuevos (R-03), excluirlos podría sesgar la muestra hacia animales con los tres AGCC sobre el límite de detección; en ese caso se reabre la pregunta con el límite de detección de S-02.

### **5.2 Pregunta 2: metabolitos que no son objetivo**

**Antecedente.** HoloFood mide también D- y L-lactato, i-butirato y n- e i-valerato. El borrador los deja fuera de x en F4 y pregunta si pueden entrar en algún escenario.

**Decisión: nunca como entrada.** Son mediciones de la misma muestra y el mismo momento que el objetivo. Como entrada, le entregarían al modelo información que no existe en el uso real, cuando se evalúa una dieta en un animal aún no medido, y la evaluación de F4 perdería validez. Pueden existir como nodos del grafo sin su valor medido. Esto tiene sentido biológico en el caso del lactato, que unas bacterias producen y otras consumen para formar butirato y propionato.

### **5.3 Pregunta 3: peso corporal**

**Antecedente.** La sección 3 del borrador declara como entradas tanto body\_weight\_g como sampling\_day.

| Opción | Evaluación |
| :---- | :---- |
| A. Mantener ambas entradas (borrador) | El peso depende en parte del tratamiento, porque los aditivos buscan mejorar el crecimiento. Como entrada, el modelo puede aprender el efecto de la dieta a través del peso. Además, peso y día crecen juntos y aportan información redundante. |
| **B. Solo el día como entrada** | El día lo fija el diseño del ensayo y D-03 ya lo declaró entrada obligatoria. Sacar el peso es menos trabajo, no más. |

**Decisión: opción B.** body\_weight\_g se conserva como atributo informado, sin ser entrada.

### **5.4 Pregunta 4: nodos residuales por familia**

**Antecedente.** El 55 % de las lecturas no llega a género. La propuesta de agregarlas en un nodo residual por familia es nuestra y estaba pendiente de confirmación por los autores de S-03 \+ D-04.

**Evaluación.** La propuesta conserva la abundancia y mantiene la suma en 1, pero no dice qué pasa con las lecturas que tampoco llegan a familia. Una sola regla general es más simple de implementar y validar que dos casos especiales.

**Decisión: se confirma, generalizada.** Toda lectura que no alcanza género se agrega en un nodo residual del rango más profundo que alcance, por ejemplo f\_\_Lachnospiraceae;g\_\_ u o\_\_X;f\_\_. Los residuales no reciben aristas funcionales, y se declara como limitación que cerca del 55 % de la abundancia queda sin camino taxón → función → metabolito (criterio C4). La confirmación la emite el sublíder; si el grupo autor plantea objeciones, se canalizan como cambio menor en el mismo PR.

### **5.5 Pregunta 5: formato de evidence\_source**

**Decisión: los formatos \<base\>@\<versión\> y doi:10.… son suficientes.** Desarrollo pregunta si hace falta el identificador de la ruta KEGG. No corresponde a este campo: evidence\_source registra de dónde salió el dato, por ejemplo mgnify-chicken-gut@v1.0.1, mientras que el ID de KEGG identifica qué función es. Ese identificador va en el nodo de función.

### **5.6 Cambios solicitados y observaciones**

**Tabla 5\.** Cambios al contrato v2

| N° | Sección | Cambio | Origen | Tipo |
| :---- | :---- | :---- | :---- | :---- |
| 1 | 2\. Cohorte supervisada | Los grafos sin AGCC no se entregan a ningún modelo en F4; quedan construidos y validados. | R-02 (§6.1 de este documento) | Previo a la firma |
| 2 | 3\. Covariables | body\_weight\_g pasa de «Entrada» a «Informado, no es entrada». | Pregunta 3 | Previo a la firma |
| 3 | 6\. Taxonomía | Reemplazar el residual por familia por la regla generalizada y retirar «pendiente de confirmación». | Pregunta 4 | Previo a la firma |
| 4 | 3 y reportes | Calificar siempre el campo cuando aparece CC (trial\_code o código de tratamiento). | VR-2 (§3 de este documento) | No bloqueante |
| 5 | Estado del PR | Confirmar si el PR \#152 está fusionado, dado que el archivo ya figura en main. | VR-4 (§3 de este documento) | No bloqueante |

**Por qué *Request changes* y no *Approve*.** Aprobar el texto tal como está implicaría responder R-02 en sentido contrario a lo decidido y dejar el peso como entrada. Los tres cambios son acotados, así que el costo es una sola vuelta de revisión (C1).

## **6\. Respuestas a R-02 a R-09**

R-02 y R-03 requirieron comparar opciones; las otras seis se resolvieron directamente con los criterios de la Tabla 2\.

### **6.1 R-02: alcance de D-08**

**Antecedente.** Nuestra respuesta del 16-10-2026 dijo dos cosas incompatibles: D-08 declara ERROR un grafo real sin metabolito, y la Tabla 6, N° 7 reserva esos grafos para tareas sin objetivo. Las reglas 1.3.0 de Desarrollo ya aplican D-08 en sentido estricto: solo 61 de 185 grafos son entregables.

| Opción | C1 | C2 | Evaluación |
| :---- | :---- | :---- | :---- |
| **A. Fuera de toda entrega a modelos en F4** | Sin cambios: ya implementado en el PR \#145 | Sin trabajo nuevo | No hay ninguna tarea sin objetivo planificada en F4. |
| B. Fuera solo del conjunto supervisado | Requiere partir la regla NOD-12 | Trabajo para un uso que nadie ejecutará este semestre | Construye capacidad sin destinatario. |

**Decisión: opción A.** Los 124 grafos quedan construidos y validados, de modo que si se define una tarea sin objetivo, la decisión se reabre sin perder trabajo. Se corrige la sección 2 del contrato v2 (Tabla 5, N° 1).

### **6.2 R-03: perfilar los 107 animales**

**Antecedente.** Perfilar las lecturas crudas de 107 animales llevaría la cohorte de 56 a un máximo de 163\. Los 107 nuevos están casi balanceados (35 / 35 / 37 por tratamiento), así que la cohorte pasaría de 34 / 15 / 7 a 69 / 50 / 44\. Hoy ese desbalance obliga a declarar exploratoria toda comparación entre dietas.

**Riesgos identificados.**

* **Mezcla de métodos.** Los 56 animales actuales tienen perfil del pipeline de MGnify (SSU, SILVA). Si los 107 se perfilan con Kraken2/Bracken, la cohorte quedaría medida con dos herramientas distintas. Es el mismo argumento que se usó en V-05 para no mezclar ensamblajes con lecturas.  
* **Costo real.** Que no tenga costo monetario no significa que no tenga costo: los FASTQ de metagenoma son pesados y su procesamiento consume horas de equipo y de personas.

| Opción | C1 | C2 | C3 | Evaluación |
| :---- | :---- | :---- | :---- | :---- |
| A. No perfilar | Sí | Sin trabajo | Sin incertidumbre | Renuncia a la mejora más grande disponible. |
| B. Perfilar los 107 ahora, dentro de F4 | No | Trabajo grande | Duración desconocida en la ruta crítica | Puede atrasar todo F4. |
| **C. Piloto fuera de la ruta crítica** | Sí | Trabajo acotado | Mide la incertidumbre antes de comprometerse | Conserva la oportunidad sin arriesgar F4. |

**Decisión: opción C.** F4 cierra con 56 animales. El piloto perfila unos 5 animales, incluyendo algunos de los 56 para comparar con su perfil actual, y registra horas y espacio en disco. Si se escala, se perfilan los 163 animales con el mismo método. Ese escenario probablemente también vuelve innecesaria la tabla SILVA → GTDB, porque el catálogo chicken-gut ya usa taxonomía GTDB. El piloto se asigna según la imputación de horas, sin importar la célula, conforme a la regla del profesor.

### **6.3 R-04 a R-09**

**Tabla 6\.** Respuestas directas

| ID | Decisión | Justificación |
| :---- | :---- | :---- |
| R-04 | Se confirma la cohorte de 56 animales y la tabla de folds sobre 56\. El umbral oficial es 1000 lecturas; el de 5000 queda como análisis de sensibilidad. | Con 5000, el Fitobiótico conserva solo 5 corrales, el límite exacto para k \= 5 (C3). |
| R-05 | Versión mínima de la tabla SILVA → GTDB: solo los géneros que cubren la mayor parte de la abundancia de la cohorte. Se acepta el prefijo de rango en taxon\_id. | Habilita aristas has\_capacity para lo que más pesa sin sobreinvertir antes del resultado del piloto de R-03 (C2). |
| R-06 | Se suben d03\_agcc.py, d07\_corrales.py y compare\_silva\_mgnify\_genera.py a docs/research/. | Costo casi nulo; permite que Desarrollo reproduzca la Tabla 5 de nuestra respuesta del 16-10-2026 y la tabla de folds. |
| R-07 | Se aceptan las bases y formatos de las reglas 1.3.0. literature\_curation vale para la dieta y para produces, siempre con DOI. Para has\_capacity rige la sección 6 del contrato v2: solo anotación desde el catálogo en taxones con enlace 1:1. | Admitir curación bibliográfica en has\_capacity contradiría la sección 6 del contrato y agregaría trabajo de curación (C2). La cobertura funcional crece por R-05 y, si se escala, por R-03. |
| R-08 | Fechas en la sección 7\. | El cronograma del área terminó el 16-10-2026 y debe actualizarse con estos compromisos. |
| R-09 | El aviso al portal se envía el 26-10-2026. Mientras no respondan, rige la lista de exclusiones actual. | R-09 depende de R-08: sin aviso no hay respuesta que informar. No bloquea F4. |

## **7\. Compromisos de Investigación y fechas**

Investigación asume once compromisos; los siete primeros vencen el 26 y el 27 de octubre, y los compromisos 1 a 4 y 6 destraban directamente a Desarrollo. Esta tabla responde R-08 y reemplaza los «Por definir» de la Tabla 7 de nuestra respuesta anterior.

**Tabla 7\.** Compromisos, responsables y fechas

| N° | Compromiso | Petición | Responsable | Fecha | Estado |
| :---- | :---- | :---- | :---- | :---- | :---- |
| 1 | Enviar el usuario de GitHub al sublíder de Desarrollo para obtener acceso al repositorio | Requisito de todas | Vicente Fuentes | Oct 26, 2026 | Hecho |
| 2 | Publicar la revisión del contrato v2 en el PR \#152 | R-01 | Vicente Fuentes | Oct 26, 2026 | Pendiente |
| 3 | Responder el alcance de D-08 y la política de procedencia en el PR \#145 | R-02, R-07 | Vicente Fuentes | Oct 26, 2026 | Pendiente |
| 4 | Confirmar la cohorte de 56 animales en el Issue \#138 | R-04 | Vicente Fuentes | Oct 26, 2026 | Pendiente |
| 5 | Enviar el aviso al portal HoloFood sobre los cuatro pares de perfiles repetidos | R-09 | Vicente Fuentes | Oct 26, 2026 | Pendiente |
| 6 | Subir los scripts de D-03, D-07 y S-03 \+ D-04 a docs/research/ | R-06 | Vicente Fuentes, con los archivos de cada autor | Oct 27, 2026 | Pendiente |
| 7 | Actualizar el cronograma del área con estos compromisos | R-08 | Vicente Fuentes | Oct 27, 2026 | Pendiente |
| 8 | Buscar la publicación del ensayo y el método analítico de los AGCC | S-01, S-02 | Por asignar según imputación | Oct 30, 2026 | Pendiente |
| 9 | Entregar la tabla SILVA → GTDB mínima | R-05, S-04 | Grupo de S-03 \+ D-04 | Oct 30, 2026 | Pendiente |
| 10 | Ejecutar el piloto de perfilado y decidir si se escala | R-03 | Por asignar según imputación, sin importar la célula | Nov 6, 2026 | Pendiente |
| 11 | Formalizar las ecuaciones bioquímicas | D-06 | Por asignar | Antes del inicio de F5 | Pendiente |

**Pregunta abierta:** la fecha de inicio de F5 está por confirmar; de ella depende la fecha del compromiso 11\.

## **8\. Riesgos y limitaciones declaradas**

Las decisiones de este documento dejan cuatro limitaciones conocidas y tres riesgos con respuesta prevista.

**Tabla 8\.** Limitaciones que se declaran en vez de corregirse en F4

| N° | Limitación | Origen | Dónde debe declararse |
| :---- | :---- | :---- | :---- |
| L1 | Toda comparación entre dietas es exploratoria: la cohorte es de 56 animales, con 34 / 15 / 7 por tratamiento. | H-01, R-04 | Resultados de F4 y artículo científico |
| L2 | Cerca del 55 % de la abundancia queda en nodos residuales sin aristas funcionales. | Pregunta 4 de R-01 | Contrato v2 y sección de métodos del artículo |
| L3 | La ventaja de la GNN sobre los baselines es provisional hasta la reevaluación con validación cruzada. | H-06 | Artículo científico (actividad 146\) |
| L4 | Las mediciones están en base húmeda; no hay conversión a base seca. | Contrato v2, sección 4 | Contrato v2 y métodos |

**Tabla 9\.** Riesgos y respuesta prevista

| N° | Riesgo | Actividad afectada | Respuesta prevista |
| :---- | :---- | :---- | :---- |
| K1 | La revisión del contrato v2 se demora y F4 sigue bloqueado. | \#140, \#142, \#146 a \#151 | Publicar la revisión el 26-10-2026 (Tabla 7, N° 2). Los tres cambios son acotados y requieren una sola vuelta. |
| K2 | El piloto de R-03 resulta más costoso de lo previsto. | Cohorte ampliada | El piloto está fuera de la ruta crítica: si no es viable, F4 y F5 siguen con 56 animales y L1 se mantiene. |
| K3 | Al incorporar datos nuevos aparecen ceros en los AGCC. | Objetivo composicional | Reabrir la pregunta 1 con el límite de detección obtenido en S-02 (Tabla 7, N° 8). |

## **Anexo A. Textos para GitHub**

Cada texto se publica en el lugar que indicó Desarrollo y queda como registro durable de la decisión; este documento solo los reúne.

### **A.1 PR \#152 — revisión *Request changes* (R-01)**

\*\*Revisión del contrato de datos v2 (commit 157e706) — Investigación\*\*

Investigación aprueba el contenido del contrato con tres cambios previos a la aprobación formal.

\*\*Respuestas a la sección 9\*\*

1\. \*\*Ceros.\*\* Se acepta la propuesta: un animal con algún AGCC objetivo igual a cero queda sin objetivo composicional (máscara en \`False\`), sin pseudoconteo. Se revisará si aparecen ceros al incorporar datos nuevos; un valor de reemplazo requiere el límite de detección del ensayo (S-02).  
2\. \*\*Metabolitos que no son objetivo.\*\* Lactatos y AGCC menores no entran a \`x\` en ningún escenario. Pueden existir como nodos sin su valor medido.  
3\. \*\*Peso corporal.\*\* \`body\_weight\_g\` no es entrada del modelo: depende en parte del tratamiento y está ligado al día. \`sampling\_day\` se mantiene como entrada obligatoria.  
4\. \*\*Nodos residuales.\*\* Se confirma, generalizado: toda lectura que no alcanza género se agrega en un residual del rango más profundo que alcance (p. ej., \`f\_\_Lachnospiraceae;g\_\_\`, \`o\_\_X;f\_\_\`). Sin aristas funcionales. Se declara como limitación que cerca del 55 % de la abundancia queda sin camino funcional.  
5\. \*\*\`evidence\_source\`.\*\* \`\<base\>@\<versión\>\` y \`doi:10.…\` son suficientes. El ID de la ruta KEGG corresponde al identificador del nodo de función.

\*\*Cambios solicitados\*\*

\- Sección 2: los grafos sin AGCC no se entregan a ningún modelo en F4 (responde R-02).  
\- Sección 3: \`body\_weight\_g\` pasa de «Entrada» a «Informado, no es entrada».  
\- Sección 6: regla de residual generalizada; retirar «pendiente de confirmación».

\*\*No bloqueante:\*\* \`CC\` designa un ensayo y el tratamiento Control; calificar siempre el campo en reportes. Confirmar el estado del PR, dado que el archivo ya figura en \`main\`.

Vicente Fuentes Rodríguez, sublíder del Área de Investigación

### **A.2 PR \#145 — comentario (R-02 y R-07)**

\*\*R-02.\*\* Los grafos reales sin metabolito quedan fuera de toda entrega a un modelo en F4, como ya aplican las reglas 1.3.0. Se mantienen construidos y validados; si se define una tarea sin objetivo, la decisión se reabre.

\*\*R-07.\*\* Se aceptan las bases admitidas y los formatos \`\<base\>@\<versión\>\` y \`doi:10.…\`. \`literature\_curation\` vale para la dieta y para \`produces\`, siempre con DOI en \`evidence\_source\`. Para \`has\_capacity\` rige la sección 6 del contrato v2: solo anotación desde el catálogo en taxones con enlace 1:1.

Vicente Fuentes Rodríguez, sublíder del Área de Investigación

### **A.3 Issue \#138 — comentario (R-04 y R-09)**

\*\*R-04.\*\* Investigación confirma la cohorte de 56 animales (umbral de 1000 lecturas SSU) y que la tabla de folds de D-07 se rehace sobre 56\. El umbral de 5000 queda solo como análisis de sensibilidad.

\*\*R-09.\*\* El aviso al portal sobre los cuatro pares de perfiles repetidos se envía el 26-10-2026. Informaremos aquí su respuesta; mientras tanto rige la lista de exclusiones actual.

### **A.4 Issue \#141 — comentario (R-03)**

\*\*R-03.\*\* Sí, como piloto fuera de la ruta crítica de F4, que cierra con 56 animales. El piloto perfila unos 5 animales, incluidos algunos de la cohorte para comparar con su perfil MGnify, y registra horas y disco. Decisión de escalar: 06-11-2026. Si se escala, se perfilan los 163 animales con el mismo método, para no mezclar herramientas (mismo criterio que V-05). Responsable: según la imputación de horas, sin importar la célula.

### **A.5 Issue \#150 — comentario (R-05)**

\*\*R-05.\*\* Se acepta el prefijo de rango en \`taxon\_id\`. Investigación entregará el 30-10-2026 una tabla SILVA 132 → GTDB r207 mínima, con fuente, versión y la lista de \`taxon\_id\` con enlace 1:1, limitada a los géneros que cubren la mayor parte de la abundancia de la cohorte. Su ampliación depende del resultado del piloto de R-03.

### **A.6 Issue \#140 — comentario (R-06)**

\*\*R-06.\*\* De acuerdo con versionar en \`docs/research/\` los scripts \`d03\_agcc.py\`, \`d07\_corrales.py\` y \`compare\_silva\_mgnify\_genera.py\`, con sus salidas. Se suben el 27-10-2026.

## **Emisión, control de versiones y referencias**

Yo, **Vicente Fuentes Rodríguez**, sublíder del Área de Investigación del proyecto Microbioma Digital, confirmo la emisión de este documento a la Célula de Desarrollo.

**Tabla 10\.** Datos de emisión

| Campo | Detalle |
| :---- | :---- |
| Documento | Respuesta de Investigación a la Respuesta de Desarrollo v1.0 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Fecha de emisión | 25-10-2026 |
| Versión | 1.0 |
| Estado | Emitido, a la espera de que Desarrollo aplique los cambios del contrato v2 |

**Tabla 11\.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
| :---- | :---- | :---- | :---- |
| 1.0 | 25-10-2026 | Respuesta a H-01 a H-07 y a las peticiones R-01 a R-09, con la trazabilidad de cada decisión. | Vicente Fuentes Rodríguez |

### **Referencias**

Área de Investigación · Microbioma Digital. (2026). *Respuesta de la Célula de Investigación a la Solicitud de revisión v1.1*, versión 1.0, 16-10-2026. Documento interno.

Célula de Desarrollo · NutriGraphDT. (2026). *Respuesta de Desarrollo a la respuesta de Investigación*, versión 1.0, 18-10-2026. Documento interno.

Célula de Desarrollo · NutriGraphDT. (2026). *Contrato de datos v2 (REMIX)*, docs/graph/data-contract-v2.md, commit 157e706. [Repositorio jvnioo/NutriGraphDT](https://github.com/jvnioo/NutriGraphDT).

Célula de Desarrollo · NutriGraphDT. (2026). *Fuente D1 HoloFood*, docs/data-sources/holofood-source.md, y *Cohorte supervisada de D1\_holofood*, reports/cohort/d1\_holofood.md, versión 1.0.0. [Repositorio jvnioo/NutriGraphDT](https://github.com/jvnioo/NutriGraphDT).

Aitchison, J. (1986). *The Statistical Analysis of Compositional Data*. Chapman & Hall.