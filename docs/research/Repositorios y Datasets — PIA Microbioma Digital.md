

<!-- Start of picture text -->
Microbions og)<br><!-- End of picture text -->

## **Microbioma Digital**



<!-- Start of picture text -->
Gemelo Digital Nutricional · GNN + PINNs<br>PIA-2 · Sección 302 · Gestión de Proyectos Informáticos · UTEM · 2026-II<br>Paleta de Colores del proyecto:<br>#25A3A8 #0E9987 #087F9E #0767A0 #032E54<br><!-- End of picture text -->

# **Revisión de repositorios y selección de datasets**

**PIA-2 · Microbioma Digital - Gemelo Digital Nutricional basado en GNN y PINNs**

**Actividades 15 y 19: Búsqueda, selección y clasificación de datasets públicos, y revisión de repositorios de metabolómica y microbioma animal (09-09-2026 — 16-09-2026)**

_Documento final del área de Investigación · Repositorios y datasets_

**Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II**

**Área de Investigación · Sublíder Vicente Fuentes Rodríguez**

**Profesor Eduardo Osorio Venegas**

Versión Final · 21-09-2026

### **Índice**

|**1. Alcance y objetivo**|**3**|
|---|---|
|**2. Datos que requiere el proyecto y criterios de evaluación**|**4**|
|**3. Revisión de repositorios (Actividad 19)**|**5**|
|3.1. Repositorios de secuencias|5|
|3.2. Catálogos de genomas microbianos|5|
|3.3. Repositorios de metabolómica|5|
|3.4. Portales multiómicos integrados|5|
|3.5. Recursos de conocimiento metabólico y composición de dietas|6|
|**4. Conjuntos de datos seleccionados (Actividad 15)**|**7**|
|4.1. Nivel A: conjuntos núcleo|7|
|4.2. Nivel B: catálogos de referencia|8|
|4.3. Nivel C: conjuntos complementarios|8|
|**5. Brechas de datos identificadas**|**9**|
|**6. Recomendaciones para Desarrollo**|**10**|
|**7. Limitaciones**|**11**|
|**Referencias**|**12**|



2

|**Índice de tablas**||
|---|---|
|**Tabla 1. Tipos de datos requeridos por el gemelo digital**|**4**|
|**Tabla 2. Criterios de evaluación y selección**|**4**|
|**Tabla 3. Repositorios y recursos revisados**|**6**|
|**Tabla 4. Conjuntos de datos seleccionados y su clasificación**|**7**|
|**Tabla 5. Correspondencia propuesta entre fuentes y tipos de nodo**|**10**|



3

### **1. Alcance y objetivo**

Este documento reporta dos actividades del área de Investigación del proyecto Microbioma Digital: la revisión de repositorios de metabolómica y microbioma animal (Actividad 19) y la búsqueda, selección y clasificación de conjuntos de datos públicos (Actividad 15). Ambas se presentan en un mismo documento porque son secuenciales: primero se identifican los repositorios donde se depositan los datos de interés y luego se seleccionan, dentro de ellos, los conjuntos de datos concretos que el proyecto puede utilizar.

El punto de partida es el _Estudio Bibliométrico_ del área (Actividad 13), que concluyó que la capa de datos necesaria para un gemelo digital nutricional ya se genera en especies de producción, mientras que la brecha se ubica en la capa de modelamiento. Este documento operacionaliza esa conclusión: identifica qué datos existen, dónde están y cuáles son aptos para alimentar el grafo heterogéneo del proyecto. En particular, se priorizaron los conjuntos de datos asociados a los antecedentes animales más cercanos identificados en la síntesis cualitativa del estudio (Plata et al., 2022; Utkina et al., 2025).

**Objetivo general.** Identificar y clasificar repositorios y conjuntos de datos públicos de microbioma gastrointestinal, metabolómica y composición de dietas en especies monogástricas de producción, útiles para construir y validar el gemelo digital del proyecto.

4

### **2. Datos que requiere el proyecto y criterios de evaluación**

El gemelo digital propuesto representa el tracto gastrointestinal como un grafo heterogéneo sobre el cual se aprende con redes neuronales de grafos y se imponen restricciones metabólicas. Para ello requiere cinco tipos de datos, que determinan los criterios de evaluación de repositorios y conjuntos de datos (Tabla 1).

**Tabla 1. Tipos de datos requeridos por el gemelo digital**

|**Tipo de dato**|**Contenido**|**Uso en el proyecto**|
|---|---|---|
|Composición microbiana|Metagenomas shotgun o secuenciación del gen 16S<br>rRNA de contenido intestinal|Nodos de taxón y su abundancia|
|Genomas y funciones|Genomas ensamblados desde metagenomas (MAG),<br>catálogos de genes, anotación funcional|Nodos de función metabólica y<br>capacidades de cada taxón|
|Metaboloma|Perfiles de metabolitos de contenido intestinal o suero<br>(RMN, espectrometría de masas)|Nodos de metabolito; validación de<br>predicciones|
|Dieta|Composición del alimento y aditivos, idealmente<br>cuantificada|Nodos de dieta; variable manipulable del<br>gemelo|
|Fenotipo productivo|Ganancia de peso, conversión alimenticia, eficiencia<br>digestiva|Variable respuesta del modelo|
||_Elaboración Propia_||



A partir de esos requerimientos se definieron siete criterios de evaluación. Los repositorios se evaluaron según los cuatro primeros; los conjuntos de datos, según todos:

**Tabla 2. Criterios de evaluación y selección**

|**Código**|**Criterio**|**Descripción**|
|---|---|---|
|CR1|Especie|Monogástrica de producción: aves (principalmente pollo broiler) o cerdo|
|CR2|Segmento|Contenido del tracto gastrointestinal (ciego, íleon, colon) o heces|
|CR3|Tipo de dato|Cubre al menos uno de los cinco tipos de la Tabla 1|
|CR4|Acceso|Público, con identificador estable (número de acceso o DOI)|
|CR5|Dieta|Composición de la dieta o intervención dietaria documentada|
|CR6|Fenotipo|Variables productivas asociadas a las muestras|
|CR7|Trazabilidad|Vinculado a una publicación revisada por pares o a un proyecto documentado|
|||_Elaboración Propia_|



Los conjuntos de datos se clasificaron en tres niveles. El nivel **A (núcleo)** agrupa los que combinan un dato ómico de contenido intestinal con dieta o fenotipo documentados, y son candidatos directos para entrenar o validar el modelo. El nivel **B (referencia)** agrupa catálogos de genomas y genes que no responden a una intervención dietaria, pero son necesarios para anotar taxones y funciones. El nivel **C (complementario)** agrupa conjuntos con intervención dietaria controlada pero con un solo tipo de dato o de menor resolución.

5

### **3. Revisión de repositorios (Actividad 19)**

#### **3.1. Repositorios de secuencias**

Los datos crudos de secuenciación de microbioma animal se depositan principalmente en los archivos del International Nucleotide Sequence Database Collaboration: el **Sequence Read Archive (SRA)** del NCBI, organizado mediante proyectos BioProject, y el **European Nucleotide Archive (ENA)** del EMBL-EBI. Ambos permiten recuperar muestras individuales con sus metadatos y constituyen la fuente de los conjuntos de datos de nivel A identificados en este documento (National Center for Biotechnology Information, s. f.; European Bioinformatics Institute, s. f.-b).

Una proporción relevante de los datos de microbioma porcino se encuentra en repositorios chinos: el **China National GeneBank DataBase (CNGBdb)** , donde se depositaron los catálogos de genes del intestino porcino (China National GeneBank, s. f.), y el **Genome Sequence Archive (GSA)** del National Genomics Data Center, que aloja proyectos con prefijo PRJCA (National Genomics Data Center, s. f.). Su inclusión es necesaria para no subrepresentar la investigación porcina, aunque su acceso y sus metadatos siguen convenciones propias que deben verificarse al descargar.

#### **3.2. Catálogos de genomas microbianos**

Los catálogos de genomas agregan genomas ensamblados desde metagenomas y genomas de aislados en colecciones no redundantes por especie. **MGnify Genomes** , del EMBL-EBI, organiza catálogos específicos por bioma que incluyen genomas ensamblados desde metagenomas y de aislados, con información de genes y proteínas predichas y su posible función; entre sus catálogos de origen animal figuran el del intestino porcino y el de rumen bovino (European Bioinformatics Institute, s. f.-c). Existe además un catálogo específico del intestino de pollo (chicken-gut v1.0.1), referido como base de datos en herramientas de análisis publicadas. Para el proyecto, estos catálogos son la fuente natural de los nodos de taxón y de sus capacidades funcionales.

#### **3.3. Repositorios de metabolómica**

**MetaboLights** , del EMBL-EBI, es el repositorio de metabolómica donde se identificaron conjuntos de datos de contenido intestinal y suero de aves con identificadores MTBLS (European Bioinformatics Institute, s. f.-a). **Metabolomics Workbench** es el repositorio equivalente del consorcio estadounidense (Metabolomics Workbench, s. f.); en esta etapa no se realizó una búsqueda específica en él, por lo que queda como fuente secundaria por explorar. En los conjuntos identificados en esta revisión, la metabolómica rara vez se depositó junto con los datos de secuenciación del mismo animal; el portal HoloFood, descrito a continuación, es la excepción.

#### **3.4. Portales multiómicos integrados**

El **HoloFood Data Portal** es el recurso más próximo a las necesidades del proyecto. El proyecto HoloFood estudió, con un enfoque hologenómico, el efecto de las interacciones hospedero–microbiota en la producción de salmón y pollo, analizando datos multiómicos, características fenotípicas y metadatos en respuesta a nuevas dietas (Rogers et al., 2025). Sus datos se depositaron en archivos públicos (BioSamples, ENA, MetaboLights y MGnify), y el portal permite acceder a conjuntos multiómicos derivados de un mismo individuo o recuperar datos fenotípicos del hospedero vinculados a una muestra de microbioma intestinal; además, ofrece catálogos de genomas y de virus específicos del proyecto (Rogers et al., 2025).

6

#### **3.5. Recursos de conocimiento metabólico y composición de dietas**

Para construir los nodos de función, metabolito y dieta, y para imponer restricciones metabólicas, el proyecto requiere bases de conocimiento además de datos experimentales. Utkina et al. (2025) ilustran el conjunto de recursos necesarios para modelar el ciego de pollo: anotaron las funciones de los genomas con KEGG y MetaCyc, perfilaron las enzimas activas sobre carbohidratos con dbCAN3, basado en la base CAZy, reconstruyeron los modelos metabólicos con gapseq y, dado que el estudio original no divulgó la composición de la dieta, formularon la dieta de entrada a partir de una dieta típica de pollo basada en maíz, traduciendo sus componentes a metabolitos mediante VMH, FooDB y Feedtables.

Esta experiencia revela dos puntos para el proyecto. Primero, recursos como **Feedtables** (composición de ingredientes para alimentación animal) y **FooDB** (composición química de alimentos) permiten traducir una dieta formulada a metabolitos de entrada, que es exactamente la operación que requiere un nodo de dieta. Segundo, la base de reconstrucciones metabólicas de referencia más extensa, AGORA2, alojada en el recurso Virtual Metabolic Human, contiene 7.302 cepas del microbioma humano, por lo que su uso en especies de producción requiere verificar la cobertura de los taxones propios de aves y cerdos (Virtual Metabolic Human, s. f.).

**Tabla 3. Repositorios y recursos revisados**

|**Repositorio**|**Tipo**|**Contenido relevante**|**Rol en el gemelo digital**|
|---|---|---|---|
|NCBI SRA / BioProject|Secuencias|Metagenomas y 16S de contenido<br>intestinal|Composición microbiana|
|ENA (EMBL-EBI)|Secuencias|Metagenomas; datos crudos de<br>HoloFood|Composición microbiana|
|CNGBdb|Secuencias y<br>catálogos|Catálogos de genes del intestino porcino<br>(PGC, PIGC)|Composición y funciones<br>(cerdo)|
|GSA / NGDC|Secuencias y<br>catálogos|Proyectos PRJCA de microbioma<br>porcino; catálogo UPGG|Composición y funciones<br>(cerdo)|
|MGnify Genomes|Catálogo de<br>genomas|Catálogos por bioma: intestino de pollo y<br>de cerdo|Nodos de taxón y función|
|MetaboLights|Metabolómica|Metabolomas de contenido intestinal y<br>suero de aves|Nodos de metabolito; validación|
|Metabolomics<br>Workbench|Metabolómica|No explorado en detalle en esta etapa|Fuente secundaria por explorar|
|HoloFood Data Portal|Portal multiómico|Metagenoma, metaboloma y fenotipo por<br>individuo, con dietas controladas (pollo)|Todos los tipos de nodo|
|KEGG / MetaCyc|Conocimiento<br>metabólico|Rutas y reacciones|Nodos de función y<br>restricciones|
|CAZy / dbCAN3|Conocimiento<br>metabólico|Enzimas activas sobre carbohidratos|Degradación de fibra dietaria|
|VMH (AGORA2)|Modelos<br>metabólicos|7.302 reconstrucciones de microbios<br>humanos|Restricciones (cobertura por<br>verificar)|
|Feedtables / FooDB|Composición de<br>dietas|Composición de ingredientes y alimentos|Nodos de dieta|



_Elaboración Propia_

7

### **4. Conjuntos de datos seleccionados (Actividad 15)**

Se seleccionaron 13 conjuntos de datos: cuatro de nivel A, seis de nivel B y tres de nivel C (Tabla 4). Todos los identificadores se verificaron en las secciones de disponibilidad de datos de las publicaciones asociadas o en las fichas de los propios repositorios.

##### **Tabla 4. Conjuntos de datos seleccionados y su clasificación**

|**ID**|**Identificador**|**Especie y segmento**|**Tipo de dato**|**Dieta / fenotipo**|**Nivel**|
|---|---|---|---|---|---|
|D1|HoloFood Data Portal|Pollo; intestino|Metagenoma,<br>metaboloma, fenotipo<br>por individuo|Nuevas dietas y aditivos;<br>fenotipo|A|
|D2|PRJNA902117 (SRA) +<br>modelos en GitHub|Pollo; ciego (33)|Metagenoma shotgun;<br>237 MAG; modelos<br>metabólicos|Dieta no divulgada; dieta<br>de entrada formulada|A|
|D3|Zenodo 6083555|Pollo; ciego|Reconstrucciones de<br>25 géneros; perfiles<br>16S y shotgun|Cuatro promotores de<br>crecimiento; desempeño|A|
|D4|MTBLS560<br>(MetaboLights)|Pollo; íleon, ciego y<br>suero (60 aves)|Metaboloma por RMN|Dieta documentada;<br>eficiencia digestiva|A|
|D5|Colección de Feng et al.<br>(2021)|Pollo; intestino (799<br>muestras)|12.339 genomas; ~16,6<br>millones de genes|No aplica|B|
|D6|Catálogo de Gilroy et al.<br>(2021)|Pollo; heces|Más de 5.500 MAG;<br>más de 20 millones de<br>genes|No aplica|B|
|D7|MGnify chicken-gut<br>v1.0.1|Pollo; intestino|Catálogo de especies|No aplica|B|
|D8|CNP0000824<br>(CNGBdb), PIGC|Cerdo; heces y lumen<br>de yeyuno, íleon y<br>ciego|17,2 millones de genes;<br>6.339 MAG|No aplica|B|
|D9|CNPhis0002818<br>(CNGBdb), PGC|Cerdo; heces (287<br>animales)|7,6 millones de genes|No aplica|B|
|D10|PRJCA042329 (GSA),<br>UPGG|Cerdo; intestino|Catálogo de genomas y<br>genes|No aplica|B|
|D11|PRJEB11368 (ENA)|Cerdo; colon|16S|0 % frente a 30 % de<br>DDGS|C|
|D12|PRJCA001177 (GSA)|Cerdo; digesta de íleon<br>y colon|16S|Distintas fuentes de fibra<br>dietaria|C|
|D13|MTBLS13078<br>(MetaboLights)|Pollo; suero (192 aves)|Metaboloma|0 % frente a 20 % de<br>bagazo fermentado|C|



_Elaboración Propia_

#### **4.1. Nivel A: conjuntos núcleo**

**D1 · HoloFood.** Es el único conjunto identificado que reúne, para un mismo animal, datos de microbioma, metaboloma y fenotipo bajo intervenciones dietarias controladas en pollo, que son los cinco tipos de dato de la Tabla 1 (Rogers et al., 2025). Sus datos crudos se distribuyen entre ENA, MetaboLights y MGnify, y el portal es el punto de acceso que preserva el vínculo entre muestras. Se recomienda como conjunto principal de entrenamiento.

**D2 · Metagenomas de ciego de pollo (PRJNA902117).** Contiene datos de secuenciación metagenómica shotgun de 33 ciegos de pollo, generados en un estudio previo y reanalizados por Utkina et al. (2025), quienes depositaron en GitHub los modelos metabólicos, los genomas

8

ensamblados utilizados, las tablas de dieta de entrada y el código de simulación. Su valor para el proyecto es doble: aporta los datos de composición y un conjunto de modelos metabólicos ya reconstruidos y validados contra perfiles de ácidos grasos de cadena corta, utilizables como restricciones. Su limitación es que la composición de la dieta no fue divulgada por el estudio original.

**D3 · Modelos del microbioma cecal bajo promotores de crecimiento (Zenodo).** Plata et al. (2022) depositaron en Zenodo las reconstrucciones metabólicas de los géneros centrales del ciego de pollo, junto con los perfiles taxonómicos y funcionales de 16S y metagenómica discutidos en su artículo. El estudio compara pollos alimentados con cuatro promotores de crecimiento antimicrobianos y asocia el desempeño productivo con el metabolismo microbiano, por lo que vincula dieta, microbioma y fenotipo.

**D4 · Metabolomas de contenido intestinal (MTBLS560).** Beauclercq et al. (2018) analizaron mediante resonancia magnética nuclear los metabolomas de contenido ileal, contenido cecal y suero de 60 pollos provenientes de líneas seleccionadas por eficiencia digestiva, y construyeron modelos que explicaron entre 74 % y 78 % de la variabilidad de los rasgos de eficiencia digestiva. La composición de la dieta se reporta en el material suplementario del artículo. Es el conjunto más adecuado para validar nodos de metabolito frente a un fenotipo productivo.

#### **4.2. Nivel B: catálogos de referencia**

Para pollo, Feng et al. (2021) ensamblaron 12.339 genomas microbianos y construyeron un catálogo de aproximadamente 16,6 millones de genes a partir de 799 muestras públicas del intestino de pollo provenientes de diez países (D5). Gilroy et al. (2021) secuenciaron 50 muestras fecales de dos razas y las analizaron junto con 582 metagenomas públicos, obteniendo más de 20 millones de genes no redundantes y más de 5.500 genomas ensamblados desde metagenomas (D6). Ambos catálogos, junto con el catálogo chicken-gut de MGnify (D7), permiten anotar los taxones y funciones detectados en los conjuntos de nivel A.

Para cerdo, el catálogo integrado PIGC (D8) contiene 17.237.052 genes agrupados al 90 % de identidad proteica a partir de 787 metagenomas intestinales, así como 6.339 genomas ensamblados agrupados en 2.673 especies, e incorpora muestras del lumen de yeyuno, íleon y ciego para representar el tracto completo (Chen et al., 2021). El catálogo previo PGC (D9) reúne más de 7,6 millones de genes a partir de muestras fecales de 287 cerdos de Francia, Dinamarca y China (China National GeneBank, s. f.). El catálogo UPGG (D10) se ofrece a través de un sitio web que incluye una base de datos en formato Kraken2 para la cuantificación taxonómica de lecturas metagenómicas.

#### **4.3. Nivel C: conjuntos complementarios**

Tres conjuntos presentan intervenciones dietarias controladas, pero con un solo tipo de dato. El proyecto PRJEB11368 (D11) evalúa el metagenoma colónico de cerdos alimentados con una dieta sin granos secos de destilería (DDGS) frente a una con 30 % de DDGS, mediante secuenciación 16S. El proyecto PRJCA001177 (D12) compara la comunidad bacteriana de la digesta ileal y colónica de cerdos alimentados con dietas que contienen distintas fibras dietarias. El conjunto MTBLS13078 (D13) contiene metabolómica sérica de 192 pollos broiler asignados a una dieta control o a una con 20 % de bagazo de cervecería fermentado. Estos conjuntos son útiles para probar la respuesta del modelo a una variable dietaria concreta, pero no permiten construir por sí solos todos los tipos de nodo.

9

### **5. Brechas de datos identificadas**

**Escasez de datos multiómicos pareados.** Entre los conjuntos identificados, solo HoloFood reúne microbioma, metaboloma y fenotipo del mismo individuo bajo dietas controladas. En el resto, la metabolómica y la secuenciación rara vez se depositan juntas, lo que obliga a combinar fuentes distintas.

**Dietas no documentadas.** Incluso en los conjuntos mejor documentados, la composición de la dieta puede no estar disponible; Utkina et al. (2025) debieron formular una dieta típica porque el estudio original no la divulgó. Para un gemelo digital cuya variable manipulable es la dieta, este es el vacío más crítico.

**Modelos metabólicos centrados en humanos.** La base de reconstrucciones metabólicas de referencia más extensa corresponde a microbios humanos. Los modelos específicos de aves provienen de estudios puntuales (Plata et al., 2022; Utkina et al., 2025), y en esta revisión no se identificaron colecciones equivalentes para el microbioma porcino.

**Asimetría entre especies.** Los datos de pollo son más completos en integración multiómica, mientras que los de cerdo destacan en catálogos de genes y genomas. Esto sugiere iniciar el desarrollo con pollo.

10

### **6. Recomendaciones para Desarrollo**

Con base en la revisión, se propone la siguiente correspondencia entre fuentes de datos y tipos de nodo para el modelado conceptual del grafo heterogéneo (Actividad 23):

**Tabla 5. Correspondencia propuesta entre fuentes y tipos de nodo**

|**Tipo de nodo**|**Fuente principal**|**Fuente complementaria**|
|---|---|---|
|Taxón|D1 (HoloFood), D2|Catálogos D5–D7|
|Función metabólica|Anotación con KEGG, MetaCyc y CAZy|Modelos de D2 y D3|
|Metabolito|D1, D4|D13|
|Dieta|Metadatos de D1|Feedtables y FooDB para traducir dietas a<br>metabolitos|
|Fenotipo productivo|D1, D4|D3|
||_Elaboración Propia_||



La elección de la especie inicial debe considerar dos criterios que apuntan en direcciones distintas. Desde la disponibilidad de datos, el pollo presenta la base más completa: concentra los cuatro conjuntos de nivel A identificados, incluido el único que integra microbioma, metaboloma y fenotipo del mismo individuo bajo dietas controladas (Rogers et al., 2025), junto con modelos metabólicos del ciego ya reconstruidos y validados (Plata et al., 2022; Utkina et al., 2025). Desde la transferencia metodológica, en cambio, el cerdo ofrece una ventaja documentada: su catálogo de referencia del microbioma intestinal comparte con el catálogo humano solo el 12,6 % de sus genes, pero el 70 % de sus rutas funcionales (China National GeneBank, s. f.), lo que favorece la reutilización de métodos desarrollados en microbioma humano, siempre que el grafo se organice en torno a funciones y metabolitos más que a taxones. Sin embargo, en esta revisión no se identificaron conjuntos porcinos que combinen microbioma, metaboloma, dieta y fenotipo del mismo animal.

e recomienda iniciar el desarrollo con pollo, utilizando HoloFood como conjunto principal, los modelos metabólicos de Utkina et al. (2025) y Plata et al. (2022) como fuente de restricciones, y MTBLS560 para validar las predicciones de metabolitos. El cerdo puede abordarse como extensión posterior, a partir del catálogo PIGC y de los catálogos D9 y D10 para los nodos de taxón y función. Si el equipo opta por iniciar con cerdo, esa decisión debe acompañarse de una búsqueda adicional de datos porcinos pareados antes del modelado conceptual del grafo heterogéneo.

11

### **7. Limitaciones**

La revisión no es exhaustiva: se orientó por los antecedentes identificados en el estudio bibliométrico y por búsquedas dirigidas, por lo que pueden existir conjuntos pertinentes no incluidos. Las cifras de muestras, genes y genomas corresponden a lo reportado por las publicaciones y fichas de repositorio, y no se verificaron descargando los datos. Las licencias de uso y las condiciones de acceso, en especial las de los repositorios chinos, deben confirmarse antes de su uso. Finalmente, Metabolomics Workbench no se exploró en detalle en esta etapa y debe revisarse en una actualización del inventario.

12

### **Referencias**

- Beauclercq, S., Nadal-Desbarats, L., Hennequet-Antier, C., Gabriel, I., Tesseraud, S., Calenge, F., Le Bihan-Duval, E., & Mignon-Grasteau, S. (2018). Relationships between digestive efficiency and metabolomic profiles of serum and intestinal contents in chickens. _Scientific Reports, 8_ (1), Artículo 6678. https://doi.org/10.1038/s41598-018-24978-9

- Chen, C., Zhou, Y., Fu, H., Xiong, X., Fang, S., Jiang, H., Wu, J., Yang, H., Gao, J., & Huang, L. (2021). Expanded catalog of microbial genes and metagenome-assembled genomes from the pig gut microbiome. _Nature Communications, 12_ , Artículo 1106. https://doi.org/10.1038/s41467-021-21295-0

- China National GeneBank. (s. f.). _China National GeneBank DataBase (CNGBdb)_ [Base de datos]. https://db.cngb.org

- European Bioinformatics Institute. (s. f.-a). _MetaboLights_ [Base de datos]. https://www.ebi.ac.uk/metabolights/

- European Bioinformatics Institute. (s. f.-b). _European Nucleotide Archive_ [Base de datos]. https://www.ebi.ac.uk/ena

- European Bioinformatics Institute. (s. f.-c). _MGnify Genomes_ [Base de datos]. https://www.ebi.ac.uk/metagenomics/browse/genomes/

- Feng, Y., Wang, Y., Zhu, B., Gao, G. F., Guo, Y., & Hu, Y. (2021). Metagenome-assembled genomes and gene catalog from the chicken gut microbiome aid in deciphering antibiotic resistomes. _Communications Biology, 4_ , Artículo 1305. https://doi.org/10.1038/s42003-021-02827-2

- Gilroy, R., Ravi, A., Getino, M., Pursley, I., Horton, D. L., Alikhan, N.-F., Baker, D., Gharbi, K., Hall, N., Watson, M., Adriaenssens, E. M., Foster-Nyarko, E., Jarju, S., Secka, A., Antonio, M., Oren, A., Chaudhuri, R. R., La Ragione, R., Hildebrand, F., & Pallen, M. J. (2021). Extensive microbial diversity within the chicken gut microbiome revealed by metagenomics and culture. _PeerJ, 9_ , Artículo e10941. https://doi.org/10.7717/peerj.10941

- Metabolomics Workbench. (s. f.). _Metabolomics Workbench_ [Base de datos]. https://www.metabolomicsworkbench.org

- National Center for Biotechnology Information. (s. f.). _Sequence Read Archive_ [Base de datos]. https://www.ncbi.nlm.nih.gov/sra

- National Genomics Data Center. (s. f.). _Genome Sequence Archive_ [Base de datos]. https://ngdc.cncb.ac.cn

- Plata, G., Baxter, N. T., Susanti, D., Volland-Munson, A., Gangaiah, D., Nagireddy, A., Mane, S. P., Balakuntla, J., Hawkins, T. B., & Kumar Mahajan, A. (2022). Growth promotion and antibiotic induced metabolic shifts in the chicken gut microbiome. _Communications Biology, 5_ (1), Artículo 293. https://doi.org/10.1038/s42003-022-03239-6

- Plata, G., Baxter, N. T., Susanti, D., Volland-Munson, A., Gangaiah, D., Nagireddy, A., Mane, S., Balakuntla, J., Hawkins, T. B., & Kumar (Mahajan), A. (2022). _Growth promotion and antibiotic induced metabolic shifts in the chicken gut microbiome_ [Software y conjunto de datos]. Zenodo. https://zenodo.org/records/6083555

- Rogers, A. B., Kale, V., Baldi, G., Alberdi, A., Gilbert, M. T. P., Gupta, D., Limborg, M. T., Li, S., Payne, T., Petersen, B., Rasmussen, J. A., Richardson, L., & Finn, R. D. (2025). HoloFood Data Portal: Holo-omic datasets for analysing host–microbiota interactions in animal production. _Database, 2025_ , Artículo baae112. https://doi.org/10.1093/database/baae112

13

- Utkina, I., Fan, Y., Willing, B. P., & Parkinson, J. (2025). Metabolic modeling of microbial communities in the chicken ceca reveals a landscape of competition and co-operation. _Microbiome, 13_ (1), Artículo 248. https://doi.org/10.1186/s40168-025-02241-4

- Virtual Metabolic Human. (s. f.). _Virtual Metabolic Human_ [Base de datos]. https://www.vmh.life

   - _Nota: los identificadores de conjuntos de datos citados en la Tabla 4 corresponden a los registros públicos de cada repositorio._

   - _Documento elaborado por el Área de Investigación · PIA-2 Microbioma Digital · Sección 302 · UTEM · 2026-II Identificadores verificados el 21-09-2026 · Documento generado el 21-09-2026_

14
