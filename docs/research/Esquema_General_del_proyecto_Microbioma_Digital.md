

## **Microbioma Digital**



<!-- Start of picture text -->
Gemelo Digital Nutricional · GNN + PINNs<br><!-- End of picture text -->



<!-- Start of picture text -->
PIA-2 · Sección 302 · Gestión de Proyectos Informáticos · UTEM<br>Identidad cromática del proyecto<br>#25A3A8 #0E9987 #087F9E #0767A0 #032E54<br><!-- End of picture text -->

# **Esquema General del proyecto**

#### **Microbioma Digital · Gemelo Digital Nutricional**

Modelo objetivo del prototipo aviar / porcino

###### **Informe técnico de diseño conceptual y modelado relacional**

Grafo heterogéneo · GNN · restricciones bioquímicas · simulación in silico

###### **Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II**

_Fundamentación: entregables formales del Área de Investigación_

Estudio Bibliométrico · Revisión de repositorios y selección de datasets

Versión 3.1 · 21 de septiembre de 2026

Documento de diseño propuesto · No corresponde a un sistema implementado ni validado

**MICROBIOMA DIGITAL  /  ESQUEMA GENERAL DEL PROYECTO**

PIA-2  ·  S302  ·  21.09.2026

### **1. Propósito y alcance del esquema general**



Este informe define **el resultado estructural que el equipo debe construir** : un grafo heterogéneo instanciable para un experimento nutricional concreto, no una secuencia de actividades ni una infografía. Cada nodo representa una entidad identificable y cada arista una relación con tipo, sentido, respaldo y, cuando proceda, atributos cuantitativos. La figura central de la página siguiente constituye el boceto técnico del producto esperado.

**Alcance del esquema:** la Figura 1 presenta un **grafo biológico relacional** que funciona como modelo objetivo del prototipo, no un mapa de etapas. Los datos, la GNN, las restricciones y la interfaz construyen, procesan o muestran el grafo, pero no son nodos biológicos.

##### **1.1. Base documental y jerarquía de evidencia**

Se utilizan como fuentes internas únicamente dos entregables formales del área de Investigación: el **Estudio Bibliométrico** [I1] y la **Revisión de repositorios y selección de datasets** [I2]. Se contrastan conceptos específicos con publicaciones arbitradas [R1–R3] y documentación oficial de aprendizaje sobre grafos [T1–T2]. La propuesta inicial y los cronogramas **no se emplean como fundamento científico ni como fuentes del diseño** .

##### **1.2. Qué es hecho documentado y qué es decisión propuesta**

|**CATEGORÍA**|**AFIRMACIÓN Y ALCANCE**|
|---|---|
|Respaldado por<br>Investigación|Se catalogan 13 conjuntos: 4 núcleo, 6 de referencia y 3 complementarios; en el<br>inventario HoloFood es la fuente aviar multiómica más integrada [I2, pp. 7–11].|
|Respaldado por literatura|El modelamiento metabólico cecal de pollo ha utilizado genomas reconstruidos y ha<br>contrastado perfiles de AGCC con ensayos experimentales [R2].|
|Decisión de diseño|Representar dieta, sustrato, taxón, función, metabolito, huésped y fenotipo como<br>tipos diferenciados; las aristas de la figura son una plantilla que deberá instanciarse<br>con evidencia.|
|Pendiente de comprobar|Qué taxones y rutas exactas, qué dosis y qué metabolitos están enlazados por<br>muestra en los datasets descargados; no se asumen en este informe.|



**Lectura del alcance:** se propone un prototipo in silico y experimental, no un gemelo individual en tiempo real ni un sistema que demuestre causalidad o eficacia de aditivos. Los términos «producción» y «concentración» se diferenciarán de acuerdo con la variable efectivamente medida [I1; I2].

Diseño objetivo · no corresponde a un sistema implementado ni validado

2

**MICROBIOMA DIGITAL  |  ESQUEMA GENERAL**

FIGURA 1  ·  DIAGRAMA TÉCNICO VECTORIAL

### **Figura 1. Grafo objetivo de una instancia del gemelo digital**

Boceto de estructura final: los nodos son entidades del dominio; las flechas denotan tipos de relaciones dirigidas. Los nombres A/B y las rutas son **marcadores de posición** , no taxones ni procesos biológicos verificados.





<!-- Start of picture text -->
GRAFO HETEROGÉNEO OBJETIVO  ·  una instancia por especie, segmento y escenario<br>Intermediario<br>si se mide [M]<br>transforma / produce*<br>Sustrato disponible para consumo* microbiano A [T]Taxón / gremio capacidad anotada* fermentativa [F]Función / ruta producto candidato* Acetato [M]<br>fermentable [S] asociación / exposición*<br>aporta / compone<br>interacción?<br>Huésped<br>Propionato [M]<br>Dieta / ingredientes aporta / compone Otros sustratos producto candidato* [H]<br>[D] medidos [S] disponible para consumo*<br>Taxón / gremio capacidad anotada* Función / ruta<br>microbiano B [T] secundaria [F] producto candidato* se mide en<br>modula?<br>Butirato [M]<br>sustrato cruzado*<br>modula?<br>Aditivo y dosis<br>[A] Fenotipo observado<br>si existe [P]<br><!-- End of picture text -->

FORMAS Y TIPOS [D] dieta · [A] aditivo · [S] sustrato · [T] taxón / gremio · [F] función / ruta · [M] metabolito · [H] huésped · [P] fenotipo. ARISTAS CONTINUAS Relación tipada que solo podrá afirmarse para una instancia si existe evidencia y compatibilidad de datos. El asterisco indica relación biológica candidata a verificar. ARISTAS DISCONTINUAS Hipótesis de interacción / modulación. Deben quedar marcadas como hipotéticas; no convertir correlaciones en efectos causales.

ARISTAS CONTINUAS Relación tipada que solo podrá afirmarse para una instancia si existe evidencia y compatibilidad de datos. El asterisco indica relación biológica candidata a verificar.

Contexto que acompaña a cada grafo (no arista metabólica): especie seleccionada (pollo o cerdo), segmento intestinal, muestra / individuo, dieta o tratamiento, fecha / tiempo y procedencia de las mediciones. La estructura admite diversas especies, pero no mezcla sus observaciones como si fueran un mismo ecosistema. [I2, pp. 4–5, 10–11]

> * Relaciones de ejemplo sujetas a datos / literatura; líneas discontinuas = hipótesis de modulación no confirmada.

3

**MICROBIOMA DIGITAL  /  ESQUEMA GENERAL DEL PROYECTO**

PIA-2  ·  S302  ·  21.09.2026

### 2. Interpretación técnica del grafo objetivo



La Figura 1 debe leerse como una ontología mínima operacional. El inventario concreto se obtiene al reemplazar cada nodo genérico por registros de una especie, segmento y conjunto de datos definidos. Por ejemplo, «taxón / gremio A» representa el lugar de uno o varios taxones identificados en la muestra, no la afirmación de que una bacteria específica consume la fibra o produce acetato. [I2, pp. 4–5, 10–11; R2]

##### 2.1. Entidades y atributos de la primera versión

|TIPO|IDENTIDAD / ATRIBUTOS MÍNIMOS|PAPEL EN EL GRAFO|
|---|---|---|
|[D] Dieta|ID de dieta, ingredientes, composición y<br>unidad; versión de fuente.|Entrada contextual / manipulable; se enlaza a<br>sustratos documentados.|
|[A] Aditivo|Categoría, sustancia o cepa, dosis, unidad<br>y control experimental.|Intervención; efecto relacional solo si consta<br>evidencia.|
|[S] Sustrato|ID químico / nutricional, cantidad<br>disponible si se mide, unidad.|Recurso disponible para funciones y comunidad.|
|[T] Taxón|ID taxonómico, nivel taxonómico,<br>abundancia y método de cuantificación.|Componente de la comunidad; evita tratar<br>abundancia relativa como biomasa absoluta.|
|[F] Función /<br>ruta|Identificador de gen, enzima o ruta y<br>procedencia de anotación.|Vincula capacidades microbianas y<br>transformaciones candidatas.|
|[M] Metabolito|ID químico, matriz de muestra,<br>concentración / flujo, unidad.|Objetivo medible o intermediario; no confundir<br>ambas magnitudes.|
|[H] Huésped|ID seudonimizado / cohorte, especie,<br>segmento y covariables.|Contextualiza la observación, no equivale a una<br>vía metabólica.|
|[P] Fenotipo|Rasgo medido, unidad, tiempo y<br>correspondencia de individuo.|Variable adicional de evaluación si existen<br>etiquetas emparejadas.|



##### 2.2. Semántica de las conexiones

Una arista se define como la tupla (nodo origen, relación, nodo destino) con dirección, evidencia y atributos opcionales. «Dieta → sustrato» expresa composición; «taxón → función» expresa capacidad anotada y no actividad demostrada; «función → metabolito» expresa una transformación candidata; «metabolito → huésped» representa exposición o asociación contextual, no efecto fisiológico probado. Las aristas «aditivo → taxón / función» permanecen hipotéticas mientras no exista contraste experimental pertinente. [I2, pp. 6–11; R2]

Regla de implementación: no crear aristas «taxón produce metabolito» por mera coocurrencia ni unir individuos o estudios distintos como si fueran mediciones pareadas. Toda arista debe declarar fuente, método, nivel de evidencia y estado observado / anotado / inferido / hipotético.

Diseño objetivo · no corresponde a un sistema implementado ni validado

4

**MICROBIOMA DIGITAL  /  ESQUEMA GENERAL DEL PROYECTO**

PIA-2  ·  S302  ·  21.09.2026



##### 2.3. Contrato mínimo para instanciar el esquema

Para que la figura se convierta en un artefacto implementable, se propone el siguiente contrato ilustrativo de estructura, sin registros biológicos supuestos. Las claves y relaciones definitivas se fijarán una vez revisados los archivos de origen.

|OBJETO|CAMPOS OBLIGATORIOS PROPUESTOS|REGLA DE CONTROL|
|---|---|---|
|Nodo|node_id · node_type · source_id · attributes ·<br>missing_mask|Un identificador único por entidad y<br>contexto; atributos con unidad cuando<br>proceda.|
|Arista|source_id · relation_type · target_id · evidence_id ·<br>evidence_status|Ambos extremos existen; dirección,<br>procedencia y estado son explícitos.|
|Instancia|graph_id · species · gut_segment · study_id ·<br>sample_id · scenario_id|No mezclar individuos, matrices,<br>tiempos ni especies sin un contrato de<br>integración.|
|Salida|target_id · measured_or_predicted · unit ·<br>sample_matrix · model_version|Diferenciar medición de predicción y<br>concentración de producción o flujo.|



### 3. De las fuentes formales a un grafo instanciado

El documento de datasets separa las fuentes en núcleo (A), catálogos de referencia (B) y conjuntos complementarios (C). La identificación de una fuente no equivale a confirmar que sus archivos ya fueron descargados, licenciados, armonizados o emparejados. [I2, pp. 4–12]

|FUENTE DE INVESTIGACIÓN|FUNCIÓN PREVISTA|CONTROL ANTES DE USAR|
|---|---|---|
|D1 · HoloFood [I2]|Candidato de entrada multiómica aviar:<br>microbioma, metaboloma, dieta /<br>fenotipo vinculados.|Verificar IDs por muestra, tiempos,<br>matrices efectivamente<br>descargables y licencia.|
|D2 · PRJNA902117 y modelos;<br>D3 · Zenodo 6083555 [I2]|Referencias aviares de composición y<br>conocimiento / reconstrucción<br>metabólica.|La dieta de D2 no fue divulgada en<br>el estudio original; no presentarla<br>como observación medida.|
|D4 · MTBLS560 [I2]|Metabolómica de íleon, ciego y suero de<br>pollo; evaluación de variables medidas.|No equiparar suero, íleon y ciego ni<br>fingir que pertenece a individuos<br>de D1.|
|D5–D7 (pollo), D8–D10 (cerdo)<br>[I2]|Catálogos de taxones, genes y<br>funciones.|Usarlos como anotación de<br>referencia, no como experimentos<br>de dieta / respuesta.|
|D11–D13 [I2]|Intervenciones parciales que permiten<br>pruebas acotadas.|No son por sí solas bases<br>multiómicas completas.|
|KEGG / MetaCyc / CAZy;<br>Feedtables / FooDB [I2]|Relaciones y vocabularios de funciones,<br>metabolitos e ingredientes.|Auditar especie, identificadores,<br>cobertura y permisos de uso.|



Diseño objetivo · no corresponde a un sistema implementado ni validado

5

**MICROBIOMA DIGITAL  /  ESQUEMA GENERAL DEL PROYECTO**

PIA-2  ·  S302  ·  21.09.2026



##### 3.1. Política de trazabilidad y compatibilidad

Se deberán conservar identificadores de estudio, individuo, muestra, segmento, matriz analítica, tratamiento y tiempo, además del acceso o DOI y versión de anotación. Las transformaciones y los escaladores se ajustan solo sobre entrenamiento. Si dos fuentes no comparten claves verificables, se integran como conocimiento de referencia o se evalúan por separado, pero no se inventa un emparejamiento multiómico. [I2, pp. 9–12]

### 4. Motor de aprendizaje asociado al grafo

La red neuronal de grafos utiliza los atributos y las conexiones del grafo de la Figura 1 para construir representaciones de nodos mediante paso de mensajes, agregación y actualización. El paradigma de message passing y la distinción de tipos en grafos heterogéneos se apoyan en [T1–T2]. El grafo es el objeto que aprende el modelo; no debe sustituirse por un flujo de cajas de infraestructura.

##### 4.1. Especificación de modelo propuesta

|CAPA|CONTRATO CONCEPTUAL|
|---|---|
|Codificación|Vectores por tipo de nodo: abundancias, componentes dietarios, variables químicas y<br>covariables; máscara explícita de valores ausentes.|
|Relaciones|Convolución / mensajes condicionados por tipo de arista; modelos heterogéneos<br>documentados en PyTorch Geometric [T2].|
|Representación|Embeddings del grafo de un individuo / muestra / escenario, sin mezclar individuos en la<br>misma instancia.|
|Predicción|Cabezal para acetato, propionato o butirato solo si el dataset ofrece etiqueta<br>comparable; reportar unidad y matriz.|
|Comparación|Modelos tabulares de referencia frente a GNN simple y GNN heterogénea; ninguna<br>superioridad se supone de antemano.|



##### 4.2. Coherencia bioquímica: componente condicionado

Una pérdida posible es L = Ldatos + λ Lbio, con pesos y términos validados experimental y dimensionalmente. Se puede comenzar por no negatividad para magnitudes que físicamente la exigen; balances de masa y relaciones estequiométricas requieren entradas, salidas, estados, unidades y ecuaciones aprobadas. No es válido imponer un balance de flujo a concentraciones aisladas, ni llamar PINN estricta a cualquier penalización sin una ley mecanística explícita. [I1, pp. 25–28; R2]

El módulo bioquímico es condicionado: si faltan parámetros o ecuaciones válidas, se documenta y se evalúa un modelo sin esa restricción; no se fabrican constantes ni se garantiza cumplimiento mediante el nombre de la técnica.

Diseño objetivo · no corresponde a un sistema implementado ni validado

6

**MICROBIOMA DIGITAL  /  ESQUEMA GENERAL DEL PROYECTO**

PIA-2  ·  S302  ·  21.09.2026

### 5. Ejecución de escenarios e interpretación de salidas



Para una misma muestra, cohorte y contexto se construyen dos instancias comparables del mismo esquema: escenario basal y escenario intervenido. Solo cambian las variables documentadas de intervención (por ejemplo composición de dieta o dosis). Se usa el mismo modelo congelado para las predicciones comparadas; se conservan por separado las observaciones reales y los contrafactuales modelados. La diferencia predicha no prueba causalidad.

##### 5.1. Artefacto funcional que debe mostrar el prototipo

|COMPONENTE VISIBLE|INFORMACIÓN MÍNIMA|
|---|---|
|Grafo exploratorio|Nodos y aristas con filtros por tipo; al seleccionar una arista muestra relación, dirección<br>y evidencia.|
|Escenarios|Definición de especie, segmento, dieta, dosis y condiciones fijas; alertas cuando no hay<br>datos comparables.|
|Resultados|Estimaciones por metabolito efectivamente medible, unidad, matriz, diferencia basal /<br>intervención e incertidumbre si está calibrada.|
|Explicabilidad|Subgrafo / atributos relevantes como explicación de la predicción del modelo, no como<br>ruta biológica causal demostrada.|
|Registro|Versión del grafo, datasets / accesiones, partición, configuración, checkpoint y fecha de<br>simulación.|



##### 5.2. Límites de generalización entre especies

El estudio de repositorios propone iniciar con pollo por disponibilidad de muestras multiómicas enlazables y modelos cecales; para cerdo describe catálogos de gran cobertura, pero no identifica un conjunto equivalente que paree dieta, microbioma, metaboloma y fenotipo del mismo animal. Por tanto, «aviar / porcino» significa esquema extensible, no un modelo ya entrenado y transferible entre especies. [I2, pp. 8–11]

### 6. Validación, pruebas y criterios de aceptación

El estudio bibliométrico examina publicaciones 2021–2025 y encuentra una intersección escasa en las cadenas y el corpus estudiados; esto orienta el interés investigativo, sin demostrar inexistencia universal de trabajos. La viabilidad del prototipo debe resolverse con experimentos sobre datos efectivamente accesibles y resultados reproducibles. [I1, pp. 9–13, 24–33]

|PRUEBA|CRITERIO DE ACEPTACIÓN VERIFICABLE|
|---|---|
|Integridad del grafo|Cada nodo posee ID / tipo; cada arista apunta a IDs existentes, declara relación y tiene<br>procedencia. No hay fusión accidental de especies, segmentos o individuos.|
|Datos y particiones|Los scripts reproducen cargas y transformaciones; separación por estudio / dieta /<br>individuo según tarea; sin fuga por muestras relacionadas.|
|Aprendizaje|El modelo entrena sin NaN, entrega tensores esperados y compara MAE / RMSE con<br>baselines en un conjunto de prueba retenido.|



Diseño objetivo · no corresponde a un sistema implementado ni validado

7

**MICROBIOMA DIGITAL  /  ESQUEMA GENERAL DEL PROYECTO**

PIA-2  ·  S302  ·  21.09.2026

|PRUEBA|CRITERIO DE ACEPTACIÓN VERIFICABLE|
|---|---|
|Bioquímica|Solo evaluar ecuaciones sustentadas; informar tasa / magnitud de violaciones y<br>comparar predicciones con y sin restricción cuando corresponda.|
|Escenarios|La intervención altera exclusivamente entradas seleccionadas; la ausencia de etiqueta,<br>unidad o cobertura devuelve «no estimable», no un número arbitrario.|
|Interpretación|Se visualizan grafo y subgrafo explicativo; etiquetas de evidencia y advertencias<br>separan asociaciones, hipótesis y predicciones.|
|Reproducibilidad|Resultados vinculados a versiones de dataset, esquema, código y modelo; verificación<br>independiente del flujo completo.|



##### 6.1. Decisiones que deben cerrarse con Investigación

Antes de fijar la arquitectura entrenable: (i) especie y segmento inicial; (ii) intervención y dosis realmente registradas; (iii) variable objetivo, matriz y unidad; (iv) ontología con taxones / rutas específicos; (v) criterio para aristas sustentadas e inferidas; (vi) ecuaciones y tolerancias bioquímicas; (vii) método de partición y conjunto de validación externa. La Figura 1 es la plantilla para tomar estas decisiones, no una confirmación de que ya están resueltas.

### 7. Referencias y procedencia del diseño

La bibliografía distingue fuentes internas formales de Investigación, literatura primaria y documentación oficial. Las referencias [I1] y [I2] sustentan el dominio biológico y el inventario; [R1–R3] sirven como contraste científico; [T1–T2], como fundamento técnico de GNN.

[I1] Área de Investigación · Microbioma Digital (2026). Estudio Bibliométrico — PIA Microbioma Digital. Versión final, 21-09-2026. Documento interno formal del proyecto. Secciones 3–7 y conclusiones.

[I2] Área de Investigación · Microbioma Digital (2026). Revisión de repositorios y selección de datasets. Versión final, 21-09-2026. Documento interno formal del proyecto. Tablas 1–5 y secciones 4–7.

[R1] Rogers, A. B. et al. (2025). HoloFood Data Portal: holo-omic datasets for analysing host–microbiota interactions in animal production. Database, 2025, baae112. https://doi.org/10.1093/database/baae112

[R2] Utkina, I., Fan, Y., Willing, B. P. & Parkinson, J. (2025). Metabolic modeling of microbial communities in the chicken ceca reveals a landscape of competition and co-operation. Microbiome, 13, 248. https://doi.org/10.1186/s40168-025-02241-4 (consultar también corrección editorial del 22-12-2025).

[R3] Plata, G. et al. (2022). Growth promotion and antibiotic induced metabolic shifts in the chicken gut microbiome. Communications Biology, 5, 293. https://doi.org/10.1038/s42003-022-03239-6

[T1] Gilmer, J. et al. (2017). Neural Message Passing for Quantum Chemistry. Proceedings of Machine Learning Research, 70, 1263–1272. https://proceedings.mlr.press/v70/gilmer17a.html

[T2] PyTorch Geometric (documentación oficial). Heterogeneous Graph Learning. https://pytorch-geometric.readthedocs.io/en/latest/notes/heterogeneous.html

Nota metodológica: se incluyen enlaces a publicaciones y recursos oficiales para comprobación. La presencia de una relación en la Figura 1 indica una estructura que se pretende modelar, no que esa relación concreta haya sido validada por los documentos revisados.

Diseño objetivo · no corresponde a un sistema implementado ni validado

8
