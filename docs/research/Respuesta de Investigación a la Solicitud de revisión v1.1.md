# **Respuesta de la Célula de Investigación a la Solicitud de revisión v1.1** 

Oct 16, 2026 

**PIA-2 · Microbioma Digital — Gemelo Digital Nutricional basado en GNN y PINNs.** Proyecto NutriGraphDT · De: Célula de Investigación · Para: Célula de Desarrollo (sublíder Julio Provoste Palacios) · Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II · Profesor Eduardo Osorio Venegas. Responde a la _Solicitud de revisión a la Célula de Investigación_ , versión 1.1, del 07-10-2026. 

**Respuesta corta.** Investigación confirma las dos decisiones provisionales que bloqueaban F4 (V-01 y V-02), con tres correcciones al criterio de evidencia, y cierra los cuatro puntos Bloqueante restantes: la variable objetivo (D-03), la partición (D-07), la fuente de anotación funcional (S-03) y el criterio taxonómico (D-04/S-04). La variable objetivo cambia: el modelo predice la **composición** de acetato, propionato y butirato, con el total como salida aparte, sobre una cohorte de **58 animales** . Eso exige una versión 2 del contrato de datos. Quedan pendientes, sin bloquear F4, la publicación del ensayo (S-01, S-02), la naturaleza de las muestras «tissue» (V-03) y las ecuaciones bioquímicas (D-06). 

## **1. Propósito y alcance** 

Este documento da la respuesta formal de Investigación a los 21 puntos de la solicitud (V-01 a V-06, D-01 a D-08 y S-01 a S-07). Cada respuesta indica si Investigación **confirma** , **corrige** , **reemplaza** o deja **pendiente** la decisión, con su fundamento. La sección 2 usa la plantilla de la Tabla 9 de la solicitud. 

Las respuestas se apoyan en tres entregables de la célula, todos calculados sobre la descarga de D1 HoloFood del 12-10-2026 y el 16-10-2026, con los mismos SHA-256 del manifiesto del repositorio. La Tabla 1 los resume. 

**Tabla 1.** Entregables de Investigación que respaldan esta respuesta 

|Entregable|Pregunta que responde|Puntos que cierra|Autores|
|---|---|---|---|
|D-03 · ¿Predecir cantidad o<br>fracción del total?|Representación de los<br>AGCC como objetivo|D-03, V-06<br>(parcial),<br>conciliación de la<br>cohorte|Matias Hurtado,<br>Bianca Torres, Belén<br>Urrutia|
|D-07 · Validación cruzada<br>por corral|Partición y validación del<br>modelo|D-07, V-04<br>(parcial)|Benjamín Barrientos,<br>Felipe Cruz, Sebastián<br>Inzulza|
|S-03 + D-04 · Géneros SILVA<br>frente a MGnify chicken-gut<br>v1.0.1|Enlace taxonómico con el<br>catálogo de genomas|S-03, S-04, D-04|Célula de Investigación|



Los tres incluyen su código ( <mark>`d03_agcc.py` ,</mark> <mark>`d07_corrales.py` ,</mark> <mark>`compare_silva_mgnify_genera.py` )</mark> y sus salidas ( <mark>`tablas.md` ,</mark> <mark>`resumen.json` )</mark> , de modo que Desarrollo puede reproducir cada cifra. Donde no hay entregable, la decisión es del líder del área. 

## **2. Resumen de decisiones** 

De los 21 puntos, Investigación confirma 7, corrige 5, reemplaza 1 y deja 8 pendientes o parciales; **ninguno de los 8 Bloqueante queda abierto** . La Tabla 2 sigue la plantilla de la Tabla 9 de la solicitud. Las fechas «Por definir» se completan en la versión 1.1. 

**Tabla 2.** Respuesta de Investigación por punto 

|ID|Prioridad|Decisión|Síntesis|Fundamento|Fecha|
|---|---|---|---|---|---|
|V-01|Bloqueante|Corrige|Se confirma el criterio;<br>`produces` admite `annotated`<br>desde base curada,<br>`has_capacity` solo para<br>enlaces 1:1 y se cierra el<br>vocabulario de<br>`evidence_method`.|Esquema §2.2;<br>S-03 + D-04;<br>ECO|16-10-2026|
|V-02|Bloqueante|Confirma|`scenario_id = observed`;<br>brazo en `diet_treatment`;se<br>acepta `derived_from`.|Esquema §3.1<br>y §5|16-10-2026|
|V-03|Bloqueante|Confirma<br>(exclusión)|Las 224 muestras «tissue» no<br>se usan en F4; su naturaleza<br>queda pendiente de S-02.|Esquema §3|16-10-2026|
|V-04|Alta|Confirma|Marcadores de corral fuera de<br>F4; nunca como `exhibits` por<br>animal.|D-07; D-03<br>(ICC corral ×<br>día)|16-10-2026|
|V-05|Media|Confirma|Solo lecturas (`ERR`…); sin<br>ensamblajes en F4.|S-03 + D-04<br>(Kraken2/Brac<br>ken)|16-10-2026|
|V-06|Media|Corrige|Factor 1 correcto; la unidad<br>debe declarar base húmeda;<br>el total se calcula con los 3<br>AGCC principales.|D-03|16-10-2026|
|D-01|Alta|Confirma|Pollo, contenido cecal.|I2; D1<br>HoloFood|16-10-2026|
|D-02|Alta|Pendiente<br>(parcial)|Tratamientos aceptados según<br>el portal; falta la publicación y<br>la dieta basal.|Resumen de<br>diseño del<br>portal|Por definir|



|ID|Prioridad|Decisión|Síntesis|Fundamento|Fecha|
|---|---|---|---|---|---|
|D-03|Bloqueante|Reemplaza|Objetivo = composición de 3<br>AGCC (2 log-razones) + log T<br>aparte; cohorte de 58.|D-03|16-10-2026|
|D-04|Bloqueante|Corrige|Género como rango de<br>trabajo; taxonomía puente<br>SILVA 132→GTDB r207.|S-03 + D-04|16-10-2026|
|D-05|Bloqueante|Corrige|Igual que V-01.|V-01|16-10-2026|
|D-06|Media|Pendiente|Actividad 78 en curso; se<br>adelantan los principios.|D-03; Wolin<br>(1960)|Por definir|
|D-07|Bloqueante|Confirma<br>(con<br>método)|StratifiedGroupKFold por<br>corral y dieta, k = 5,≥10<br>semillas.|D-07|16-10-2026|
|D-08|Alta|Corrige|Obligatorios: dieta, taxón,<br>función, metabolito y<br>huésped.|Hallazgo 7.1<br>de la solicitud|16-10-2026|
|S-01|Alta|Pendiente|Investigación busca la<br>composición de la dieta basal.|—|Por definir|
|S-02|Alta|Pendiente|Publicación del ensayo aún no<br>identificada.|—|Por definir|
|S-03|Bloqueante|Confirma|Catálogo MGnify chicken-gut<br>v1.0.1 (KEGG y CAZy).|S-03 + D-04|16-10-2026|
|S-04|Alta|Parcial|Tabla de equivalencias<br>versionada; curación de casos<br>1:N pendiente; colisiones por<br>ID con rango.|S-03 + D-04|Por definir|
|S-05|Alta|Parcial|Umbral provisional de 1000<br>lecturas SSU, con análisis de<br>sensibilidad.|D-07;<br>`holofood-sou`<br>`rce.md`|16-10-2026|
|S-06|Media|Pendiente|Evaluar D4 MTBLS560 y el<br>aporte real de los `ERZ`….|—|Por definir|
|S-07|Media|Parcial|Observaciones al diccionario;<br>aprobación tras el contrato v2.|Sección 5|16-10-2026|



## **3. Validación de las decisiones provisionales (V-01 a V-06)** 

### **3.1. V-01 · Criterio de evidencia de las aristas — Corrige** 

Investigación confirma la Tabla 6 de la solicitud y la prohibición de crear aristas por coocurrencia (Esquema §2.2), con tres correcciones. Las reglas 1.2.0 (EDG-04) pueden mantenerse; solo cambian las celdas de la Tabla 3. 

**Tabla 3.** Correcciones al criterio de evidencia propuesto por Desarrollo 

|Relación|Propuesta de<br>Desarrollo|Decisión de Investigación|Razón|
|---|---|---|---|
|`function`→<br>`produces`→<br>`metabolite`|Solo `inferred`<br>(advertencia)|Además `annotated` cuando<br>la reacción viene de una base<br>curada (ruta o reacción<br>KEGG/MetaCyc con su<br>versión); nunca `observed`|La base afirma que la ruta<br>produce el metabolito; eso es<br>una afirmación de<br>conocimiento, no una<br>predicción, pero tampoco una<br>medición.|
|`taxon`→<br>`has_capacity`→<br>`function`|`annotated` sin<br>condición|`annotated` solo si el taxón se<br>enlaza al catálogo con<br>relación `1:1` en la tabla de<br>equivalencias (S-04); los<br>casos `1:N` y `sin par` no<br>generan arista hasta su<br>curación|El 33,6 % de las lecturas a<br>género cae en nombres SILVA<br>que corresponden a varios<br>géneros GTDB (S-03 + D-04).|
|`evidence_method`|Solo<br>`measurement`|Vocabulario cerrado (Tabla 4)|Sin vocabulario cerrado,<br>EDG-04 no puede verificar<br>que el método sea coherente<br>con el estado.|



**Tabla 4.** Vocabulario cerrado de <mark>`evidence_method` ,</mark> versión 1 

|`evidence_method`|Estado admitido|Uso en el proyecto|
|---|---|---|
|`measurement`|`observed`|AGCC medidos en el contenido cecal.|
|`database_annotation`|`annotated`|KEGG, CAZy o MetaCyc vía el catálogo MGnify;<br>exige fuente y versión.|
|`literature_curation`|`annotated`|Dato tomado por un curador desde una<br>publicación (por ejemplo, la composición de la<br>dieta, S-01); exige DOI.|
|`model_prediction`|`inferred`|Salida de un modelo, incluido el propio gemelo<br>digital.|



|`evidence_method`|Estado admitido|Uso en el proyecto|
|---|---|---|
|`statistical_association`|`inferred`|Asociación estimada en datos; nunca crea|
|||`taxon`→`metabolite`.|
|`expert_hypothesis`|`hypothetical`|Hipótesis de modulación por aditivos y<br>similares.|



Respuestas a las preguntas de la solicitud: 

1. **¿** **<mark>`produces`</mark> nunca puede ser observada?** Correcto. Se mide la concentración del metabolito, no la transformación que lo origina. 

2. **¿Qué bases cuentan como anotación?** Para <mark>`has_capacity` :</mark> KEGG y CAZy tal como las publica el catálogo MGnify chicken-gut v1.0.1 (S-03). Para <mark>`produces` :</mark> KEGG o MetaCyc. Para <mark>`provides` :</mark> Feedtables y FooDB. La versión exacta de cada base se toma del catálogo o del recurso y se guarda en la arista; Investigación la verifica al cerrar S-04. 

3. **¿Las aristas inferidas e hipotéticas llegan al modelo?** Las <mark>`inferred`</mark> sí, con el estado de evidencia como atributo de la arista, y con una ablación con y sin ellas en F4. Las <mark>`hypothetical`</mark> no entran a los grafos de entrenamiento de F4; se reservan para las instancias sintéticas de simulación. 

4. **¿** **<mark>`exhibits`</mark> es observada si el fenotipo se mide por corral?** No. Un promedio de corral no es un fenotipo del animal y no genera una arista <mark>`exhibits`</mark> por animal (ver V-04). 

5. **¿Hace falta un vocabulario cerrado?** Sí: la Tabla 4. 

### **3.2. V-02 · Escenario de un animal real — Confirma** 

Investigación confirma <mark>`scenario_id = "observed"`</mark> para toda instancia real. Un animal Control es un brazo control real, no el contrafactual de otro animal, y emparejarlos violaría el Esquema §3.1. 

1. **¿Distinguir brazo control y tratado?** No en <mark>`scenario_id` .</mark> El brazo ya vive en <mark>`diet_treatment` ;</mark> duplicarlo crea dos fuentes de verdad que pueden divergir. 

2. **¿Cómo registrar la derivación?** Se acepta <mark>`derived_from`</mark> con el <mark>`sample_id`</mark> (BioSample) del animal observado. Se pide además que cada instancia derivada declare qué variable cambió y a qué valor, para que INS-06 e INS-07 puedan comprobar que solo cambia la intervención. 

Una consecuencia útil: el escenario <mark>`basal`</mark> simulado de un animal Control debería reproducir su propia observación. Esa diferencia sirve como control de calidad del simulador. 

### **3.3. V-03 · Matriz de los AGCC — Confirma la exclusión** 

Se confirma usar solo contenido cecal y no usar las 224 muestras «caecum tissue» en F4, ni como objetivo ni como entrada. Investigación no puede decidir aún si son contenido mal rotulado o tejido real: hace falta el método analítico del ensayo (S-02). Mientras tanto, Investigación pide a Desarrollo un conteo de cuántos animales tienen ambas matrices y si sus valores coinciden; valores idénticos apuntarían a un error de rótulo del portal. 

### **3.4. V-04 · Marcadores de corral — Confirma** 

Los promedios de corral (conversión alimenticia, ganancia diaria, peso medio) **no** se usan en F4. Si se incorporan después, será como atributo del corral en análisis por corral, nunca como fenotipo del animal. <mark>`pen_code`</mark> se conserva para la partición, como fija D-07. 

D-03 refuerza esta decisión: el total de AGCC es lo que más comparten los animales del mismo corral sacrificados el mismo día (ICC corral × día = 0,53). Cualquier variable de corral está confundida con la ocasión de muestreo. 

### **3.5. V-05 · Datos de secuenciación — Confirma** 

Se confirma usar solo perfiles de lecturas ( <mark>`ERR` …)</mark> , sumar las resecuenciaciones y tratar los conteos como composicionales. No se incorporan ensamblajes ( <mark>`ERZ` …)</mark> en F4: sus conteos no son comparables y mezclarlos rompería la unidad de las abundancias. 

Antes de reabrir el punto, Investigación pide saber cuántos animales **con AGCC de contenido** agregarían los <mark>`ERZ` …,</mark> porque el cuello de botella es el emparejamiento con AGCC, no el metagenoma. A mediano plazo, S-03 + D-04 recomienda perfilar las lecturas contra el catálogo con Kraken2/Bracken, lo que reemplazaría la clasificación SSU actual. 

### **3.6. V-06 · Unidades y metabolitos — Corrige** 

- **Factor 1 µmol/g = 1 mmol/kg:** correcto. Se corrige la declaración: la unidad debe indicar **base húmeda (digesta fresca)** . Las tablas descargadas no traen materia seca, y sin ese dato las cifras no son comparables con estudios que informan base seca. 

- **D- y L-lactato separados:** correcto. No forman parte del denominador del objetivo (D-03) y se informan aparte. 

- **Totales y razones del portal no se usan:** correcto. El total del modelo es T = acetato + propionato + n-butirato, calculado por Desarrollo, no el «AGCC totales» del portal. Los AGCC menores (i-butirato, n- e i-valerato) se informan aparte: son el 2,1 % del total volátil en la mediana. 

## **4. Decisiones del Esquema General §6.1 (D-01 a D-08)** 

### **4.1. D-01 · Especie y segmento — Confirma** 

Pollo de engorde, **contenido cecal** , para F4. D1 HoloFood es la única fuente verificada que reúne microbioma, AGCC y dieta del mismo animal bajo tratamientos controlados. El cerdo (MetaboLights, MTBLS13996) queda como extensión posterior, no como parte de F4. 

### **4.2. D-02 · Intervención y dosis — Pendiente (parcial)** 

Investigación acepta, de forma provisional, los tratamientos del resumen de diseño del portal: Control ( `CC` ), Probiótico ( `CO` , _B. subtilis_ DSM 32324 y DSM 32325 y _B. amyloliquefaciens_ DSM 25840, 0,75 g/kg de alimento) y Fitobiótico ( `CE` , extracto de uva blanca, 0,75 g/kg). La confirmación formal depende de la publicación del ensayo (S-02) y la dieta basal, de S-01. 

Se pide que el grafo rotule `CE` como **Fitobiótico (extracto de uva blanca)** y conserve «Prebiotic» solo como nombre de origen de la API, para no propagar un rótulo incorrecto a los resultados. 

### **4.3. D-03 · Variable objetivo, matriz y unidad — Reemplaza** 

El objetivo principal es la **composición** de los tres AGCC principales, no su concentración. El fundamento es el entregable D-03; la Tabla 5 resume la evidencia. 

- **Composición:** fracción molar p = c / (acetato + propionato + n-butirato), predicha como dos log-razones respecto del acetato, log(propionato/acetato) y log(butirato/acetato), o con una salida softmax. 

- **Total:** log T como salida secundaria, con pérdida y métricas propias. La cantidad en mmol/kg se reconstruye como T × p para el contrato y para comparar con A45-2. 

- **Matriz y unidad:** contenido cecal; fracción en %, total en mmol/kg de digesta fresca. 

- **Lactatos y AGCC menores:** no son objetivo; se informan aparte. 

- **Cohorte: 58 animales.** Se excluye SAMEA112905124 (corral CC03), cuyo perfil repite el de otro animal, hasta que el portal lo aclare. 

- **Métricas:** R² y MAE de cada fracción, en puntos porcentuales, y su promedio macro; R² y MAE de log T; métricas en mmol/kg reconstruidas. 

**Tabla 5.** R² fuera de fold de un modelo ridge sobre los factores del diseño (StratifiedGroupKFold por corral, k = 5, 10 semillas) 

|Objetivo|Todos (227)|Cohorte (59)|
|---|---|---|
|Acetato, cantidad (µmol/g)|−0,01|−0,34|
|Acetato, fracción (%)|0,34|0,32|
|Propionato, cantidad (µmol/g)|0,53|0,54|
|Propionato, fracción (%)|0,46|0,40|
|Butirato, cantidad (µmol/g)|0,13|0,14|
|Butirato, fracción (%)|0,00|0,10|
|Total, log T|0,06|−0,14|
|Promedio macro, cantidad|0,22|0,11|
|Promedio macro, fracción|0,27|0,27|



Fuente: D-03, Tabla 4. El 95 % de la varianza del log del acetato es la varianza del total, y el total no se predice fuera del corral. El butirato es la excepción: su cantidad se predice mejor que su fracción porque crece con el total a lo largo de la edad. 

### **4.4. D-04 · Ontología de taxones y rutas — Corrige** 

El rango de trabajo para F4 es el **género** , con nombres puenteados de SILVA 132 a GTDB r207 mediante la tabla de equivalencias de S-04. No se unen HoloFood y el catálogo por nombre de género sin esa tabla: un _join_ directo deja fuera el 77 % de los géneros y asigna mal los que GTDB dividió. 

Cifras de S-03 + D-04: coinciden por nombre 100 de 483 géneros (21 %), que reúnen el 83 % de las lecturas asignadas a género; solo ~49 % de esas lecturas tienen un par <mark>`1:1`</mark> inequívoco. Además, solo el 44,7 % de las lecturas SSU llega a género. 

Como el 55 % de las lecturas no llega a género, Investigación **propone** agregar esas lecturas en un nodo residual por familia (por ejemplo, «Lachnospiraceae sin género»). Así las abundancias relativas siguen sumando 1, y esos nodos no reciben aristas funcionales. Esta propuesta del líder debe confirmarse con los autores de S-03 + D-04. La ruta Kraken2/Bracken contra el catálogo resolvería el punto de raíz, porque la taxonomía nacería en GTDB. 

Rutas y funciones: KEGG (módulos y ortólogos) y CAZy, según S-03. 

### **4.5. D-05 · Criterio de aristas sustentadas e inferidas — Corrige** 

Se resuelve con V-01 (sección 3.1). 

### **4.6. D-06 · Ecuaciones y tolerancias bioquímicas — Pendiente** 

La formalización corresponde a la Actividad 78 de Investigación y se entregará antes de F5. Se adelantan dos principios que ya condicionan F4: 

- Las relaciones estequiométricas de la fermentación se escriben en proporciones molares (Wolin, 1960). Se aplican directo a la composición que predice el modelo. 

- Los balances de masa en cantidades absolutas necesitan el total, que hoy no se predice fuera del corral (R² de log T ≈ 0). Por eso la salida del total se mantiene aunque sea débil. 

### **4.7. D-07 · Partición y validación externa — Confirma, con método** 

Se confirma particionar por corral y se fija el método del entregable D-07: 

- Validación cruzada agrupada por <mark>`pen_code`</mark> y estratificada por dieta (StratifiedGroupKFold), **k = 5** , al menos **10 semillas** , informando media y dispersión. 

- Con 5 folds quedan 11 a 13 animales y 5 a 8 corrales por fold, con las tres dietas en todos. k no puede superar 6: Prebiótico tiene animales en solo 6 corrales. 

- Se descartan un corral por fold (16 de 32 folds tendrían un solo animal y 26 no tendrían Prebiótico) y dejar un ensayo fuera (el ensayo CC no tiene animales Probiótico). 

- Se agrega un **baseline que use solo el día de muestreo** y métricas por día: el día aporta 25 de los 47 puntos de R² del diseño en log(propionato/acetato) (D-03). 

La partición oficial 2.0.0 deja val con 7 animales en 5 corrales. Investigación recomienda usar la validación cruzada como evaluación principal; mantener además un test fijo es decisión del sublíder de Desarrollo. Sobre validación externa: D4 MTBLS560 se acepta solo si Investigación verifica que comparte especie, matriz y unidad (S-06). 

### **4.8. D-08 · Tipos de nodo obligatorios en datos reales — Corrige** 

Para el primer modelo son obligatorios **dieta, taxón, función, metabolito y huésped** . Sin nodos de función, los taxones quedan aislados y un modelo de grafos no puede usar el microbioma para predecir AGCC (hallazgo 7.1 de la solicitud). 

Propuesta para NOD-12 en datos reales: <mark>`ERROR`</mark> si falta alguno de esos cinco tipos, una vez entregada la tabla de equivalencias de S-04; hasta entonces, la ausencia de función sigue como advertencia. Aditivo, sustrato y fenotipo siguen como advertencia: dependen de S-01, S-02 y V-04. 

## **5. Información e insumos solicitados (S-01 a S-07)** 

### **5.1. S-01 y S-02 · Dieta basal y publicación del ensayo — Pendientes** 

Investigación aún no identifica la publicación primaria del ensayo de pollo de HoloFood; una búsqueda preliminar (16-10-2026) no la encontró. Se buscará por los autores del consorcio y por los estudios ENA del ensayo (ERP122587, ERP125074, ERP131894). De ella saldrán la composición de la dieta basal por fase (S-01), la confirmación de los tratamientos (D-02) y el método analítico de los AGCC (V-03, V-06): materia seca, hora de muestreo y lote analítico. Si no existe una publicación del ensayo, se declarará como limitación y la dieta se tomará del protocolo del portal, con evidencia <mark>`literature_curation` .</mark> 

### **5.2. S-03 · Fuente de anotación funcional — Confirma** 

Se aprueba el catálogo **MGnify chicken-gut v1.0.1** como fuente de anotación <mark>`taxon` →</mark> <mark>`has_capacity` →</mark> <mark>`function` ,</mark> con KEGG y CAZy por genoma. El 93 % de sus genomas (12 499 de 13 386) se ensamblaron de los propios metagenomas de HoloFood, lo que hace esperable una cobertura alta del microbioma de D1. Condición: solo los taxones con enlace <mark>`1:1`</mark> en la tabla de S-04 reciben aristas anotadas (V-01). 

### **5.3. S-04 · Compatibilidad SILVA–GTDB y colisiones — Parcial** 

El criterio queda fijado; la curación sigue abierta. 

- **Tabla de equivalencias versionada** SILVA 132 → GTDB r207 a nivel de género, generada por <mark>`compare_silva_mgnify_genera.py` .</mark> Cada fila marca su relación: <mark>`1:1` ,</mark> <mark>`1:N`</mark> o <mark>`sin par` .</mark> 

- **Curación pendiente** de los casos <mark>`1:N`</mark> (por ejemplo, _Bacteroides_ , 14,9 % de las lecturas a género, que corresponde a _Bacteroides_ , _Bacteroides_E_ y _Phocaeicola_ ; y _Lactobacillus_ , dividido en 2020) y de los cinco géneros abundantes sin par ( _Subdoligranulum_ , _Oscillibacter_ , _Tyzzerella_ , _Ruminiclostridium_ , _Phascolarctobacterium_ ; 7,7 % de las lecturas a género). Fuente candidata: la columna <mark>`ssu_silva_taxonomy`</mark> de los metadatos de GTDB r207. 

- **Colisiones de nombre:** no se suman. <mark>`taxon_id`</mark> debe incluir el prefijo de rango ( <mark>`p__Actinobacteria`</mark> y <mark>`c__Actinobacteria`</mark> son nodos distintos), porque agrupan lecturas resueltas a rangos distintos. Con el género como rango de trabajo, ambos quedan como residuales sin aristas funcionales. 

### **5.4. S-05 · Umbral de profundidad — Parcial** 

Umbral provisional para F4: **≥ 1000 lecturas SSU** por animal, el mismo que usan D-07 y <mark>`holofood-source.md` .</mark> Desarrollo debe informar una sensibilidad con 5000 lecturas. Efecto en la cohorte: 2 de los 59 animales tienen menos de 1000 lecturas; Desarrollo debe confirmar si alguno es SAMEA112905124, porque la cohorte final quedaría en 56 o 57 animales. 

### **5.5. S-06 · Fuentes adicionales — Pendiente** 

Investigación evaluará D4 (MTBLS560) para verificar especie, matriz, unidad y si trae microbioma del mismo animal. Los <mark>`ERZ` …</mark> dependen del conteo pedido en V-05. No se comprometen fuentes nuevas para F4: el desbalance 37/15/7 obliga a declarar exploratoria toda comparación entre tratamientos. 

### **5.6. S-07 · Diccionario de datos del grafo — Parcial** 

El esquema v1 no puede dejar de ser provisional hasta el contrato de datos v2 (Actividad 31). Observaciones para esa versión: 

- **Metabolito:** agregar la representación del objetivo de D-03 (fracción por metabolito y total como salida aparte). Hoy <mark>`graph-builder.md`</mark> guarda la concentración como `y` en <mark>`mmol_kg` .</mark> 

- **Huésped:** declarar en <mark>`covariates`</mark> el ensayo ( <mark>`trial_code` )</mark> , el corral ( <mark>`pen_code` )</mark> , el día de muestreo, el sexo y la raza. 

- **Unidades:** una sola notación canónica de máquina ( <mark>`mmol_kg` ,</mark> <mark>`g_kg` )</mark> y una etiqueta de 

   - presentación; hoy conviven <mark>`g_kg`</mark> y <mark>`g/kg` .</mark> 

- **Estados de evidencia:** consolidar en los cinco de DS-01. <mark>`experimental`</mark> y <mark>`literature`</mark> de <mark>`data.schema`</mark> pasan a ser valores de <mark>`evidence_method`</mark> (Tabla 4), no estados. 

- **<mark>`sample_matrix` :</mark>** vocabulario cerrado con <mark>`caecum_content`</mark> como único valor admitido en F4. 

## **6. Inconsistencias detectadas y cambios que se piden a Desarrollo** 

Al contrastar la solicitud con el repositorio y con los entregables, Investigación encontró siete puntos que Desarrollo debe corregir o conciliar. La nota de conciliación de la solicitud (61 frente a 59) queda resuelta. 

**Tabla 6.** Inconsistencias y acción pedida 

|N°|Inconsistencia|Explicación|Acción pedida a Desarrollo|
|---|---|---|---|
|1|61 grafos con<br>metabolitos frente a 59<br>animales emparejados|2 animales solo traen lactato; no<br>tienen ningún AGCC volátil (S-03 +<br>D-04).|Documentar la causa en el<br>reporte de validación.|
|2|Cohorte de 59 (solicitud,<br>D-07) frente a 58 (D-03)|D-03 excluye SAMEA112905124<br>por perfil repetido.|Usar 58 como cohorte oficial<br>y volver a correr la tabla de<br>folds de D-07 sobre 58.|
|3|Perfiles de AGCC<br>idénticos en 4 pares de<br>animales (8 animales)|Probable error de carga del portal;<br>SAMEA112905116 trae los valores<br>de SAMEA112905124<br>redondeados, lo que sugiere que la<br>copia es la primera. Dos pares unen<br>corrales y dietas distintos.|Excluir los 8 de todo análisis<br>de AGCC hasta la respuesta<br>del portal; Investigación hará<br>el aviso.|



|N°|Inconsistencia|Explicación|Acción pedida a Desarrollo|
|---|---|---|---|
|4|228 animales con AGCC<br>(D-07) frente a 227<br>(D-03); 149 frente a 148<br>pares de corral gemelo|D-03 quita además el único animal<br>con propionato igual a cero<br>(SAMEA112904762), que la<br>log-razón no admite.|Ninguna; se registra para<br>que las cifras no se lean<br>como contradicción.|
|5|NOD-08 cuenta<br>`metabolite.concentra`<br>`tion` ausente en 61<br>instancias|El valor vive en`y`; con fracciones<br>como objetivo (D-03), el registro<br>cambia.|Revisar NOD-08 al aplicar el<br>contrato v2.|
|6|Unidad «µmol/g<br>digesta» sin base<br>declarada|Las tablas no traen materia seca.|Declarar base húmeda en<br>`unit` o en un atributo de<br>matriz.|
|7|`holofood-source.md`<br>declara entregables los<br>185 grafos|Son íntegros, pero solo la cohorte<br>de 58 tiene objetivo; 124 no tienen<br>nodos de metabolito.|Aclarar que el conjunto<br>supervisado es la cohorte, y<br>separar los demás para<br>tareas sin objetivo.|



Además, dos efectos de los datos condicionan cualquier resultado de F4 y deben quedar explícitos en los informes de modelos: 

- **Dieta confundida con el día de muestreo.** En el día 35 hay 26 Control, 3 Probiótico y 2 Prebiótico, y Control tiene 31 machos de 37. Estratificar por dieta deja algún fold sin uno de los días en 40 de 100 semillas (D-07). Por eso se piden métricas por día (sección 4.7). 

- **Efecto del ensayo en la composición.** El ensayo aporta 13 puntos a log(propionato/acetato) sin que cambie la dieta (D-03). Investigación decidirá si entra al grafo como covariable del huésped o como nodo; para F4, como covariable. 

## **7. Compromisos y próximos pasos** 

Con esta respuesta, Desarrollo puede empezar F4 con la cohorte de 58, el objetivo composicional y la validación cruzada de D-07. El primer paso conjunto es el contrato de datos v2 (Actividad 31), porque cambia el objetivo del grafo. 

**Tabla 7.** Compromisos de cada célula 

|Compromiso|Célula|Punto|Responsable|Fecha|
|---|---|---|---|---|
|Redactar el contrato de datos REMIX v2|Investigación y|D-03,|Vicente|Por definir|
|(objetivo composicional, total aparte,<br>covariables del huésped, unidades)|Desarrollo|S-07|Fuentes y Julio<br>Provoste||
|Aplicar el vocabulario de<br>`evidence_method` ylas correcciones de|Desarrollo|V-01|Por definir|Por definir|



|Compromiso|Célula|Punto|Responsable|Fecha|
|---|---|---|---|---|
|EDG-04; volver a correr el reporte de<br>validación|||||
|Curar los casos `1:N` y los cinco géneros<br>abundantes sin par de la tabla de<br>equivalencias|Investigación|S-04,<br>D-04|Por definir|Por definir|
|Identificar la publicación del ensayo y<br>extraer la dieta basal y el método<br>analítico|Investigación|S-01,<br>S-02,<br>D-02|Por definir|Por definir|
|Avisar al portal HoloFood de los 4 pares<br>de perfiles repetidos|Investigación|Tabla<br>6, N° 3|Por definir|Por definir|
|Contar animales con ambas matrices de<br>AGCC y comparar valores|Desarrollo|V-03|Por definir|Por definir|
|Contar animales con AGCC de contenido<br>que agregarían los `ERZ`…|Desarrollo|V-05,<br>S-06|Por definir|Por definir|
|Confirmar la cohorte final tras el umbral<br>de 1000 lecturas|Desarrollo|S-05|Por definir|Por definir|
|Repetir los baselines de A45-2 con<br>fracción y log T como objetivos, más un<br>baseline solo de día|Desarrollo|D-03,<br>D-07|Por definir|Por definir|
|Entregar la formalización de<br>restricciones bioquímicas|Investigación|D-06|Por definir|Antes de F5|



Toda corrección futura de V-01 o V-02 se comunicará con una nueva versión de este documento, para que Desarrollo vuelva a correr el reporte de validación y 

<mark>`tests/integration/test_holofood_graph.py` .</mark> 

## **8. Emisión y control de versiones** 

Yo, **Vicente Fuentes Rodríguez** , sublíder del Área de Investigación del proyecto Microbioma Digital, confirmo la emisión de este documento a la Célula de Desarrollo. Su contenido refleja los entregables D-03, D-07 y S-03 + D-04 y las decisiones del líder del área a la fecha indicada. 

**Tabla 8.** Datos de emisión 

|Campo|Detalle|
|---|---|
|Documento|Respuesta de la Célula de Investigación a la Solicitud de|
||revisión v1.1|
|Emitido por|Célula de Investigación · Proyecto NutriGraphDT|



|Campo|Detalle|
|---|---|
|Responsable de la emisión|Vicente Fuentes Rodríguez, Sublíder del Área de Investigación|
|Destinatario|Célula de Desarrollo · Sublíder Julio Provoste Palacios|
|Fecha de emisión|16-10-2026|
|Versión|1.0|
|Estado|Emitido, a la espera de acuse de Desarrollo|



**Vicente Fuentes Rodríguez** · Sublíder del Área de Investigación · Microbioma Digital · Confirma la emisión · 16-10-2026 

**Tabla 9.** Control de versiones 

|Versión|Fecha|Cambios|Responsable|
|---|---|---|---|
|1.0|16-10-2026|Respuesta inicial a los 21 puntos de la<br>solicitud v1.1.|Vicente Fuentes Rodríguez|



## **Referencias** 

Aitchison, J. (1986). _The Statistical Analysis of Compositional Data_ . Chapman & Hall. 

Área de Investigación · Microbioma Digital. (2026). D-03 · ¿Predecir cantidad (mmol/kg) o fracción del total (%)? Entregable interno, con <mark>`d03_agcc.py` ,</mark> <mark>`tablas.md`</mark> y <mark>`resumen.json` .</mark> 

Área de Investigación · Microbioma Digital. (2026). D-07 · Validación cruzada por corral en los 59 animales. Entregable interno, 16-10-2026, con <mark>`d07_corrales.py` .</mark> 

Área de Investigación · Microbioma Digital. (2026). S-03 + D-04 · Géneros SILVA de HoloFood frente al catálogo MGnify chicken-gut v1.0.1. Entregable interno, con <mark>`compare_silva_mgnify_genera.py` .</mark> 

Área de Investigación · Microbioma Digital. (2026). Esquema General del proyecto Microbioma Digital. Documento interno, §2.2, §3.1, §5 y §6.1. 

Célula de Desarrollo · NutriGraphDT. (2026). Solicitud de revisión a la Célula de Investigación, versión 1.1, 07-10-2026. 

Célula de Desarrollo · NutriGraphDT. (2026). Documentación del repositorio jvnioo/NutriGraphDT, carpeta docs/ (fuente D1 HoloFood, propuesta de evidencia y escenario, reporte de validación, esquema v1, diccionario de datos y reglas de integridad 1.2.0). https://github.com/jvnioo/NutriGraphDT 

García-López, M. et al. (2019). Analysis of 1,000 type-strain genomes improves taxonomic classification of Bacteroidetes. _Frontiers in Microbiology_ , 10, 2083. 

Giglio, M. et al. (2019). ECO, the Evidence & Conclusion Ontology: community standard for evidence information. _Nucleic Acids Research_ , 47(D1), D1186–D1194. https://doi.org/10.1093/nar/gky1036 

Rogers, A. B., Kale, V., Baldi, G., et al. (2025). HoloFood Data Portal: Holo-omic datasets for analysing host–microbiota interactions in animal production. _Database, 2025_ , baae112. https://doi.org/10.1093/database/baae112 

Wolin, M. J. (1960). A theoretical rumen fermentation balance. _Journal of Dairy Science_ , 43, 1452–1459. 

Zheng, J. et al. (2020). A taxonomic note on the genus _Lactobacillus_ . _International Journal of Systematic and Evolutionary Microbiology_ , 70, 2782–2858. 

