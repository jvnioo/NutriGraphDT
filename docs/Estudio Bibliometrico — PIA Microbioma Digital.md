

## **Microbioma Digital**

**Gemelo Digital Nutricional · GNN + PINNs** PIA-2 · Sección 302 · Gestión de Proyectos Informáticos · UTEM · 2026-II Paleta de Colores del proyecto:

**#25A3A8 #0E9987 #087F9E #0767A0 #032E54**

# **Estudio Bibliométrico**

**PIA-2 · Microbioma Digital - Gemelo Digital Nutricional basado en GNN y PINNs Actividad 13: Estudio del estado del arte y análisis bibliométrico sobre microbioma, GNN, PINN y gemelos digitales.**

04 de septiembre de 2026 **—** 21 de septiembre de 2026

_Documento final del área de Investigación · Estudio bibliométrico_

**Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II**

**Área de Investigación · Sublíder Vicente Fuentes Rodríguez**

**Profesor Eduardo Osorio Venegas**

Versión Final · 21-09-2026

### **Índice**

|**1. Alcance y objetivo del estudio**|**6**|
|---|---|
|**2. Preguntas de investigación**|**7**|
|**3. Metodología**|**8**|
|3.1. Diseño|8|
|3.2. Estrategia de búsqueda en dos fases|8|
|3.3. Bases de datos|8|
|3.4. Criterios de inclusión y exclusión|9|
|3.5. Procesamiento y limpieza|9|
|3.6. Software y parámetros de análisis|10|
|3.7. Flujo de selección (PRISMA 2020)|10|
|**4. Resultados**|**12**|
|4.1. Composición del corpus|12|
|4.2. Intersección entre ejes|12|
|4.3. Evolución de la producción|12|
|4.4. Impacto|13|
|4.5. Fuentes|14|
|4.6. Países y colaboración|14|
|4.7. Estructura conceptual global|16|
|4.8. Estructura conceptual por eje|17|
|4.9. Base intelectual (co-citación)|21|
|4.10. Cadena complementaria: gemelo digital|23|
|**5. Síntesis cualitativa del estado del arte**|**24**|
|5.1. Propósito y criterio de selección|24|
|5.2. Aprendizaje sobre grafos aplicado a comunidades microbianas|24|
|5.3. Aprendizaje científicamente restringido|25|
|5.4. Modelamiento mecanístico de la relación dieta–microbioma|26|
|5.5. Microbioma y nutrición en especies de producción|26|
|5.6. Gemelos digitales|27|
|5.7. Síntesis integradora|28|
|**6. Discusión**|**30**|
|**7. Limitaciones**|**31**|
|**8. Conclusiones**|**33**|
|**9. Insumos que este documento habilita**|**34**|
|**Anexo A — Ecuaciones de búsqueda por base**|**35**|
|A.1 Scopus — bloque de filtros común|35|
|A.2 Scopus — Eje A: aprendizaje sobre grafos|35|
|A.3 Scopus — Eje B: aprendizaje científicamente restringido|35|
|A.4 Scopus — Eje C: microbioma y dieta en especies de producción|35|
|A.5 Scopus — Eje D: modelamiento mecanístico y estequiométrico|35|
|A.6 Scopus — Cadenas de intersección|35|
|A.7 Otras bases (cribado documental, no bibliométrico)|36|



2

|A.8 Scopus — Cadenas complementarias de gemelo digital|37|
|---|---|
|**Anexo B — Registro de búsquedas**|**38**|
|**Anexo C — Tablas de datos detalladas**|**39**|
|**Referencias**|**42**|



3

### **Índice de figuras**

|Figura 1. Producción anual por eje temático (Scopus, 2021–2025)<br>11|
|---|
|Figura 2. Red de colaboración entre países (Scopus, 2021–2025)<br>13|
|Figura 3. Red de colaboración entre países según citas promedio<br>13|
|Figura 4. Mapa de co-ocurrencia de palabras clave del autor en la literatura sobre microbioma<br>intestinal y modelamiento computacional (Scopus, 2021–2025)<br>15|
|Figura 5. Mapa de co-ocurrencia de palabras clave del autor del eje A (aprendizaje sobre grafos) 17|
|Figura 6. Mapa de co-ocurrencia de palabras clave del autor del eje B (aprendizaje científicamente<br>restringido)<br>18|
|Figura 7. Mapa de co-ocurrencia de palabras clave del autor del eje D (modelamiento mecanístico)<br>19|
|Figura 8. Red de co-citación de referencias citadas (Scopus, 2021–2025)<br>20|
|Figura 9. Mapa de densidad de co-citación de referencias citadas<br>21|



4

### **Índice de tablas**

|Tabla 1. Preguntas de investigación y técnicas asociadas|7|
|---|---|
|Tabla 2. Definición operativa de los ejes temáticos|8|
|Tabla 3. Criterios de inclusión y exclusión|9|
|Tabla 4. Parámetros de los mapas generados|10|
|Tabla 5. Flujo de identificación y selección de la fase definitiva|10|
|Tabla 6. Composición del corpus por eje|12|
|Tabla 7. Intersecciones entre ejes (Scopus, 2021–2025)|12|
|Tabla 8. Producción anual y tasa de crecimiento anual (TCA) por eje|12|
|Tabla 9. Indicadores de impacto por eje|13|
|Tabla 10. Fuentes principales por eje|14|
|Tabla 11. Países con mayor producción y países con mayor impacto relativo|14|
|Tabla 12. Clústeres del mapa de co-ocurrencia global|16|
|Tabla 13. Dominio de aplicación de cada eje metodológico|18|
|Tabla 14. Referencias más co-citadas|20|
|Tabla 15. Cadenas complementarias de gemelo digital (Scopus, 2021–2025)|23|
|Tabla 16. Síntesis de los antecedentes más próximos al proyecto|28|



5

### **1. Alcance y objetivo del estudio**

Este documento reporta el estudio bibliométrico del área de Investigación del proyecto **Microbioma Digital** , orientado a caracterizar cuantitativamente la literatura científica sobre los cuatro ejes de relevancia definidos en el protocolo de inclusión y exclusión del proyecto, y a verificar empíricamente la brecha de investigación formulada en el documento _Antecedentes Generales_ (Actividad 6).

El estudio responde a una pregunta que el consolidado de antecedentes dejó planteada pero no podía resolver con diez fichas institucionales: **si la ausencia de trabajos en la intersección de los ejes es un rasgo sistemático de la literatura o un artefacto del muestreo de entidades revisadas** .

**Objetivo general:** Caracterizar la producción científica 2021–2025 sobre modelamiento computacional aplicado al microbioma intestinal y sobre microbioma y dieta en especies de producción animal, y cuantificar el grado de integración entre ambos dominios.

**Objetivos específicos:**

1. Describir el volumen, la evolución, el impacto y la distribución editorial y geográfica de la producción en cada eje temático.

2. Mapear la estructura conceptual de cada eje y del conjunto.

3. Cuantificar las intersecciones entre ejes.

4. Identificar la base intelectual del campo mediante análisis de co-citación.

5. Contrastar los hallazgos con la brecha formulada en el consolidado de antecedentes.

6

### **2. Preguntas de investigación**

**Tabla 1. Preguntas de investigación y técnicas asociadas**

|**Código**|**Pregunta**|**Técnica que la responde**|
|---|---|---|
|PI1|¿Cómo evolucionó la producción científica de cada eje<br>entre 2021 y 2025?|Producción anual y tasa de crecimiento<br>anual|
|PI2|¿Cuál es el impacto relativo de cada eje?|Citas totales, citas por documento,<br>índice h (Hirsch, 2005)|
|PI3|¿En qué revistas y países se concentra cada eje?|Recuento de fuentes y afiliaciones;<br>co-autoría por países|
|PI4|¿Cuál es la estructura temática del campo y dónde se<br>ubican los términos metodológicos?|Co-ocurrencia de palabras clave del<br>autor|
|PI5|¿En qué dominio de aplicación se concentra cada eje<br>metodológico?|Co-ocurrencia por eje|
|PI6|¿Existen documentos que integren dos o más ejes?|Cadenas de intersección y<br>solapamiento en el corpus unificado|
|PI7|¿Cuál es la base intelectual compartida del campo?|Co-citación de referencias citadas|



_Elaboración Propia_

Se formularon siete preguntas de investigación que abordan la evolución temporal, el impacto, la distribución geográfica, la estructura temática, las intersecciones entre ejes y la base intelectual del campo. La Tabla 1 sintetiza estas interrogantes y detalla las técnicas métricas y de análisis asociadas para darles respuesta. A continuación, se detalla el alcance metodológico de cada una de las interrogantes para contextualizar los hallazgos del estudio:

1. **PI1 (Evolución temporal)** : Permite dimensionar el dinamismo y el interés creciente de la comunidad científica en cada frente analizado, evidenciando el acelerado despegue de los enfoques metodológicos avanzados frente a la producción más estable del dominio tradicional de producción animal.

2. **PI2 (Impacto relativo)** : Evalúa la relevancia y la repercusión de la literatura mediante el análisis de citas totales, promedio por documento y el índice h, destacando cuáles frentes generan mayor tracción académica e influencia en la disciplina.

3. **PI3 (Concentración editorial y geográfica)** : Identifica los principales polos de producción científica y revistas de acogida, permitiendo reconocer la existencia de comunidades editoriales fragmentadas y la distribución global del esfuerzo de investigación.

4. **PI4 (Estructura temática global)** : Mapea la co-ocurrencia de palabras clave para revelar la arquitectura conceptual del campo, evidenciando la distancia temática y topológica entre los clústeres aplicados de producción animal y los términos metodológicos avanzados.

5. **PI5 (Dominio de aplicación metodológica):** Precisa los contextos biológicos y clínicos específicos en los que efectivamente se despliegan las técnicas de modelamiento (como biomedicina humana o microbiota de suelo), contrastándolos con las necesidades de las especies de producción.

6. **PI6 (Intersección entre ejes)** : Cuantifica empíricamente el grado de integración interdisciplinaria en la literatura existente mediante el análisis de solapamientos y cadenas de búsqueda combinadas, confirmando la ausencia de trabajos previos en las áreas críticas del proyecto.

7

7. **PI7 (Base intelectual compartida)** : Examina las redes de co-citación de referencias para determinar los cimientos teóricos y metodológicos sobre los cuales se construye el campo, identificando la desconexión entre la literatura clásica de nutrición animal y los frentes de modelamiento computacional.

8

### **3. Metodología**

#### **3.1. Diseño**

Se realizó un estudio bibliométrico descriptivo y de mapeo científico, siguiendo las directrices de Donthu et al. (2021) y el marco metodológico de Zupic y Čater (2015). El reporte del proceso de identificación y selección se ajustó a la declaración PRISMA 2020 (Page et al., 2021). El análisis combina dos familias de técnicas: análisis de rendimiento (indicadores descriptivos de productividad e impacto) y mapeo científico (co-ocurrencia de términos, co-autoría y co-citación).

#### **3.2. Estrategia de búsqueda en dos fases**

**Fase exploratoria.** Se aplicó en Scopus, el 19 de septiembre de 2026, una ecuación general que combinaba términos de modelamiento computacional, microbioma intestinal y dieta o especies de producción, restringida al periodo 2021–2025. Se recuperaron **635 registros** , de los cuales **484** mencionan explícitamente técnicas de modelamiento en el título, el resumen o las palabras clave del autor. Al contrastar esos registros con los cuatro ejes de relevancia del protocolo del proyecto, se constató que **370 (76 %) no cubrían ningún eje** y que la literatura recuperada correspondía mayoritariamente a estudios de salud humana: solo **59 registros (12 %)** abordaban especies de producción animal.

**Fase definitiva.** Dado que el protocolo define la brecha como la intersección entre ejes, se adoptó una estrategia de búsqueda por eje temático, complementada con cadenas de intersección:

**Tabla 2. Definición operativa de los ejes temáticos**

|**Eje**|**Definición operativa**|
|---|---|
|**A**|Aprendizaje sobre grafos: construcción explícita de un grafo y aprendizaje sobre él mediante GNN en<br>dominio biológico, metabólico o microbiano|
|**B**|Aprendizaje científicamente restringido: PINN,_neural ODE_,_scientific machine learning_y modelos con<br>restricciones ecológicas o dinámicas explícitas|
|**C**|Microbioma gastrointestinal y dieta en especies de producción animal|
|**D**|Modelamiento mecanístico y estequiométrico del metabolismo microbiano|
||_Elaboración Propia_|



Las cadenas de intersección ejecutadas fueron A∩C, B∩C y C∩D. Las ecuaciones completas se presentan en el **Anexo A** y el registro de todas las ejecuciones, incluidas las que no arrojaron resultados, en el **Anexo B** . Adicionalmente, se ejecutaron dos cadenas complementarias sobre el concepto de gemelo digital (sección 4.10).

_Nota de transparencia: el cambio de estrategia no se debió a los resultados obtenidos, sino a que la ecuación general no se alineaba con la definición de relevancia establecida en el protocolo del proyecto (versión 1.0, 09-09-2026), anterior a la búsqueda. El protocolo existía antes; la primera ecuación simplemente no lo utilizó._

#### **3.3. Bases de datos**

**Scopus constituyó la base del análisis bibliométrico.** La elección respondió a la adecuación al método y no a una supuesta superioridad general de la base. El análisis bibliométrico requiere metadatos completos y homogéneos —referencias citadas, afiliaciones, palabras clave del autor y recuento de citas— exportables en un formato compatible con el software de mapeo, requisito que

9

Scopus cumple de forma integral. Scopus presenta además una cobertura de revistas más amplia que Web of Science (Mongeon & Paul-Hus, 2016), con representación relevante en ingeniería, computación y ciencias agrarias. Google Scholar, pese a su mayor exhaustividad, se descartó como fuente principal por sus limitaciones de precisión, control de la búsqueda y reproducibilidad (Gusenbauer & Haddaway, 2020). La designación de Scopus como base principal estaba establecida en el protocolo del proyecto con anterioridad a la ejecución de las búsquedas. El análisis cuantitativo se restringió a esta base para preservar la homogeneidad de los metadatos.

**Web of Science se utilizó como control cruzado.** Se ejecutó en ella la cadena del eje A: de **186 registros con DOI recuperable, 164 (88 %)** ya estaban presentes en el corpus de Scopus, lo que confirma una cobertura adecuada de la base principal.

**Las demás bases alimentaron el cribado documental del proyecto, no el análisis bibliométrico:** PubMed (ejes C y D), IEEE Xplore (eje A), ScienceDirect (eje B) y SciELO (producción regional latinoamericana). ACM Digital Library, Redalyc y Google Scholar se consultaron sin exportación masiva, por no estar diseñadas para ese fin; sus resultados se registraron por conteo en pantalla.

#### **3.4. Criterios de inclusión y exclusión**

**Tabla 3. Criterios de inclusión y exclusión**

|**Criterio**|**Inclusión**|**Exclusión**|
|---|---|---|
|Periodo|2021–2025|Fuera de rango|
|Tipo documental|Artículo, revisión, ponencia|Editorial, errata, capítulo, libro|
|Idioma|Inglés, español, portugués|Otros|
|Contenido|Cobertura de al menos un eje, según la<br>cadena de origen|Sin cobertura de eje|



_Elaboración Propia_

**Justificación del periodo.** Se delimitó a cinco años completos porque los indicadores de producción anual y la tasa de crecimiento requieren años cerrados; 2026 se excluyó por estar incompleto al momento de la búsqueda.

**Excepción temporal.** Documentos anteriores a 2021 se consideran únicamente cuando el contenido requerido (definiciones fundacionales, métodos originales o datos de referencia) no está disponible en la literatura del periodo. Estos documentos **no forman parte del corpus analizado** y se identificaron mediante el análisis de co-citación (sección 4.9), que los sustenta empíricamente.

**Efecto del filtro idiomático.** La ecuación exploratoria sin restricción de idioma recuperó 635 registros y con restricción a inglés recuperó 634: la exclusión afectó a **un solo documento (0,16 %)** , por lo que su efecto sobre los resultados es despreciable.

#### **3.5. Procesamiento y limpieza**

Los registros se exportaron en formato CSV con todos los campos, incluidas las referencias citadas. La depuración comprendió cuatro operaciones:

1. **Aplicación de filtros** de año, idioma y tipo documental mediante rutinas reproducibles en Python, dado que las exportaciones se realizaron sin filtros en la interfaz.

2. **Eliminación de duplicados** por EID, DOI y título normalizado.

10

3. **Construcción de un tesauro de 475 equivalencias** para VOSviewer, que unifica plurales, ortografía británica y estadounidense, siglas (GNN, PINN, FBA, GEM) y sinónimos de dominio. El tesauro redujo las palabras clave únicas de **7.318 a 6.843** .

4. **Verificación de integridad** : 0 duplicados residuales por EID, DOI o título; 9 de 4.127 registros sin referencias citadas exportadas.

**Se declaran dos decisiones de normalización:**

- Se unificaron _microbiome_ y _microbiota_ , práctica habitual en bibliometría dado su uso intercambiable en la literatura, pese a que técnicamente no son equivalentes.

- Se mantuvo “performance” separado de “growth performance”, porque en los ejes metodológicos el primero designa el desempeño de un modelo y no el desempeño productivo del animal.

#### **3.6. Software y parámetros de análisis**

El análisis de rendimiento se realizó mediante rutinas en Python (pandas) sobre los metadatos depurados. El mapeo científico se ejecutó en **VOSviewer 1.6.21** (van Eck & Waltman, 2010), con normalización por **fuerza de asociación** ( _association strength_ ) y resolución de clustering de **1,00** con tamaño mínimo de clúster de **1** (valores por defecto del programa) en todos los mapas.

**Tabla 4. Parámetros de los mapas generados**

|**Mapa**|**Corpus**|**Análisis**|**Unidad**|**Conteo**|**Umbral**|**Ítems**|**Clústeres**|
|---|---|---|---|---|---|---|---|
|Co-ocurrencia global|Unión<br>(4.127)|Co-occurrenc<br>e|Author<br>keywords|Full|10<br>ocurrencias|209|9|
|Co-ocurrencia eje A|168|Co-occurrenc<br>e|Author<br>keywords|Full|2<br>ocurrencias|52|13|
|Co-ocurrencia eje B|36|Co-occurrenc<br>e|Author<br>keywords|Full|2<br>ocurrencias|22|5|
|Co-ocurrencia eje D|372|Co-occurrenc<br>e|Author<br>keywords|Full|4<br>ocurrencias|56|8|
|Colaboración por<br>países|Unión<br>(4.127)|Co-authorshi<br>p|Countries|Fractional|10<br>documentos|50|6|
|Co-citación|Unión<br>(4.127)|Co-citation|Cited<br>references|Full|20 citas|131|5|



_Elaboración Propia_

_Nota: el eje C no se mapeó por separado por representar el 86,3 % del corpus unificado, de modo que su mapa individual sería equivalente al global._

#### **3.7. Flujo de selección (PRISMA 2020)**

**Tabla 5. Flujo de identificación y selección de la fase definitiva**

|**Etapa**|**Registros**|
|---|---|
|Identificados en Scopus (cadenas A, B, C, D)|8.080|
|Excluidos por año, idioma o tipo documental|−3.944|
|Registros filtrados|4.136|
|Duplicados entre cadenas eliminados|−9|



11

|**Etapa**|**Registros**|
|---|---|
|**Corpus final analizado**|**4.127**|



_Elaboración Propia_

_Nota: los 9 registros duplicados corresponden a documentos recuperados simultáneamente por las cadenas C y D, es decir, al único solapamiento observado entre ejes (sección 4.2)._

12

### **4. Resultados**

#### **4.1. Composición del corpus**

El corpus quedó conformado por **4.127 documentos únicos** publicados entre 2021 y 2025. Su distribución evidencia un desbalance pronunciado entre ejes.

**Tabla 6. Composición del corpus por eje**

|**Eje**|**Documentos**|**% del corpus**|
|---|---|---|
|A · Aprendizaje sobre grafos|168|4,1 %|
|B · Aprendizaje científicamente restringido|36|0,9 %|
|C · Microbioma y dieta en producción animal|3.560|86,3 %|
|D · Modelamiento mecanístico|372|9,0 %|
|**Unión (sin duplicados)**|**4.127**|**100 %**|



_Elaboración Propia_

#### **4.2. Intersección entre ejes**

**Las cadenas de intersección confirmaron la ausencia de integración entre los ejes metodológicos y el eje de producción animal.** La cadena A∩C no recuperó ningún registro. La cadena B∩C recuperó un único documento, publicado en 2026 y por tanto fuera de la ventana analizada. La cadena C∩D recuperó 29 registros en el periodo, de los cuales **18 corresponden efectivamente al tracto gastrointestinal** ; los 11 restantes tratan de microbiota de suelo o manejo de purines y constituyen falsos positivos de esa cadena.

**El análisis de solapamiento dentro del corpus unificado replicó el patrón.** Ningún documento pertenece simultáneamente a los ejes A y B, A y C, A y D, B y C, ni B y D. Solo **9 documentos** pertenecen a la vez a los ejes C y D.

**Tabla 7. Intersecciones entre ejes (Scopus, 2021–2025)**

|**Intersección**|**Cadena específica**|**Solapamiento en el corpus unificado**|
|---|---|---|
|A∩B|—|0|
|A∩C|0|0|
|A∩D|—|0|
|B∩C|0|0|
|B∩D|—|0|
|C∩D|29 (18 gastrointestinales)|9|



_Elaboración Propia_

#### **4.3. Evolución de la producción**

La producción creció en los cuatro ejes, pero a ritmos marcadamente distintos. **Los ejes metodológicos crecen entre tres y cinco veces más rápido que el eje de producción animal, partiendo de bases muy inferiores.**

13

**Tabla 8. Producción anual y tasa de crecimiento anual (TCA) por eje**

|**Año**|**A**|**B**|**C**|**D**|**Unión**|
|---|---|---|---|---|---|
|2021|13|2|544|58|616|
|2022|19|2|617|58|694|
|2023|24|7|623|65|718|
|2024|47|4|778|82|909|
|2025|65|21|998|109|1.190|
|**TCA**|**49,5 %**|**80,0 %**|**16,4 %**|**17,1 %**|**17,9 %**|



_Elaboración Propia_

_Nota: la TCA del eje B debe interpretarse con cautela, pues se calcula sobre una base de 2 documentos en 2021._

**Figura 1**

_Producción anual por eje temático (Scopus, 2021–2025)_



<!-- Start of picture text -->
3 1.000<br>5 3 a ae a a<br>E100 ————S rs<br>8<br>7 SS<br>202, 2aze 2023 a2 2025<br>Ao de pubicaciin<br>EHA= 8©.  AprendizaeMerobiomalycient. restingido AW= nian(sin dupicados)<br>deta en prod, anima<br><!-- End of picture text -->

_Nota. Elaboración propia a partir de los metadatos de Scopus. Escala logarítmica en el eje vertical, dado que el eje C supera en dos órdenes de magnitud a los ejes A y B._

#### **4.4. Impacto**

**El eje D presentó el mayor impacto por documento** , con 36,7 citas promedio, más del doble que los restantes ejes, que se sitúan en torno a 17 citas por documento. El eje C, pese a concentrar el volumen, alcanzó el mayor índice h por efecto de su tamaño. El eje B registró la mayor proporción de documentos sin citas, coherente con su carácter reciente.

**Tabla 9. Indicadores de impacto por eje**

|**Indicador**|**A**|**B**|**C**|**D**|
|---|---|---|---|---|
|Documentos|168|36|3.560|372|
|Citas totales|2.979|589|61.548|13.668|
|Citas por documento|17,7|16,4|17,3|**36,7**|
|Índice h|22|12|81|56|



14

|**Indicador**|**A**|**B**|**C**|**D**|
|---|---|---|---|---|
|Documentos sin citas|14 (8,3 %)|6 (16,7 %)|199 (5,6 %)|9 (2,4 %)|



_Elaboración Propia_

#### **4.5. Fuentes**

**Las fuentes revelan comunidades editoriales mayoritariamente separadas; la única fuente compartida entre los títulos principales es** **_Frontiers in Microbiology_ , revista de alcance multidisciplinar.** El eje C se concentra en revistas de producción animal; el eje A, en revistas de bioinformática; el eje D, en revistas de microbiología de sistemas. **El eje B no presenta concentración editorial alguna** : ninguna fuente supera los dos documentos, lo que indica la ausencia de una comunidad consolidada en torno a ese frente.

**Tabla 10. Fuentes principales por eje**

|**Eje**|**Fuentes principales (documentos)**|
|---|---|
|A|_Briefings in Bioinformatics_(19),_Bioinformatics_(7),_BMC Bioinformatics_(7),_Frontiers in Microbiology_(6),<br>_Scientific Reports_(6)|
|B|_Industrial and Engineering Chemistry Research_(2),_Journal of Computational Physics_(2),_Journal of_<br>_Process Control_(2)|
|C|_Poultry Science_(474),_Animals_(338),_Frontiers in Microbiology_(196),_Frontiers in Veterinary Science_<br>(152),_Animal Nutrition_(108)|
|D|_Gut Microbes_(22),_Microbiome_(14),_mSystems_(12),_Frontiers in Microbiology_(11),_ISME Journal_(10)|



_Elaboración Propia_

#### **4.6. Países y colaboración**

El análisis de co-autoría por países (umbral de 10 documentos) identificó **50 países en 6 clústeres de colaboración** : un bloque asiático liderado por China, un bloque occidental liderado por Estados Unidos, un bloque anglo-asiático articulado por el Reino Unido, un bloque de Medio Oriente y sur de Asia, un bloque heterogéneo que reúne a Japón, Países Bajos, Tailandia, Nigeria, Sudáfrica y Argentina, y un bloque nórdico.

**China y Estados Unidos concentran el volumen y, pese a pertenecer a bloques distintos, mantienen el vínculo más intenso de toda la red** (fuerza de enlace fraccional de 75,0), seguido por Egipto–Arabia Saudita (40,4), China–Pakistán (34,1) y Bélgica–China (34,0).

**Tabla 11. Países con mayor producción y países con mayor impacto relativo**

|**Por documentos**|**Docs.**|**Por citas/documento (≥40 docs.)**|**Citas/doc.**|
|---|---|---|---|
|China|2.147|Suecia|41,3|
|Estados Unidos|546|Alemania|31,2|
|Corea del Sur|178|Dinamarca|30,2|
|Egipto|160|Suiza|29,2|
|Alemania|140|Turquía|28,8|
|Italia|132|—|—|



_Elaboración Propia_

15

**Chile participa en la red, en posición periférica del bloque occidental** : 16 documentos, 241 citas, 15,1 citas por documento (por sobre Brasil, con 10,9) y cinco enlaces de colaboración, con España (3,5), Canadá (1,5), China, Francia y México (1,0 cada uno).

**Figura 2**

_Red de colaboración entre países (Scopus, 2021–2025)_



<!-- Start of picture text -->
. = oN<br>i ree gate<br>A Se ~<br>(ae NN.<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21. Co-autoría por países, conteo fraccional, umbral mínimo de 10 documentos (50 países en 6 clústeres). El tamaño del nodo representa el número de documentos y el grosor del enlace, la intensidad de la colaboración._

**Figura 3**

_Red de colaboración entre países según citas promedio_



<!-- Start of picture text -->
hee Z aa See<br>a SS eS ‘<br>La] NSeeee<br>of eX \<br>on a aide ma y<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21. Vista de superposición. La escala de color abarca de 2023,0 a 2023,8, por lo que las diferencias temporales entre países son menores a un año._

16

#### **4.7. Estructura conceptual global**

El mapa de co-ocurrencia de palabras clave del autor sobre el corpus unificado (209 términos, umbral de 10 ocurrencias) identificó **nueve clústeres temáticos** . **Ocho corresponden a investigación en producción animal** , organizados por especie, por tipo de intervención y por variable respuesta. **Un único clúster agrupa los términos metodológicos** , y lo hace junto con temas de salud humana.

**Tabla 12. Clústeres del mapa de co-ocurrencia global**

|**Clúster**|**Ítems**|**Etiqueta temática**|**Términos principales (ocurrencias)**|
|---|---|---|---|
|1|39|Microbiota, fibra y barrera intestinal<br>en porcinos|gut microbiota (1.416), weaned piglet (233), short-chain fatty acid<br>(180), piglet (156), intestinal barrier (135)|
|2|35|**Métodos computacionales y**<br>**microbiología de sistemas**|microbiota (702), prebiotic (93), metagenomics (92),<br>cross-feeding (52), graph neural network (38)|
|3|28|Aditivos y alternativas a antibióticos<br>en aves|probiotic (256), poultry (112), intestinal morphology (85), antibiotic<br>(74)|
|4|23|Desempeño productivo y calidad de<br>carne|growth performance (503), cecal microbiota (162), meat quality<br>(113)|
|5|22|Salud intestinal del broiler|broiler (785), gut health (350), immune response (82), necrotic<br>enteritis (37)|
|6|21|Caracterización ómica y eficiencia<br>alimentaria|pig (220), chicken (146), 16s rrna sequencing (124),<br>metabolomics (114)|
|7|21|Gallinas ponedoras y producción de<br>huevo|laying hen (175), immunity (152), performance (127), egg quality<br>(61)|
|8|12|Cepas probióticas específicas|lactobacillus (41), intestine (40), bacillus subtilis (39)|
|9|8|Antioxidantes y antimicrobianos en el<br>destete|antioxidant (88), weaning (27), antimicrobial resistance (23)|



_Elaboración Propia_

**La separación entre dominios es cuantificable en tres dimensiones:**

**Posición.** La coordenada _x_ promedio de los términos metodológicos es **+1,27** , frente a **−0,28** de los términos de producción animal, en un mapa cuya amplitud total va de −1,23 a +1,53. Las distancias euclidianas entre términos confirman el patrón: “graph neural network” se sitúa a 1,46 de “broiler” y a 1,14 de “pig”; “physics-informed neural network”, a 1,55 y 1,22 respectivamente.

**Conectividad.** Los términos metodológicos presentan la menor fuerza de enlace relativa del mapa. “Physics-informed neural network” registra 13 ocurrencias con apenas **4 enlaces** y una fuerza total de enlace de 5 (razón 0,38, la más baja del mapa); “graph neural network”, 38 ocurrencias con 13 enlaces. Como referencia, “gut microbiota” registra 195 enlaces y una fuerza total de 2.956.

**Novedad.** Son los términos con mayor año promedio de publicación del mapa: physics-informed neural network (2024,2), machine learning (2024,1), graph attention network (2024,0), graph neural network (2023,8), frente a un promedio general de 2023,3.

**Un hallazgo adicional de alto valor para el proyecto:** los términos de caracterización ómica ocupan posiciones intermedias entre ambos dominios —“metagenomics” ( _x_ = 0,77), “multi-omics” ( _x_ = 0,89) y “16s rrna sequencing” ( _x_ = 0,35)—, lo que indica que la generación de datos de secuenciación y metabolómica en especies de producción ya está establecida, aunque su análisis no incorpora las técnicas de modelamiento identificadas.

17

**Figura 4**

_Mapa de co-ocurrencia de palabras clave del autor en la literatura sobre microbioma intestinal y modelamiento computacional (Scopus, 2021–2025)_



<!-- Start of picture text -->
Trio fempeniaton<br>* aeA intestinaliglammation||—%<br>seprosucieperormaet diagneaI onging /__-almelaphimarom *<br>ier tore* SnNOW ba LBL)UN ogpsn temoagra tas coccliosis<br>ntiorcant function werkva  RECGai laraAap |) eaesnla eacin nn — sre bactemides<br>serum metabottesantioxidecospacitygrowth=< NOR wearsy © siiormance.5 ae 9CLOSES4 eTshoreGesh heattyacidyeapstapies ai|@ Sas© crostapeingvidomcteri<br>roving ting gs(evanenoe ag ge AESTjota enseeag metaboligmodelingfifi alee analysis<br>. - cecal raieeobiotsSN Se ee<br>fermented feed, 7 COS med "mi ta erareringity 7 mye,<br>rc rane ‘tesa,/ PG pe ©5 —_ metaaifomics Fryenormneural n a tor<br>aa Li ae, Lape = * rapt thaga neice<br>eestoannres Prodctioniperto rid . Fy, a<br>—_meatpalty, tai CHh,er) bee iS ss IN Tretabolepathways<br>visea laying peormance 7M RISES anerie<br>corms SB 1G huitions anubotteesisance<br>antioxidant activity — perf eS abi VV BaereP nase rcromology<br>sips eis) Je Meera<br>. hermetia illucens¢ ope feed aiiitives<br>insecemeal a a antiga gromth promoter<br>insect bots prod<br>productive performance . ‘sustainability. comHoneterijejuni inflammatory<br>‘Soybean meal ponerse<br>tadson<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21 sobre 4.127 documentos. Umbral mínimo de 10 ocurrencias (209 términos), conteo completo y normalización por fuerza de asociación. El tamaño del nodo representa la frecuencia del término y el color, el clúster temático. Los términos metodológicos se ubican en la periferia derecha del mapa._

#### **4.8. Estructura conceptual por eje**

Los mapas individuales precisan el dominio de aplicación de cada frente metodológico.

**Eje A (52 términos, 13 clústeres).** Los términos dominantes son “graph neural network” (38), “deep learning” (29), “graph convolutional network” (23) y “graph attention network” (17). Las aplicaciones se concentran en predicción de asociaciones microbio-enfermedad y microbio-fármaco en humanos, y en tareas bioinformáticas (identificación viral, predicción de hospedero de fagos, clasificación). **En los 168 documentos del eje no se registró ninguna palabra clave de producción animal.** El término “nutrition” aparece en dos documentos —ambos de nutrición clínica humana, junto a “extremely preterm infants” y “feeding advancement”— y figura en el mapa **con 0 enlaces** . La fragmentación es alta: 13 clústeres para 52 términos, siete de ellos con tres ítems o menos.

18

**Eje B (22 términos, 5 clústeres).** El término central es “physics-informed neural network” (13 ocurrencias, 14 enlaces). **La única aplicación microbiana identificable corresponde a microbiota de suelo y sistemas suelo-planta** : el clúster 2 agrupa “soil microbiota growth”, “am fungi”, “arbuscular mycorrhizal fungi”, “pde”, “numerical methods” y “biology”. Un segundo clúster reúne “neural ode”, “machine learning”, “neural networks”, “lotka-volterra system”, “scientific machine learning”, “dynamical systems” y “time series”. **No se registró ningún término de producción animal ni de tracto gastrointestinal animal.** La red es la menos cohesionada del estudio, con un ítem completamente aislado (ver limitación 7.4).

**Eje D (56 términos, 8 clústeres).** Es el mapa más cohesionado. Los términos dominantes son “gut microbiota” (96), “microbiota” (74), “cross-feeding” (52), “genome-scale metabolic model” (31) y “metabolic modeling” (31). **Aquí el modelamiento sí aparece vinculado a términos dietarios** : “flux balance analysis” y “genome-scale metabolic model” enlazan con “diet”, “dietary fiber” y “cross-feeding”. El contexto, sin embargo, es humano: “infant gut microbiota”, “human milk oligosaccharides”, “human gut microbiota”, “ulcerative colitis”, “parkinson's disease” y “cardiovascular disease”. **Solo 6 de 372 documentos (1,6 %) mencionan especies de producción animal.**

**Tabla 13. Dominio de aplicación de cada eje metodológico**

|**Eje**|**Ítems /**<br>**clústeres**|**Aplicación microbiana dominante**|**Documentos con**<br>**términos de**<br>**producción animal**|
|---|---|---|---|
|A · Grafos|52 / 13|Asociaciones microbio-enfermedad y<br>microbio-fármaco (humano)|0 de 168 (0 %)|
|B · Aprendizaje restringido|22 / 5|Microbiota de suelo y sistemas suelo-planta|0 de 36 (0 %)|
|D · Modelamiento<br>mecanístico|56 / 8|Microbioma intestinal humano y dieta|6 de 372 (1,6 %)|



_Elaboración Propia_

19

**Figura 5**

_Mapa de co-ocurrencia de palabras clave del autor del eje A (aprendizaje sobre grafos)_



<!-- Start of picture text -->
represetaon eating<br>readme<br>data<br>heterazenegus network<br>anita’ pptie<br>srophyocogs aur<br>srop cons network atibote<br>| weaiaetighen imkrobS erations<br>soph<br>aah comets rasta btte ie nelwork qprenndeanice~<br>oJ<br>o<br>microbe-dise@e gps6ciation, \eeesod mpage ,<br>vtarenner sch obey eyas Bkoepote<br>tontondechanism Goro<br>mutiview andimutimedsi net B°9PM atBbedsing<br>ms Shes<br>etabol@network sno epalaence<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21 sobre 168 documentos. Umbral mínimo de 2 ocurrencias (52 términos en 13 clústeres). El término “nutrition” aparece sin enlaces._

20

**Figura 6**

_Mapa de co-ocurrencia de palabras clave del autor del eje B (aprendizaje científicamente restringido)_



<!-- Start of picture text -->
physics-informed neural networ<br>artificial iftelligence<br>«<br>ordinary diffefential equation<br>soil microtjipta growth<br>@ my, 2 hysics-i<br>cae PY sics-infor:me néural networ<br>mec deep (@arningBJ machin@parning<br>hybridjmodel e<br>eneu@ ode?<br>neural @iptworks<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21 sobre 36 documentos. Umbral mínimo de 2 ocurrencias (22 términos en 5 clústeres). La única aplicación microbiana corresponde a microbiota de suelo._

21

##### **Figura 7**

_Mapa de co-ocurrencia de palabras clave del autor del eje D (modelamiento mecanístico)_



<!-- Start of picture text -->
eae Le<br>V crostiedine iden<br>gut rlerobitg, pate<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21 sobre 372 documentos. Umbral mínimo de 4 ocurrencias (56 términos en 8 clústeres)._

#### **4.9. Base intelectual (co-citación)**

El análisis de co-citación de referencias citadas (131 referencias, umbral de 20 citas) identificó **cinco clústeres** : nutrición porcina y ácidos grasos de cadena corta (40 referencias); herramientas de análisis y microbiota aviar (27); microbioma intestinal de aves y productividad (26); nutrición avícola y análisis estadístico (24); y procesamiento de secuencias (14).

**Tabla 14. Referencias más co-citadas**

|**Referencia (forma abreviada del mapa)**|**Co-citas**|**Clúster**|
|---|---|---|
|_Nutrient Requirements of Swine_(2012)|225|1|
|_Nutrient Requirements of Poultry_(1994)|158|4|
|Holmes S., phyloseq: an R package… (2013)|129|4|
|Salzberg S. L., FLASH: fast length adjustment… (2011)|113|5|
|Bäckhed F., From dietary fiber to host physiology… (2016)|110|1|
|Blanquet-Diot S., Gut microbiota dysbiosis in postweaning piglets…|103|1|
|Holmes S. P., DADA2: high-resolution sample inference… (2016)|100|2|
|Yu Z., Intestinal microbiome of poultry and its interaction with host and diet|80|3|
|Edgar R. C., UPARSE: highly accurate OTU sequences… (2013)|79|3|
|Huttenhower C., Metagenomic biomarker discovery and explanation (2011)|73|2|



_Elaboración Propia_

##### **Tres hallazgos cuantificados:**

**Ausencia total de referencias fundacionales de modelamiento.** Se filtraron las 131 referencias por términos de método ( _physics-informed_ , _neural network_ , _graph_ , _deep learning_ ,

22

_machine learning_ , _flux balance_ , _genome-scale_ , Lotka-Volterra, _neural ODE_ , _convolutional_ ). Las únicas coincidencias fueron phyloseq y ggplot2, ambas por contener la palabra _graphics_ en el título. **No se identificó ninguna referencia de modelamiento computacional en la base intelectual del campo.**

**Base intelectual consolidada y anterior al periodo analizado.** De las 129 referencias con año identificable, **125 (97 %) son anteriores a 2021** , con mediana en 2014 y rango entre 1990 y 2022. Este resultado sustenta empíricamente el criterio de excepción temporal declarado en la sección 3.4.

**Naturaleza de la base.** Las dos referencias más co-citadas son manuales normativos de requerimientos nutricionales (NRC) y la mayoría de las restantes son herramientas de secuenciación, ensamblaje, clasificación taxonómica y análisis estadístico descriptivo.

##### **Figura 8**

_Red de co-citación de referencias citadas (Scopus, 2021–2025)_



<!-- Start of picture text -->
nh<br>nihewsd<br>foals a<br>RE EN i hetoto<br>Hse SETS Ian<br>Sa ee ee<br>Re/) |<br>i<br><!-- End of picture text -->

_Nota. Elaboración propia con VOSviewer 1.6.21. Umbral mínimo de 20 co-citas (131 referencias en 5 clústeres). Ninguna referencia fundacional de modelamiento computacional alcanzó el umbral._

23

**Figura 9**

_Mapa de densidad de co-citación de referencias citadas_



_Nota. Elaboración propia con VOSviewer 1.6.21, mismos parámetros que la Figura 8._

#### **4.10. Cadena complementaria: gemelo digital**

Dado que ninguno de los cuatro ejes incorporó el término _digital twin_ , concepto central del proyecto, se ejecutaron dos cadenas complementarias en Scopus (Anexo A.8).

**La cadena E1 (gemelo digital y microbioma)** recuperó 33 registros, de los cuales 25 cumplieron los criterios de inclusión. Todos corresponden a salud humana o a sistemas ambientales —microbioma infantil y neurodesarrollo, eje intestino-cerebro, nutrición personalizada, medicación de precisión, sistemas suelo-planta y tratamiento de aguas—. **Ninguno aborda especies de producción animal.** El frente es marcadamente reciente: 21 de los 33 registros se publicaron en 2025.

**La cadena E2 (gemelo digital y ganadería)** recuperó 105 registros, de los cuales 82 cumplieron los criterios de inclusión. **Ninguno menciona microbioma ni microbiota** en su título, resumen o palabras clave. Los gemelos digitales identificados operan a escala de sistema productivo: instalaciones, manejo de praderas, condiciones ambientales, fenotipado y detección de lesiones. Tres documentos desarrollan gemelos digitales orientados a la nutrición animal, aunque sin incorporar la dimensión microbiana.

**Tabla 15. Cadenas complementarias de gemelo digital (Scopus, 2021–2025)**

|**Cadena**|**Registros brutos**|**Tras filtros**|**Con términos de**<br>**microbioma**|**Con especies de**<br>**producción**|
|---|---|---|---|---|
|E1 · Gemelo digital y<br>microbioma|33|25|25|0|
|E2 · Gemelo digital y<br>ganadería|105|82|0|Mayoritario|



_Elaboración Propia_

_Nota: los registros de las cadenas complementarias no se incorporan al corpus de 4.127 documentos ni a los mapas; constituyen una verificación independiente._

24

### **5. Síntesis cualitativa del estado del arte**

#### **5.1. Propósito y criterio de selección**

El análisis bibliométrico describe la estructura de la literatura a partir de sus metadatos, pero no el contenido de los trabajos. Esta sección complementa los resultados cuantitativos con una síntesis cualitativa de los documentos más pertinentes para el proyecto, con el fin de caracterizar qué hacen, con qué métodos y en qué dominio, y de precisar la distancia que separa cada frente del objetivo del proyecto.

Se seleccionaron 25 documentos según cuatro criterios: pertinencia simultánea a un frente metodológico y a sistemas microbianos o dietarios; pertenencia a la intersección C∩D, la única poblada; alto número de citas dentro de su eje; y proximidad al diseño del proyecto identificada en el documento _Antecedentes Generales_ (Área de Investigación PIA-2 Microbioma Digital, 2026). Dos documentos de 2026 (Aminian-Dehkordi et al., 2026; Thompson et al., 2026) quedan fuera de la ventana del análisis bibliométrico, pero dentro de la ventana 2021–2026 del protocolo del proyecto, y se incluyen por su proximidad metodológica. La síntesis se basa en los resúmenes y metadatos de los registros de Scopus; su profundización mediante lectura completa corresponde al cribado documental del proyecto.

#### **5.2. Aprendizaje sobre grafos aplicado a comunidades microbianas**

Las redes neuronales sobre grafos se consolidaron como herramienta de la bioinformática por su capacidad para procesar datos con estructura de red. En su revisión, Zhang et al. (2021) organizan sus aplicaciones en tres tareas —clasificación de nodos, predicción de enlaces y generación de grafos— y en tres dominios: predicción de enfermedades, descubrimiento de fármacos e imagenología biomédica. Los autores advierten que su desarrollo aún enfrenta desafíos en el procesamiento de datos de baja calidad, en la metodología y en la interpretabilidad. Esta orientación biomédica coincide con la dominante en el mapa del eje A (sección 4.8).

La línea más consolidada del eje A en el ámbito microbiano es la predicción de asociaciones entre microbios y enfermedades. Long et al. (2021) propusieron GATMDA, un marco que combina redes de atención sobre grafos con completación inductiva de matrices para predecir asociaciones microbio–enfermedad en humanos, a partir de características construidas con múltiples fuentes de datos biomédicos. Los autores justificaron el enfoque en que los métodos previos, basados en modelos lineales o en propagación de etiquetas, no capturan asociaciones no lineales y fallan ante enfermedades o microbios sin asociaciones observadas. En dos conjuntos de datos (HMDAD y Disbiome), el modelo superó a los métodos de referencia, y dos estudios de caso, asma y enfermedad inflamatoria intestinal, respaldaron su efectividad. Este tipo de trabajo trata el microbioma como un conjunto de entidades asociadas a fenotipos clínicos, sin representar su metabolismo ni su respuesta a la dieta.

En el plano microbiano, Andersen et al. (2025) desarrollaron un modelo basado en GNN que predice la dinámica de abundancia de especies a partir exclusivamente de datos históricos de abundancia relativa. Entrenado sobre series temporales de 24 plantas de tratamiento de aguas residuales de Dinamarca (4.709 muestras recogidas durante 3 a 8 años), el modelo anticipó la dinámica de las especies hasta diez puntos temporales hacia adelante. Los autores lo probaron también sobre un conjunto de datos de microbioma intestinal humano y lo proponen como aplicable a cualquier serie longitudinal microbiana. El trabajo demuestra que un grafo aprendido a partir de la co-variación temporal basta para pronosticar comunidades complejas, aunque no incorpora conocimiento mecanístico ni variables dietarias.

25

El antecedente más próximo a la arquitectura propuesta por el proyecto es SIMBA-GNN (Aminian-Dehkordi et al., 2026), que integra simulaciones metabólicas con un transformador de grafos que considera los atributos de las aristas. A partir de una cohorte humana con dieta alta en fibra, mapeada sobre redes metabólicas, sus autores ejecutaron miles de simulaciones por pares para inferir probabilidades de _cross-feeding_ , perfiles de actividad de rutas y similitud funcional entre microbios. Con esas señales construyeron un grafo global microbio–metabolito–ruta, sobre el cual un transformador de grafos heterogéneo aprende a predecir la presencia y la abundancia relativa de los microbios en cada individuo. SIMBA-GNN muestra que es factible utilizar la simulación mecanística como conocimiento previo de un grafo heterogéneo; su dominio, sin embargo, es el microbioma humano, y la dieta interviene como característica de la cohorte y no como variable manipulable.

#### **5.3. Aprendizaje científicamente restringido**

Los trabajos de este frente comparten una estrategia: incorporar ecuaciones conocidas del sistema al aprendizaje de una red neuronal para mejorar su interpretabilidad y su desempeño con pocos datos. En el ámbito del microbioma intestinal, Wang et al. (2023) propusieron mNODE, un predictor de perfiles metabolómicos a partir de la composición microbiana basado en ecuaciones diferenciales ordinarias neuronales. El método superó a las alternativas existentes en microbiomas humanos y ambientales, permitió incorporar información dietaria para mejorar la predicción en el microbioma intestinal humano y, mediante análisis de susceptibilidad, reveló interacciones microbio–metabolito. Los autores lo presentan como una herramienta para estudiar la relación microbioma–dieta–metaboloma con miras a la nutrición de precisión.

Thompson et al. (2026) desarrollaron el _neural species mediator_ , un modelo que combina un modelo mecanístico de la dinámica de metabolitos con un componente de aprendizaje automático. Parten de que la competencia y el _cross-feeding_ de metabolitos gobiernan la dinámica de las comunidades, y de que los modelos mecanísticos existentes son poco flexibles, mientras que los de aprendizaje automático requieren grandes volúmenes de datos, son difíciles de interpretar y tienden a sobreajustar el ruido experimental. Sobre datos experimentales _in vitro_ , el modelo híbrido superó a cada uno de sus componentes por separado en capacidad predictiva e interpretabilidad. PhyMicroNet (Lin et al., 2025) sigue una lógica análoga para inferir interacciones dirigidas entre especies: incorpora las ecuaciones generalizadas de Lotka-Volterra al aprendizaje para asegurar la plausibilidad ecológica de las interacciones estimadas. Validado con datos simulados y con datos reales de microbioma intestinal humano, superó a cuatro métodos de referencia y mantuvo mayor robustez ante datos escasos o ruidosos.

Fuera del intestino, las redes neuronales informadas por la física se han aplicado a la predicción del crecimiento de poblaciones microbianas del suelo en función de variables ambientales (Cuomo et al., 2025) y al control predictivo de la evolución de un microbioma en un reactor secuencial por lotes orientado a la producción de polihidroxialcanoatos, donde el contenido intracelular del polímero aumentó de 0,51 % a 16,5 % bajo el control del modelo (Catalão et al., 2025). Por su parte, Arroyo-Esquivel et al. (2024) evaluaron las ecuaciones diferenciales neuronales como herramienta de pronóstico de comunidades ecológicas simuladas: ofrecieron pronósticos más precisos que los modelos ARIMA y el mejor desempeño cuando la evaluación consideró intervalos de predicción, aunque fueron superadas por el modelado dinámico empírico en exactitud puntual. En conjunto, estos trabajos confirman que el aprendizaje restringido ya se aplica a comunidades microbianas, pero en sistemas humanos _in vitro_ , ambientales o de bioprocesos, sin variables de dieta animal ni fenotipos productivos.

26

#### **5.4. Modelamiento mecanístico de la relación dieta–microbioma**

Este frente se sostiene sobre un marco ecológico consolidado. Culp y Goodman (2023) revisan el _cross-feeding_ —el intercambio de metabolitos entre microbios— como una interacción que contribuye a formar comunidades intestinales estables, resistentes a la invasión y resilientes ante perturbaciones, y describen sus mecanismos a lo largo de los niveles tróficos, desde los fermentadores primarios hasta los consumidores de hidrógeno, incluido el intercambio de aminoácidos, vitaminas y cofactores. Bakkeren et al. (2025) plantean que la clave para identificar principios generales del microbioma reside en el metabolismo microbiano: los nutrientes disponibles determinan qué especies pueden persistir, y la competencia por ellos condiciona otros mecanismos, como la competencia bacteriana directa y el _cross-feeding_ . Los autores extienden explícitamente este enfoque al diseño de microbiomas en salud, agricultura y ambiente.

Este marco ya ha mostrado capacidad predictiva. Shi et al. (2025) sometieron comunidades _in vitro_ derivadas de heces humanas a 707 fármacos, en cerca de 5.000 condiciones, y encontraron que las respuestas composicionales y metabolómicas estaban moldeadas por la competencia por nutrientes, de forma consistente con las predicciones de un modelo consumidor-recurso. Marinos et al. (2024) mostraron primero que definir prebióticos consumidos exclusivamente por una especie objetivo no suele ser posible, por la superposición de nichos metabólicos, y luego utilizaron modelamiento metabólico para identificar prebióticos de precisión capaces de aumentar selectivamente una especie en una comunidad de dos miembros del microbioma de _Caenorhabditis elegans_ . Cuatro de los compuestos predichos se confirmaron experimentalmente y uno de ellos se validó _in vivo_ . Estos resultados son relevantes para el proyecto porque demuestran que un modelo metabólico puede traducirse en una decisión dietaria verificable, que es precisamente la función que se espera de un gemelo digital nutricional.

La dieta aparece como variable explícita del modelamiento en Koduru et al. (2022), quienes analizaron el crecimiento, la persistencia intestinal y la biosíntesis de posbióticos de seis bacterias ácido-lácticas, junto con sus interacciones con 15 bacterias intestinales bajo 11 regímenes dietarios, combinando multi-ómica y modelamiento _in silico_ . Las predicciones sobre persistencia e interacciones se confirmaron con abundancias del microbioma cecal y con experimentos en medio gastado. Los autores concluyeron que los atributos probióticos dependen tanto de la dieta como de la especie y que no pueden explicarse solo a partir del genoma; por ejemplo, las dietas altas en grasa y bajas en carbohidratos resultaron más probablemente perjudiciales para la mayoría de las bacterias estudiadas.

#### **5.5. Microbioma y nutrición en especies de producción**

La literatura sobre especies de producción se organiza en torno a problemas productivos concretos. Tang et al. (2022) describen cómo el estrés del destete —asociado a la separación de la madre y a los cambios de dieta y de ambiente— altera la morfología y la función del intestino delgado del lechón, deteriora la barrera intestinal y conduce a menor consumo de alimento, mayor incidencia de diarrea y retraso del crecimiento, y proponen ese conocimiento como base para estrategias nutricionales. Jha y Mishra (2021) revisan el papel de la fibra dietaria en aves, que pasó de considerarse un factor antinutricional a reconocerse por sus efectos sobre el desarrollo del tracto gastrointestinal, la fermentación y la microbiota; subrayan, no obstante, que la fuente, el tipo, la forma y el nivel de inclusión de la fibra determinan si esos beneficios se obtienen. Ambas revisiones ilustran el carácter predominantemente descriptivo del eje C: identifican relaciones entre dieta, microbiota y desempeño, pero no las formalizan en modelos predictivos.

Desde este mismo eje, algunas revisiones ya adoptan el marco ecológico del _cross-feeding_ . St-Pierre et al. (2023) examinan el destete temprano en cerdos —practicado en la industria entre las

27

dos y cuatro semanas de edad, frente a las 12 a 18 semanas del destete natural— y describen cómo el cambio abrupto de la leche a una dieta sólida altera la disponibilidad de sustratos y desencadena una cascada de sucesión microbiana, porque las comunidades intestinales dependen de relaciones de _cross-feeding_ . Durante esa transición la microbiota es inestable y propensa a la disbiosis. Los autores proponen identificar especies críticas del microbioma maduro para facilitar su establecimiento tras el destete, pero el trabajo es una revisión descriptiva y no formaliza esa dinámica en un modelo.

La intersección C∩D muestra que el modelamiento metabólico ya comenzó a aplicarse en aves. Plata et al. (2022) estudiaron el ciego de pollos alimentados con cuatro promotores de crecimiento antimicrobianos y, mediante modelamiento basado en restricciones de 25 géneros bacterianos centrales, asociaron el mayor desempeño con menores demandas de metabolitos para el crecimiento microbiano, lo que apunta a una alteración en el uso del nitrógeno; la metabolómica no dirigida resultó coherente con las predicciones del modelo. Al-Nijir et al. (2024) generaron modelos metabólicos a escala genómica de hongos probióticos y los simularon en comunidades microbianas intestinales de aves: el modelamiento se correlacionó con la producción de ácidos grasos de cadena corta, en especial en el ciego, y los efectos de los probióticos resultaron dependientes de la cepa, de la composición del microbioma residente y de la dieta del hospedero. Los autores advierten que sus resultados se basan en predicciones computacionales que requieren validación _in vivo_ . Finalmente, Utkina et al. (2025) construyeron 237 genomas ensamblados a partir de metagenomas de 33 ciegos de pollo y aplicaron modelamiento basado en restricciones; los perfiles de ácidos grasos de cadena corta simulados fueron en gran medida consistentes con los ensayos experimentales y confirmaron el papel de _Bacteroides fragilis_ como nodo metabólico central de la comunidad.

Estos tres trabajos constituyen los antecedentes animales más cercanos al proyecto identificados en el corpus. Comparten dos rasgos: emplean modelamiento mecanístico, no aprendizaje sobre grafos ni aprendizaje restringido, y abordan la dieta como condición de la simulación, no como variable a optimizar. El documento _Antecedentes Generales_ había identificado un patrón coincidente en rumiantes, con enfoques metagenómicos y estadísticos que no construyen un grafo explícito (Área de Investigación PIA-2 Microbioma Digital, 2026).

#### **5.6. Gemelos digitales**

Los gemelos digitales identificados por las cadenas complementarias se agrupan en dos líneas que no se intersectan. En microbioma humano, Balasubramanyam et al. (2025) proponen un gemelo digital del microbioma intestinal orientado a la medicación de precisión, que modela la dinámica de la microbiota, predice interacciones fármaco–microbio mediante bosques aleatorios y estima los cambios poblacionales mediante modelamiento matemático, con un ROC-AUC reportado de 0,97. Su componente predictivo es tabular y no incorpora grafos ni restricciones mecanísticas en el aprendizaje.

En producción animal, el gemelo digital opera a escala de granja o de rebaño. Raba et al. (2022) implementaron, en el marco del proyecto IoFEED, un gemelo digital basado en sensores que miden el inventario de alimento en aproximadamente 325 silos de granjas, con el fin de optimizar la logística de distribución del alimento mediante simulación y optimización. Brown-Brandl y Tao (2025) revisan la integración de datos en tiempo real con gemelos digitales —réplicas virtuales de animales, instalaciones y operaciones— como frontera de la ganadería de precisión. Rao y Neethirajan (2025), a partir de 122 estudios, describen arquitecturas de gemelos digitales para la nutrición de precisión del ganado lechero que combinan telemetría en tiempo real con simulaciones mecanísticas de fermentación y algoritmos de optimización de la formulación; entre los desafíos

28

pendientes, señalan la necesidad de integrar inteligencia artificial explicable con modelos de digestión biológicamente fundados.

En ninguno de estos trabajos el resumen ni las palabras clave mencionan el microbioma. El más cercano al proyecto, el de Rao y Neethirajan (2025), incorpora simulación mecanística de la fermentación, pero en ganado lechero, un rumiante, y sin que el microbioma figure como componente explícito del gemelo.

#### **5.7. Síntesis integradora**

La lectura conjunta permite precisar la brecha en términos operativos (Tabla 13). Cada componente del sistema que propone el proyecto tiene al menos un antecedente sólido: grafos heterogéneos informados por simulación metabólica (Aminian-Dehkordi et al., 2026), aprendizaje restringido por la dinámica de metabolitos (Thompson et al., 2026; Wang et al., 2023), modelamiento metabólico de comunidades del ciego de aves con la dieta como condición (Al-Nijir et al., 2024; Utkina et al., 2025) y gemelos digitales nutricionales en ganadería (Rao & Neethirajan, 2025). Sin embargo, estos antecedentes se distribuyen en dominios distintos: los métodos de aprendizaje, en microbioma humano, ambiental o de bioprocesos; el modelamiento metabólico animal, sin aprendizaje; y los gemelos digitales animales, sin microbioma.

**Tabla 16. Síntesis de los antecedentes más próximos al proyecto**

|**Trabajo**|**Método**|**Sistema**|**Rol de la dieta**|**Aporte al proyecto**|
|---|---|---|---|---|
|Aminian-Dehkordi et al.<br>(2026)|Transformador de grafos<br>heterogéneo con<br>simulación metabólica|Microbioma<br>intestinal humano|Característica de la<br>cohorte (alta en fibra)|_Referente de_<br>_arquitectura del grafo_|
|Andersen et al. (2025)|GNN sobre series de<br>abundancia|Plantas de<br>tratamiento de<br>aguas; intestino<br>humano|No incorporada|_Pronóstico temporal de_<br>_comunidades_|
|Wang et al. (2023)|Ecuaciones diferenciales<br>neuronales (mNODE)|Microbiomas<br>humanos y<br>ambientales|Información de<br>entrada adicional|_Predicción del_<br>_metaboloma desde la_<br>_composición_|
|Thompson et al. (2026)|Ecuación diferencial<br>neuronal con restricción<br>mecanística|Comunidades in<br>vitro|No mencionada en el<br>resumen|_Restricción por dinámica_<br>_de metabolitos_|
|Lin et al. (2025)|PINN con ecuaciones de<br>Lotka-Volterra|Intestino humano|No mencionada en el<br>resumen|_Inferencia de_<br>_interacciones dirigidas_|
|Shi et al. (2025)|Modelo<br>consumidor-recurso|Comunidades<br>humanas in vitro|No aplica (fármacos)|_Competencia por_<br>_nutrientes como marco_<br>_predictivo_|
|Marinos et al. (2024)|Modelamiento<br>metabólico|Microbioma de C.<br>elegans|Prebióticos<br>diseñados|_Del modelo a la decisión_<br>_dietaria_|
|Plata et al. (2022)|Modelamiento basado<br>en restricciones|Ciego de pollo|Promotores de<br>crecimiento en la<br>dieta|_Vínculo metabolismo_<br>_microbiano–desempeño_|
|Al-Nijir et al. (2024)|Modelos metabólicos a<br>escala genómica|Intestino de aves|Condición de la<br>simulación|_Efectos probióticos_<br>_dependientes de la dieta_|
|Utkina et al. (2025)|Modelamiento basado<br>en restricciones|Ciego de pollo|Contexto<br>(degradación de<br>fibra)|_Validación con AGCC_<br>_experimentales_|
|Balasubramanyam et<br>al. (2025)|Gemelo digital con<br>bosques aleatorios|Intestino humano|No aplica (fármacos)|_Concepto de gemelo del_<br>_microbioma_|



29

|**Trabajo**|**Método**|**Sistema**|**Rol de la dieta**|**Aporte al proyecto**|
|---|---|---|---|---|
|Rao y Neethirajan<br>(2025)|Gemelo digital con<br>simulación de<br>fermentación|Ganado lechero|Optimización de la<br>formulación|_Gemelo nutricional sin_<br>_microbioma_|



_Elaboración Propia_

De la lectura conjunta se desprenden tres observaciones para el diseño del proyecto. Primero, la combinación de simulación metabólica y aprendizaje sobre grafos ya demostró ser viable en microbioma humano, lo que sugiere que su traslado a aves o cerdos plantea principalmente desafíos de datos y de adaptación. Segundo, los modelos metabólicos del ciego de pollo reproducen perfiles de ácidos grasos de cadena corta consistentes con mediciones experimentales (Utkina et al., 2025), lo que ofrece una fuente de restricciones mecanísticas utilizable por el componente de aprendizaje restringido. Tercero, las advertencias de los propios autores —la interpretabilidad limitada de las GNN (Zhang et al., 2021) y la dependencia del contexto junto con la necesidad de validación _in vivo_ (Al-Nijir et al., 2024)— anticipan riesgos que el proyecto deberá abordar en su evaluación.

30

### **6. Discusión**

**Los tres frentes metodológicos existen, están activos y crecen, pero cada uno se aplica a un dominio distinto del que requiere el proyecto.** El eje A se aplica a asociaciones biomédicas humanas; el eje B, a microbiota de suelo y sistemas suelo-planta; el eje D, al microbioma intestinal humano en relación con la dieta. El eje C, por su parte, concentra el 86,3 % del corpus con metodologías descriptivas y asociativas. Los resultados bibliométricos coinciden con la formulación de la brecha del documento _Antecedentes Generales_ , pero la sustentan ahora sobre 4.127 documentos en lugar de diez fichas institucionales.

Establecido ese punto, cabe precisar la naturaleza de la separación observada. **La brecha no es de disponibilidad de métodos ni de datos, sino de transferencia entre comunidades.** Tres evidencias convergentes lo indican. Primero, las comunidades editoriales están mayoritariamente separadas: los ejes publican en revistas distintas, como _Poultry Science_ en producción animal frente a _Briefings in Bioinformatics_ en aprendizaje sobre grafos. Segundo, la co-citación muestra que ambas comunidades no comparten base intelectual: la literatura de microbioma y nutrición animal se apoya en manuales normativos y herramientas de secuenciación, sin ninguna referencia de modelamiento computacional. Tercero, los términos de caracterización ómica ocupan posiciones intermedias en el mapa global, lo que indica que **la capa de datos que un gemelo digital requiere ya se genera en especies de producción** ; lo ausente es la capa de modelamiento.

**Este último punto tiene consecuencias directas sobre la factibilidad del proyecto.** El eje D demuestra que modelar mecanísticamente la relación dieta–microbioma es una práctica establecida y de alto impacto (36,7 citas por documento, el mayor del estudio), y el eje A demuestra que el aprendizaje sobre grafos aplicado a sistemas microbianos es un frente maduro en el dominio biomédico. El aporte del proyecto no consiste en desarrollar técnicas nuevas, sino en trasladar y articular técnicas existentes hacia un dominio donde no han sido aplicadas. Las cadenas complementarias refuerzan esta lectura: el gemelo digital existe tanto en microbioma humano como en nutrición animal, pero en ninguno de los documentos identificados ambas dimensiones se integran. El aporte del proyecto consiste, por tanto, en incorporar la capa microbiana a un concepto que ya opera en producción animal.

A esa lectura de factibilidad se suma una consideración de oportunidad. **El ritmo de crecimiento sugiere una ventana temporal acotada.** Los ejes metodológicos crecen a tasas de 49,5 % y 80,0 % anual, frente a 16,4 % del eje C, y sus términos son los más recientes del mapa global. La intersección que hoy aparece vacía es un espacio en rápido movimiento; este punto debe entenderse como oportunidad y no como garantía de permanencia.

**En el plano regional, los resultados complementan el diagnóstico del consolidado.** Chile participa en la red de colaboración internacional (16 documentos, 15,1 citas por documento, cinco enlaces con España, Canadá, China, Francia y México), en posición periférica del bloque occidental. El estudio bibliométrico no contradice el hallazgo del consolidado sobre la separación entre microbioma humano y nutrición animal en las instituciones nacionales; lo sitúa en un contexto donde esa separación es también un rasgo de la literatura internacional.

31

### **7. Limitaciones**

**7.1. Cobertura de una sola base.** El análisis bibliométrico se realizó exclusivamente sobre Scopus, por lo que los resultados describen la literatura indexada en esa base. El control cruzado con Web of Science mostró una coincidencia del 88 % en el eje A, pero no se replicó en los demás ejes. Scopus presenta sesgos de cobertura documentados en función de la disciplina, el país de publicación y el idioma (Mongeon & Paul-Hus, 2016), lo que puede subrepresentar la producción regional latinoamericana. Tampoco indexa de forma sistemática preprints (arXiv, bioRxiv) ni todas las actas de conferencias de aprendizaje automático, canales en los que suelen publicarse primero los avances de los ejes A y B. Esta última limitación es la más relevante para la afirmación de ausencia en las intersecciones A∩C y B∩C.

**7.2. Sesgo temporal de las citas.** Los documentos de 2024 y 2025 disponen de menos tiempo de acumulación de citas, lo que subestima sistemáticamente su impacto. Esto afecta especialmente al eje B, cuya producción se concentra en 2025.

**7.3. Duplicados en el análisis de co-citación.** VOSviewer no unifica variantes de formato de una misma referencia. Se identificaron **23 casos de duplicación** , entre ellos DADA2 (tres variantes), phyloseq, UPARSE y FLASH. El conteo real de co-citas de esas obras es superior al que muestra el mapa.

**7.4. Variantes no unificadas en el eje B.** El mapa del eje B contiene un ítem aislado, “physics-informed neural networks (pinns)”, que corresponde a una variante del término central no cubierta por el tesauro. Con la corrección aplicada, el nodo central pasaría de 13 a 15 ocurrencias. Existen además otras variantes de baja frecuencia ( _bayesian physics-informed neural networks_ , _physics informed machine learning_ , _ph-pinns_ ).

**7.5. Ruido residual de la cadena C∩D.** La cadena de intersección C∩D incluyó el término _stoichiometric_ sin restricción al tracto gastrointestinal, lo que recuperó 11 registros de microbiota de suelo y manejo de purines sobre 29 totales. Las cifras reportadas en la sección 4.2 distinguen explícitamente ambos conjuntos.

**7.6. Decisiones subjetivas de normalización.** La construcción del tesauro implica juicios sobre qué términos son equivalentes. Las dos decisiones de mayor impacto se declaran en la sección 3.5.

**7.7. Documentos sin palabras clave del autor.** 275 documentos (6,7 % del corpus) carecen de palabras clave del autor y no aportan al análisis de co-ocurrencia. Los mapas reflejan la estructura conceptual del 93,3 % restante.

**7.8. Alcance de las afirmaciones de ausencia.** Todas las ausencias constatadas se limitan a

las fuentes y ecuaciones de búsqueda declaradas.

**7.9. Dependencia de las ecuaciones de búsqueda.** Los hallazgos de intersección dependen del vocabulario de las cadenas. Términos afines como _knowledge graph_ , _network-based model_ o _hybrid modeling_ no se incluyeron en los ejes, por lo que ampliar el vocabulario podría modificar los conteos. El concepto de gemelo digital, ausente de los cuatro ejes, se cubrió mediante dos cadenas complementarias (sección 4.10).

**7.10. Asignación de ejes por cadena de origen.** La pertenencia de cada documento a un eje se determinó por la cadena que lo recuperó, sin verificación manual individual. La cadena C∩D

32

evidenció un 38 % de falsos positivos (11 de 29), lo que sugiere un nivel de ruido no despreciable en la asignación.

**7.11. Impacto no normalizado por disciplina.** Los indicadores de citas comparan ejes pertenecientes a disciplinas con prácticas de citación distintas. El mayor impacto por documento del eje D refleja en parte la cultura de citación de la microbiología de sistemas, por lo que la comparación entre ejes debe interpretarse con cautela.

33

### **8. Conclusiones**

La literatura publicada entre 2021 y 2025 sobre los cuatro ejes de relevancia del proyecto ascendió a **4.127 documentos** en Scopus, con un desbalance marcado entre ellos: el 86,3 % correspondió a microbioma y dieta en producción animal, dominio en el que las metodologías empleadas fueron descriptivas y asociativas. Los tres ejes metodológicos reunieron, en conjunto, una fracción menor del corpus.

**No se identificó ningún documento que integrara el aprendizaje sobre grafos (eje A) o el aprendizaje científicamente restringido (eje B) con la producción animal (eje C)** en las fuentes y ecuaciones consultadas. La única intersección poblada fue C∩D, con 18 documentos gastrointestinales. Cada eje metodológico se aplicó, además, a un dominio distinto del requerido por el proyecto: biomedicina humana en el caso del eje A, microbiota de suelo en el del eje B y microbioma intestinal humano en el del eje D. Las cadenas complementarias mostraron que el gemelo digital se aplica al microbioma humano y a la producción animal, pero no se identificó ningún documento que integrara ambas dimensiones.

Los ejes metodológicos crecieron entre tres y cinco veces más rápido que el eje de producción animal, y sus términos resultaron los más recientes del mapa conceptual, lo que los caracterizó como frentes emergentes aún no transferidos. El análisis de co-citación mostró que las comunidades no compartieron base intelectual: ninguna referencia fundacional de modelamiento computacional alcanzó el umbral de co-citación y el 97 % de la base intelectual resultó anterior a 2021.

La capa de datos necesaria para un gemelo digital nutricional ya se generaba en especies de producción, como evidenció la posición intermedia de los términos de caracterización ómica en el mapa global; la brecha se ubicó, por tanto, en la capa de modelamiento y no en la de datos. En consecuencia, el aporte del proyecto se situó en la transferencia e integración de técnicas existentes hacia un dominio donde no habían sido aplicadas, y no en el desarrollo de técnicas nuevas.

34

### **9. Insumos que este documento habilita**

|**Destinatario**|**Artefacto que se deriva**|
|---|---|
|Documentación|Sección de estado del arte y justificación del anteproyecto, con sustento cuantitativo|
|Formulación verificable<br>de la brecha (Tabla 7)|Formulación verificable de la brecha (Tabla 4)|
|Desarrollo|Referencias de arquitecturas y precedentes metodológicos por eje (Tablas 10 y 13)|
|Desarrollo|Evidencia de disponibilidad de datos ómicos en especies de producción (sección 4.7)|
|Investigación|Corpus depurado y tesauro para futuras actualizaciones del barrido|
|Investigación|Referencias fundacionales identificadas por co-citación, para la excepción temporal|



_Elaboración Propia_

35

### **Anexo A — Ecuaciones de búsqueda por base**

#### **A.1 Scopus — bloque de filtros común**

```
AND PUBYEAR > 2020 AND PUBYEAR < 2026
```

```
AND ( LIMIT-TO ( DOCTYPE , "ar" ) OR LIMIT-TO ( DOCTYPE , "re" ) OR LIMIT-TO ( DOCTYPE , "cp" ) )
AND ( LIMIT-TO ( LANGUAGE , "English" ) OR LIMIT-TO ( LANGUAGE , "Spanish" ) OR LIMIT-TO (
LANGUAGE , "Portuguese" ) )
```

_Nota: las exportaciones se realizaron sin estos filtros en la interfaz; los filtros se aplicaron posteriormente mediante rutinas reproducibles en Python sobre los metadatos, con resultado equivalente._

#### **A.2 Scopus — Eje A: aprendizaje sobre grafos**

```
TITLE-ABS-KEY ( ( "graph neural network*" OR gnn OR gnns OR "graph convolutional network*"
  OR "graph attention network*" OR graphsage OR "heterogeneous graph*" OR "graph transformer*"
  OR "graph representation learning" OR "graph embedding*" OR "message passing neural network*" )
AND ( microbiome* OR microbiota OR microbial OR metagenom* OR "metabolic network*" OR "metabolic
model*" ) )
```

#### **A.3 Scopus — Eje B: aprendizaje científicamente restringido**

```
TITLE-ABS-KEY ( ( "physics-informed neural network*" OR "physics-informed machine learning"
  OR "physics-informed deep learning" OR pinn OR pinns OR "neural ode*"
  OR "neural ordinary differential equation*" OR "universal differential equation*"
  OR "scientific machine learning" OR "biologically-informed neural network*" )
AND ( microbi* OR "community dynamics" OR "lotka-volterra" OR "consumer-resource" ) )
```

#### **A.4 Scopus — Eje C: microbioma y dieta en especies de producción**

```
TITLE-ABS-KEY ( ( "gut microbio*" OR "intestinal microbio*" OR "gastrointestinal microbio*"
OR "cecal microbio*" OR "caecal microbio*" OR "ileal microbio*" OR "gut microflora" OR
"intestinal flora" )
AND ( poultry OR broiler* OR chicken* OR "laying hen*" OR swine OR pig OR pigs OR piglet*
  OR porcine OR sows OR monogastric* )
```

```
AND ( diet* OR "feed additive*" OR "feed efficiency" OR "feed conversion" OR "animal nutrition"
  OR "dietary supplement*" OR "growth performance" OR "average daily gain" ) )
```

#### **A.5 Scopus — Eje D: modelamiento mecanístico y estequiométrico**

```
TITLE-ABS-KEY ( ( "flux balance analysis" OR "genome-scale metabolic model*"
  OR "genome-scale metabolic reconstruction*" OR "constraint-based model*" OR "constraint-based
metabolic"
  OR stoichiometric OR "consumer-resource model*" OR "cross-feeding" OR "community metabolic
model*"
```

```
  OR "metabolic modeling" OR "metabolic modelling" )
AND ( gut OR intestin* OR gastrointestinal OR cecal OR caecal OR colonic OR rumen )
AND microbi* )
```

#### **A.6 Scopus — Cadenas de intersección**

##### **A∩C**

```
TITLE-ABS-KEY ( ( "graph neural network*" OR gnn OR gnns OR "graph convolutional network*"
  OR "graph attention network*" OR graphsage OR "heterogeneous graph*" OR "graph transformer*" )
AND ( microbiome* OR microbiota )
```

```
AND ( poultry OR broiler* OR chicken* OR swine OR pig OR pigs OR piglet* OR porcine
  OR livestock OR monogastric* OR "animal nutrition" OR "farm animal*" ) )
```

##### **B∩C**

```
TITLE-ABS-KEY ( ( "physics-informed" OR pinn OR pinns OR "neural ode*"
  OR "neural ordinary differential equation*" OR "universal differential equation*"
  OR "scientific machine learning" OR "constrained neural network*" )
AND ( gut OR intestin* OR gastrointestinal OR cecal OR caecal OR microbio* )
```

36

```
AND ( poultry OR broiler* OR chicken* OR swine OR pig OR pigs OR piglet* OR porcine
  OR livestock OR monogastric* ) )
```

##### **C∩D**

```
TITLE-ABS-KEY ( ( "flux balance analysis" OR "genome-scale metabolic model*" OR "constraint-based
model*"
  OR stoichiometric OR "consumer-resource model*" OR "cross-feeding" OR "community metabolic
model*"
  OR "metabolic modeling" OR "metabolic modelling" )
AND ( microbiome* OR microbiota OR microbial )
AND ( poultry OR broiler* OR chicken* OR swine OR pig OR pigs OR piglet* OR porcine OR
monogastric* ) )
```

#### **A.7 Otras bases (cribado documental, no bibliométrico)**

##### **Web of Science — Eje A**

```
TS=( ( "graph neural network*" OR gnn OR gnns OR "graph convolutional network*"
  OR "graph attention network*" OR graphsage OR "heterogeneous graph*" OR "graph transformer*"
  OR "graph representation learning" OR "graph embedding*" OR "message passing neural network*" )
AND ( microbiome* OR microbiota OR microbial OR metagenom* OR "metabolic network*" OR "metabolic
model*" ) )
AND PY=(2021-2025)
AND LA=(English OR Spanish OR Portuguese)
AND DT=(Article OR Review OR "Proceedings Paper")
```

##### **PubMed — Eje C**

```
("gut microbio*"[tiab] OR "intestinal microbio*"[tiab] OR "cecal microbio*"[tiab] OR "caecal
microbio*"[tiab]
  OR "Gastrointestinal Microbiome"[Mesh])
AND (poultry[tiab] OR broiler*[tiab] OR chicken*[tiab] OR swine[tiab] OR pig[tiab] OR pigs[tiab]
  OR piglet*[tiab] OR porcine[tiab] OR monogastric*[tiab] OR "Swine"[Mesh] OR "Chickens"[Mesh] OR
"Poultry"[Mesh])
AND (diet*[tiab] OR "feed additive*"[tiab] OR "feed efficiency"[tiab] OR "growth
performance"[tiab]
  OR "Animal Feed"[Mesh] OR "Diet"[Mesh])
```

##### **PubMed — Eje D**

```
("flux balance analysis"[tiab] OR "genome-scale metabolic model*"[tiab] OR "constraint-based
model*"[tiab]
  OR stoichiometric[tiab] OR "consumer-resource model*"[tiab] OR "cross-feeding"[tiab]
OR "community metabolic model*"[tiab] OR "metabolic modeling"[tiab] OR "metabolic
modelling"[tiab])
AND (gut[tiab] OR intestin*[tiab] OR gastrointestinal[tiab] OR cecal[tiab] OR "Gastrointestinal
Microbiome"[Mesh])
```

**IEEE Xplore — Eje A** ( _Command Search_ , filtro de años en la interfaz)

```
("All Metadata":"graph neural network" OR "All Metadata":"graph neural networks" OR "All
Metadata":GNN
 OR "All Metadata":"graph convolutional network" OR "All Metadata":"graph attention network"
 OR "All Metadata":GraphSAGE)
AND ("All Metadata":microbiome OR "All Metadata":microbiota OR "All Metadata":microbial OR "All
Metadata":metagenomic)
```

**ScienceDirect — Eje B** (dividido por el límite de 8 operadores booleanos por campo; sin comodines)

```
B1: ("physics-informed neural network" OR "physics-informed machine learning" OR PINN OR "neural
ODE"
    OR "neural ordinary differential equation") AND (microbial OR microbiome OR microbiota)
B2: ("scientific machine learning" OR "universal differential equation" OR "biologically-informed
neural
    network") AND (microbial OR microbiome OR microbiota OR "community dynamics")
```

37

```
B3: ("Lotka-Volterra" OR "consumer-resource") AND ("neural network" OR "machine learning" OR
"deep
```

```
    learning") AND (microbial OR microbiome)
```

##### **SciELO — Eje C regional** (todos los índices, sin filtro de año)

```
(microbiota OR microbioma OR microbiome) AND (frango$ OR pollo$ OR broiler$ OR poultry OR suinos
OR suínos OR cerdo$ OR porcino$ OR swine OR leitoes OR leitões OR lechon$)
```

_Nota: el bloque de dieta se omitió en SciELO porque la combinación de comillas con truncamiento devolvía cero resultados; el criterio dietario se aplicó en el cribado manual, según el eje C._

#### **A.8 Scopus — Cadenas complementarias de gemelo digital**

##### **E1 · Gemelo digital y microbioma**

```
TITLE-ABS-KEY ( "digital twin*" AND ( "gut microbio*" OR "intestinal microbio*"
  OR microbiome* OR microbiota ) )
AND PUBYEAR > 2020 AND PUBYEAR < 2026
```

##### **E2 · Gemelo digital y ganadería**

```
TITLE-ABS-KEY ( "digital twin*" AND ( livestock OR poultry OR broiler* OR chicken*
  OR swine OR pig OR pigs OR "animal nutrition" OR "precision livestock" ) )
AND PUBYEAR > 2020 AND PUBYEAR < 2026
```

38

### **Anexo B — Registro de búsquedas**

**Tabla B.1. Registro de ejecuciones (fecha de búsqueda: 19-09-2026)**

|**Base**|**Cadena**|**Registros brutos**|**Tras filtros**<br>**2021–2025**|**Uso**|
|---|---|---|---|---|
|Scopus|Exploratoria (sin<br>idioma)|635|—|Fase exploratoria|
|Scopus|Exploratoria (inglés)|634|484 con modelamiento<br>explícito|Fase exploratoria|
|Scopus|Eje A|291|168|Bibliométrico|
|Scopus|Eje B|74|36|Bibliométrico|
|Scopus|Eje C|6.908|3.560|Bibliométrico|
|Scopus|Eje D|807|372|Bibliométrico|
|Scopus|A∩C|**0**|**0**|Verificación de brecha|
|Scopus|B∩C|1 (año 2026)|**0**|Verificación de brecha|
|Scopus|C∩D|64|29 (18<br>gastrointestinales)|Verificación de brecha|
|Scopus|E1 · Gemelo digital y<br>microbioma|33|25|Verificación<br>complementaria|
|Scopus|E2 · Gemelo digital y<br>ganadería|**105**|**82**|Verificación<br>complementaria|
|Web of Science|Eje A|187|—|Control cruzado (88 %<br>de coincidencia)|
|PubMed|Eje C|2.564|2.474|Cribado documental|
|PubMed|Eje D|463|335|Cribado documental|
|IEEE Xplore|Eje A|64|52|Cribado documental|
|ScienceDirect|B1|4|—|Cribado documental<br>(resultados no<br>pertinentes)|
|ScienceDirect|B2|**0**|—|Cribado documental|
|ScienceDirect|B3|2|—|Cribado documental|
|SciELO|Eje C regional|162 (sin filtro de año)|59|Cribado documental|
|ACM Digital Library|Eje A|Sin exportación<br>masiva|—|Registro por conteo en<br>pantalla|
|Redalyc|Consultas simples|Sin exportación<br>masiva|—|Registro por conteo en<br>pantalla|
|Google Scholar|Verificación de<br>cobertura|Sin exportación<br>masiva<br>_Elaboración Propia_|—|Búsqueda hacia<br>adelante y hacia atrás|



_Nota: los cuatro resultados de ScienceDirect B1 no guardan relación temática con la cadena, lo que indica que la búsqueda no se ejecutó en el campo previsto. Se registran por transparencia; el eje B queda cubierto por Scopus._

39

### **Anexo C — Tablas de datos detalladas**

##### **C.1 Documentos más citados por eje**

|**Eje**|**Citas**|**Año**|**Documento**|**Fuente**|
|---|---|---|---|---|
|A|462|2021|Graph Neural Networks and Their Current Applications in<br>Bioinformatics|_Frontiers in Genetics_|
|A|399|2024|Discovery of a structural class of antibiotics with explainable<br>deep learning|_Nature_|
|A|201|2021|Application of deep learning methods in biological networks|_Briefings in Bioinformatics_|
|B|164|2024|KAN-ODEs: Kolmogorov–Arnold network ordinary<br>differential equations|_Computer Methods in Applied_<br>_Mechanics and Engineering_|
|B|51|2023|Predicting metabolomic profiles from microbial composition<br>through neural ordinary differential equations|_Nature Machine Intelligence_|
|C|375|2022|Weaning stress and intestinal health of piglets: A review|_Frontiers in Immunology_|
|C|319|2021|Dietary fiber in poultry nutrition and their effects on nutrient<br>utilization, performance…|_Journal of Animal Science and_<br>_Biotechnology_|
|D|700|2021|Short chain fatty acids and its producing organisms: An<br>overlooked therapy for IBD?|_EBioMedicine_|
|D|444|2023|Cross-feeding in the gut microbiome: Ecology and<br>mechanisms|_Cell Host & Microbe_|



_Elaboración Propia_

_Nota: el documento del eje D sobre Bacillus velezensis en rizosfera vegetal (430 citas), recuperado por la cadena D, corresponde a ruido temático y se excluye de esta tabla._

_Nota de interés para el proyecto: el documento de Nature Machine Intelligence (2023) sobre predicción de perfiles metabolómicos mediante neural ODE es el antecedente más próximo al componente B del proyecto identificado en el corpus._

##### **C.2 Clústeres del mapa del eje A (52 términos, 13 clústeres)**

|**Clúster**|**Ítems**|**Términos representativos**|
|---|---|---|
|1|9|microbe-disease association, graph convolutional network, attention mechanism, microbe-drug<br>association|
|2|8|microbiota, bioinformatics, link prediction, graph representation learning, soil microbiome|
|3|6|antimicrobial peptide, staphylococcus aureus, antibiotic, heterogeneous network|
|4|5|graph neural network, deep learning, biological networks, protein language model|
|5|5|machine learning, gut microbiota, microbial interactions, microbial ecology|
|6|4|classification, graph embedding, metabolic network|
|7|3|artificial intelligence, multi-omics, metabolism|
|8|3|graph attention network, graph convolutional neural networks|
|9–13|9|metagenomic data, mutual information, phage–host interaction, representation learning,<br>sars-cov-2, metagenomics, viral identification, heterogeneous graph,**nutrition (0 enlaces)**|



_Elaboración Propia_

40

##### **C.3 Clústeres del mapa del eje B (22 términos, 5 clústeres)**

|**Clúster**|**Ítems**|**Términos**|
|---|---|---|
|1|7|machine learning, neural ode, neural networks, scientific machine learning, dynamical systems,<br>lotka-volterra system, time series|
|2|6|soil microbiota growth, am fungi, arbuscular mycorrhizal fungi, pde, numerical methods, biology|
|3|5|physics-informed neural network, deep learning, artificial neural network, hybrid model, microbial<br>fermentation|
|4|3|artificial intelligence, ordinary differential equation, uncertainty quantification|
|5|1|physics-informed neural networks (pinns) —**ítem aislado, 0 enlaces**|



_Elaboración Propia_

##### **C.4 Clústeres del mapa del eje D (56 términos, 8 clústeres)**

|**Clúster**|**Ítems**|**Términos representativos**|
|---|---|---|
|1|13|microbiota, metabolic modeling, metagenomics, constraint-based modeling, microbial<br>interactions, multi-omics, inflammatory bowel disease|
|2|10|bifidobacterium, prebiotic, bifidobacteria, human milk oligosaccharides, infant gut microbiota,<br>bacteroides|
|3|9|genome-scale metabolic model, flux balance analysis, systems biology, machine learning, diet,<br>metabolic network, parkinson's disease|
|4|6|dietary fiber, pectin, human gut microbiota, carbohydrate-active enzymes, mucin, cross-feeding<br>interactions|
|5|6|probiotic, akkermansia muciniphila, intestinal barrier, polysaccharides, metabolic interaction,<br>inflammation|
|6|6|gut microbiota, cross-feeding, short-chain fatty acid, butyrate, lactate, resistant starch|
|7|4|metabolomics, bile acids, clostridioides difficile, microbial metabolism|
|8|2|metabolism, fermentation|



_Elaboración Propia_

##### **C.5 Enlaces de colaboración más intensos entre países**

|**Par de países**||**Fuerza de enlace (fraccional)**|
|---|---|---|
|China – Estados Unidos||75,0|
|Egipto – Arabia Saudita||40,4|
|China – Pakistán||34,1|
|Bélgica – China||34,0|
|China – Corea del Sur||25,3|
|Canadá – Estados Unidos||22,5|
||_Elaboración Propia_||



##### **C.6 Participación de Chile**

|**Indicador**||**Valor**|
|---|---|---|
|Documentos|16||
|Citas totales|241||



41

|**Indicador**|**Valor**|
|---|---|
|Citas por documento|15,1|
|Enlaces de colaboración|5|
|Socios (fuerza de enlace)|España (3,5), Canadá (1,5), China (1,0), Francia (1,0), México<br>(1,0)|
|Clúster|Bloque occidental|



_Elaboración Propia_

42

### **Referencias**

- Al-Nijir, M., Chuck, C. J., Bedford, M. R., & Henk, D. A. (2024). Metabolic modelling uncovers the complex interplay between fungal probiotics, poultry microbiomes, and diet. _Microbiome, 12_ (1), Artículo 267. https://doi.org/10.1186/s40168-024-01970-2

- Aminian-Dehkordi, J., Parsa, M., Dickson, A., & Mofrad, M. R. K. (2026). SIMBA-GNN: Mechanistic graph learning for microbiome prediction. _npj Systems Biology and Applications, 12_ (1), Artículo 8. https://doi.org/10.1038/s41540-025-00631-w

- Andersen, K. S., Zhao, K., Agerskov, A. D. L., Sørensen, C. B., Holmager, T. J., Nierychlo, M., Peces, M., Guo, C., & Nielsen, P. H. (2025). Predicting microbial community structure and temporal dynamics by using graph neural network models. _Nature Communications, 16_ (1), Artículo 9124. https://doi.org/10.1038/s41467-025-64175-7

- Área de Investigación PIA-2 Microbioma Digital. (2026). _Antecedentes generales: Consolidado de la Actividad 6_ [Documento interno no publicado]. Universidad Tecnológica Metropolitana.

- Arroyo-Esquivel, J., Klausmeier, C. A., & Litchman, E. (2024). Using neural ordinary differential equations to predict complex ecological dynamics from population density data. _Journal of the Royal Society Interface, 21_ (214), Artículo 20230604. https://doi.org/10.1098/rsif.2023.0604

- Bakkeren, E., Piskovsky, V., & Foster, K. R. (2025). Metabolic ecology of microbiomes: Nutrient competition, host benefits, and community engineering. _Cell Host & Microbe, 33_ (6), 790–807. https://doi.org/10.1016/j.chom.2025.05.013

- Balasubramanyam, A., Balasubramani, Y., Jain, U. D., Shekar, H., Yangala, N., & Honnavalli, P. B. (2025). Modelling a digital twin of the human gut microbiome towards precision medication: A data driven approach. En _Proceedings of the 2025 IEEE 13th International Conference on Healthcare Informatics (ICHI)_ (pp. 490–500). IEEE. https://doi.org/10.1109/ICHI64645.2025.00063

- Brown-Brandl, T. M., & Tao, J. (2025). ASAS-NANP Symposium: Mathematical modeling in animal nutrition: Harnessing real-time data and digital twins for precision livestock farming. _Journal of Animal Science, 103_ , Artículo skaf138. https://doi.org/10.1093/jas/skaf138

- Catalão, M., Pinto, J., Torres, C. A. V., Freitas, F., Reis, M. A. M., Costa, R. S., & Oliveira, R. (2025). Bioprocess model-predictive control with physics-informed neural networks: Driving microbiome evolution toward high polyhydroxyalkanoates production capacity. _Journal of Process Control, 156_ , Artículo 103594. https://doi.org/10.1016/j.jprocont.2025.103594

- Culp, E. J., & Goodman, A. L. (2023). Cross-feeding in the gut microbiome: Ecology and mechanisms. _Cell Host & Microbe, 31_ (4), 485–499. https://doi.org/10.1016/j.chom.2023.03.016

- Cuomo, S., De Rosa, M., Piccialli, F., Pompameo, L., & Vocca, V. (2025). A numerical approach for soil microbiota growth prediction through physics-informed neural network. _Applied Numerical Mathematics, 207_ , 97–110. https://doi.org/10.1016/j.apnum.2024.08.025

- Donthu, N., Kumar, S., Mukherjee, D., Pandey, N., & Lim, W. M. (2021). How to conduct a bibliometric analysis: An overview and guidelines. _Journal of Business Research, 133_ , 285–296. https://doi.org/10.1016/j.jbusres.2021.04.070

- Gusenbauer, M., & Haddaway, N. R. (2020). Which academic search systems are suitable for systematic reviews or meta-analyses? Evaluating retrieval qualities of Google Scholar, PubMed, and 26 other resources. _Research Synthesis Methods, 11_ (2), 181–217. https://doi.org/10.1002/jrsm.1378

- Hirsch, J. E. (2005). An index to quantify an individual's scientific research output. _Proceedings of the National Academy of Sciences, 102_ (46), 16569–16572. https://doi.org/10.1073/pnas.0507655102

43

- Jha, R., & Mishra, P. (2021). Dietary fiber in poultry nutrition and their effects on nutrient utilization, performance, gut health, and on the environment: A review. _Journal of Animal Science and Biotechnology, 12_ (1), Artículo 51. https://doi.org/10.1186/s40104-021-00576-0

- Koduru, L., Lakshmanan, M., Lee, Y. Q., Ho, P.-L., Lim, P.-Y., Ler, W. X., Ng, S. K., Kim, D., Park, D.-S., Banu, M., Ow, D. S. W., & Lee, D.-Y. (2022). Systematic evaluation of genome-wide metabolic landscapes in lactic acid bacteria reveals diet- and strain-specific probiotic idiosyncrasies. _Cell Reports, 41_ (10), Artículo 111735. https://doi.org/10.1016/j.celrep.2022.111735

- Lin, B., Deng, T., Huang, X., & Wang, Y. (2025). PhyMicroNet: Inferring directed species interactions in microbiomes from longitudinal abundance data using physics-informed neural networks. En _Proceedings of the 2025 IEEE International Conference on Bioinformatics and Biomedicine (BIBM)_ (pp. 312–317). IEEE. https://doi.org/10.1109/BIBM66473.2025.11356920

- Long, Y., Luo, J., Zhang, Y., & Xia, Y. (2021). Predicting human microbe-disease associations via graph attention networks with inductive matrix completion. _Briefings in Bioinformatics, 22_ (3), Artículo bbaa146. https://doi.org/10.1093/bib/bbaa146

- Marinos, G., Hamerich, I. K., Debray, R., Obeng, N., Petersen, C., Taubenheim, J., Zimmermann, J., Blackburn, D., Samuel, B. S., Dierking, K., Franke, A., Laudes, M., Waschina, S., Schulenburg, H., & Kaleta, C. (2024). Metabolic model predictions enable targeted microbiome manipulation through precision prebiotics. _Microbiology Spectrum, 12_ (2). https://doi.org/10.1128/spectrum.01144-23

- Mongeon, P., & Paul-Hus, A. (2016). The journal coverage of Web of Science and Scopus: A comparative analysis. _Scientometrics, 106_ (1), 213–228. https://doi.org/10.1007/s11192-015-1765-5

- Page, M. J., McKenzie, J. E., Bossuyt, P. M., Boutron, I., Hoffmann, T. C., Mulrow, C. D., Shamseer, L., Tetzlaff, J. M., Akl, E. A., Brennan, S. E., Chou, R., Glanville, J., Grimshaw, J. M., Hróbjartsson, A., Lalu, M. M., Li, T., Loder, E. W., Mayo-Wilson, E., McDonald, S., … Moher, D. (2021). The PRISMA 2020 statement: An updated guideline for reporting systematic reviews. _BMJ, 372_ , n71. https://doi.org/10.1136/bmj.n71

- Plata, G., Baxter, N. T., Susanti, D., Volland-Munson, A., Gangaiah, D., Nagireddy, A., Mane, S. P., Balakuntla, J., Hawkins, T. B., & Kumar Mahajan, A. (2022). Growth promotion and antibiotic induced metabolic shifts in the chicken gut microbiome. _Communications Biology, 5_ (1), Artículo 293. https://doi.org/10.1038/s42003-022-03239-6

- Raba, D., Tordecilla, R. D., Copado, P., Juan, A. A., & Mount, D. (2022). A digital twin for decision making on livestock feeding. _INFORMS Journal on Applied Analytics, 52_ (3), 267–282. https://doi.org/10.1287/inte.2021.1110

- Rao, S., & Neethirajan, S. (2025). Computational architectures for precision dairy nutrition digital twins: A technical review and implementation framework. _Sensors, 25_ (16), Artículo 4899. https://doi.org/10.3390/s25164899

- Shi, H., Newton, D. P., Nguyen, T. H., Estrela, S., Sanchez, J., Tu, M., Ho, P.-Y., Zeng, Q., DeFelice, B. C., Sonnenburg, J. L., & Huang, K. C. (2025). Nutrient competition predicts gut microbiome restructuring under drug perturbations. _Cell, 188_ (24), 6971–6986.e14. https://doi.org/10.1016/j.cell.2025.10.038

- St-Pierre, B., Perez Palencia, J. Y., & Samuel, R. S. (2023). Impact of early weaning on development of the swine gut microbiome. _Microorganisms, 11_ (7), Artículo 1753. https://doi.org/10.3390/microorganisms11071753

- Tang, X., Xiong, K., Fang, R., & Li, M. (2022). Weaning stress and intestinal health of piglets: A review. _Frontiers in Immunology, 13_ , Artículo 1042778. https://doi.org/10.3389/fimmu.2022.1042778

44

- Thompson, J., Connors, B. M., Zavala, V. M., & Venturelli, O. S. (2026). Physics-constrained neural ordinary differential equation models to discover and predict microbial community dynamics. _Proceedings of the National Academy of Sciences, 123_ (13), Artículo e2517661123. https://doi.org/10.1073/pnas.2517661123

- Utkina, I., Fan, Y., Willing, B. P., & Parkinson, J. (2025). Metabolic modeling of microbial communities in the chicken ceca reveals a landscape of competition and co-operation. _Microbiome, 13_ (1), Artículo 248. https://doi.org/10.1186/s40168-025-02241-4

- van Eck, N. J., & Waltman, L. (2010). Software survey: VOSviewer, a computer program for bibliometric mapping. _Scientometrics, 84_ (2), 523–538. https://doi.org/10.1007/s11192-009-0146-3

- Wang, T., Wang, X.-W., Lee-Sarwar, K. A., Litonjua, A. A., Weiss, S. T., Sun, Y., Maslov, S., & Liu, Y.-Y. (2023). Predicting metabolomic profiles from microbial composition through neural ordinary differential equations. _Nature Machine Intelligence, 5_ (3), 284–293. https://doi.org/10.1038/s42256-023-00627-3

- Zhang, X.-M., Liang, L., Liu, L., & Tang, M.-J. (2021). Graph neural networks and their current applications in bioinformatics. _Frontiers in Genetics, 12_ , Artículo 690049. https://doi.org/10.3389/fgene.2021.690049

- Zupic, I., & Čater, T. (2015). Bibliometric methods in management and organization. _Organizational Research Methods, 18_ (3), 429–472. https://doi.org/10.1177/1094428114562629

_Estudio bibliométrico elaborado por el Área de Investigación · PIA-2 Microbioma Digital · Sección 302 · UTEM ·_

_2026-II_

_Búsquedas ejecutadas el 19-09-2026 · Documento generado el 21-09-2026_

45
