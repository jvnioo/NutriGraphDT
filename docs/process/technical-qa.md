# Preguntas técnicas previsibles y sus respuestas (A132, #368)

- **Emite:** Desarrollo. **Fecha:** 25-11-2026. **Issue:** #369.
- **Regla:** cada respuesta cita su fuente en el repositorio. Si el repositorio no respalda una
  afirmación, no se hace. Las cifras se copian de los reportes citados; si un reporte se regenera,
  hay que revisar esta página.
- **Revisión:** la revisión por otro integrante que pide #369 queda pendiente. Este documento lo
  escribió Desarrollo y no se le atribuye la aprobación de Investigación.

## 1. Alcance de los datos

**¿Por qué la plataforma usa datos sintéticos y no los datos reales de D1?**
Porque los datos públicos de D1 (HoloFood) reconstruyen solo 3 de las 11 relaciones del esquema.
Faltan el tramo `dieta → sustrato → taxón` y toda arista de aditivos, así que D1 no puede simular un
cambio de dieta o de aditivo a través del microbioma, que es lo que la plataforma debe mostrar. El
dataset sintético tiene los 8 tipos de nodo y las 11 relaciones.
*Fuente:* [`final-scope.md`](final-scope.md), secciones 1 y 2; decisión de Investigación
[#256](../research/decision_minimal_graph_D1.md), sección 1.

**¿Qué se puede afirmar con datos sintéticos?**
Que el flujo completo funciona de punta a punta (datos, grafo, modelo con restricciones,
simulación, explicación e interfaz), que se cumplen los contratos (invariancia, «no estimable»
fuera de soporte, rótulos de evidencia) y que las corridas se reproducen desde un clon limpio. No
se puede afirmar ningún efecto biológico: los targets sintéticos no dependen de la dieta ni del
aditivo.
*Fuente:* [`final-scope.md`](final-scope.md), sección 5;
[`synthetic-dataset-spec.md`](../synthetic-dataset/synthetic-dataset-spec.md) (alcance científico).

**¿Entonces la diferencia entre basal e intervenido no significa nada?**
Significa lo que predice el modelo para una instancia que no se observó. Describe al modelo, no un
efecto de la intervención. Toda respuesta lo advierte (`CAUSAL_WARNING`, `DIFFERENCE_WARNING`).
*Fuente:* [`scenario-comparison.md`](../models/scenario-comparison.md), secciones 1 y 4;
`src/nutrigraphdt/api/contract.py`.

## 2. Qué mostró D1

**¿Qué aprendieron del trabajo con D1?**
Que en D1 el grafo no agrega capacidad predictiva demostrable. Tras corregir cómo llegaba la señal
del microbioma, la GNN pasa de 4,19 a 3,92 pp (y de 4,11 a 3,90 pp) de error en fracciones y deja
de ser claramente peor que `ridge` por familia (3,69 pp), pero la mejora no se distingue del ruido
y no supera a `ridge`. Con 56 animales los datos no alcanzan para separar las causas.
*Fuente:* [`gnn-microbiome-diagnosis.md`](../models/gnn-microbiome-diagnosis.md) («Respuesta
corta»); [`gnn-taxon-identity.md`](../models/gnn-taxon-identity.md), sección 4.

**¿Las GNN superan al baseline por edad del animal (`day_only`) en D1?**
No se demostró. En la comparación pareada con δ = 0,5 pp (provisional, P-02), todos los intervalos
incluyen 0 y alcanzan +δ: el resultado es «No concluyente», que no es evidencia de equivalencia.
En `homo_sage`, el brazo sin restricciones queda por encima de `day_only` en 10 de 10 medias por
semilla.
*Fuente:* [`constraints-comparison-a73.md`](../models/constraints-comparison-a73.md), comparación
contra `day_only`.

## 3. Métricas de la entrega

**¿Con qué calidad predice el modelo de la plataforma?**
En el test de la corrida de entrega (4 animales sintéticos), el error medio de las fracciones es
6,21 pp, el de `ln T` es 0,110 y el R² medio de las fracciones es −0,14. En la validación cruzada
sintética de A68-P2 (60 animales, 10 semillas × 5 folds) fue 5,10 pp y 0,117. La diferencia se
explica por el diseño (12 animales de train y un fold frente a 50 folds). En este generador los
AGCC no dependen de las entradas, así que ninguna de las cifras mide capacidad predictiva.
*Fuente:* [`reports/delivery/report.md`](../../reports/delivery/report.md), secciones 4 y 5;
[`delivery.md`](delivery.md).

**¿La entrega se reproduce?**
Sí. `python scripts/run_delivery.py` vuelve a entrenar las dos corridas de la plataforma desde
cero y sus predicciones coinciden con las congeladas (diferencia máxima 0); los 6 escenarios del
catálogo dan su estado esperado con cada una.
*Fuente:* [`reports/delivery/report.md`](../../reports/delivery/report.md), sección 3.

## 4. Restricciones bioquímicas

**¿Qué restricción usa el modelo y con qué peso?**
La cota de D-06 sobre la fracción de propionato (`d06.hydrogen.propionate_bound`, p_p ≤ 2/3) con
λ = 0,1, la que eligió el barrido sintético para `homo_sage` (empate exacto entre λ = 0,1, 1, 10 y
100; se elige la menor).
*Fuente:* `reports/constraints/lambda_sweep/synthetic/selection.json`;
`configs/training/api_fixture_constrained.json`.

**¿Por qué el modelo con restricciones da lo mismo que el sin restricciones?**
Porque ninguna predicción viola la cota: la penalización y su gradiente son cero y el entrenamiento
es idéntico. La tasa de violación es 0 % en A68-P2 y en las dos corridas de entrega.
*Fuente:* [`reports/delivery/report.md`](../../reports/delivery/report.md), secciones 4 y 5;
[`reports/constraints/comparison/report.md`](../../reports/constraints/comparison/report.md).

**¿Qué significa «GNN/PINNs»?**
La GNN entrenada con `L_datos + λ·L_bio` (A57 y A68). No hay una red PINN aparte.
*Fuente:* [`final-scope.md`](final-scope.md), sección 7.

## 5. Simulación y «no estimable»

**¿Qué pasa si el usuario pide un escenario que el modelo no vio?**
Si la predicción cae fuera del soporte empírico del train de la corrida (mínimo y máximo de cada
fracción), la respuesta es «no estimable» y no lleva números; si basal o intervenido lo es, la
comparación también. Una entrada fuera de lo observado en el train, aunque la predicción sea
estimable, se advierte («el modelo extrapola»).
*Fuente:* [`scenario-comparison.md`](../models/scenario-comparison.md), sección 3;
`src/nutrigraphdt/api/engine.py` (`COVERAGE_WARNING`); D-06 §7.

**¿Cómo se garantiza que el escenario solo cambia lo declarado?**
Las pruebas recorren todo el catálogo y comparan la instancia derivada con la del basal: nodos,
aristas, máscaras y evidencias iguales salvo el atributo intervenido; una intervención nula da
diferencia cero exacta.
*Fuente:* [`scenario-comparison.md`](../models/scenario-comparison.md), sección 5;
`tests/integration/test_simulation_scenarios.py`.

## 6. Explicabilidad

**¿Qué explica la página Explicación?**
Las importancias de nodos y atributos de GNNExplainer para una salida del modelo, sobre la instancia
del escenario. El modelo de la plataforma (`homo_sage`) no admite máscaras de aristas, así que no
hay importancia por relación; el subgrafo muestra las aristas del grafo entre los nodos más
importantes.
*Fuente:* [`demo.md`](../demo.md), sección «Explicación (A104)»; `docs/models/explainers-poc.md`.

**¿Una importancia alta es un mecanismo biológico?**
No. Es una asociación que el modelo usa, no una causa; en datos sintéticos describe al modelo.
*Fuente:* A71-P3 (#280); `src/nutrigraphdt/demo/explanation.py` (`INTERPRETATION`).

**¿Son estables las explicaciones?**
En D1, con `EdgeGradientSaliency`, la estabilidad entre semillas del explicador vale 1 por
construcción (el método es determinista) y no mide robustez. La informativa es entre semillas del
plan: Φ̂ medio 0,43 (`log_butyrate_acetate`) y 0,46 (`log_propionate_acetate`), con 0 de 56
animales bajo el umbral provisional de 0,40.
*Fuente:* [`reports/explainability/d1/report.md`](../../reports/explainability/d1/report.md).

## 7. Incertidumbre

**¿Las predicciones tienen intervalo?**
En la plataforma, sí: un intervalo MC-dropout del modelo congelado (30 pasadas, nivel 80 %), **sin
calibrar**. La calibración en la cohorte sintética está pendiente (#391).
*Fuente:* [`demo.md`](../demo.md), sección «Resultados (A101)»; `src/nutrigraphdt/api/engine.py`
(`ScenarioEngine.interval`).

**¿Qué tan bien calibrada estaba la incertidumbre en D1?**
Depende de la salida. Para `log_propionate_acetate` la cobertura observada es compatible con la
nominal (53, 82 y 89 % al 50, 80 y 90 %); para `log_butyrate_acetate` hay subcobertura (34 y 63 % al
50 y 80 %).
*Fuente:* [`reports/uncertainty/d1/report.md`](../../reports/uncertainty/d1/report.md); resultado
exploratorio (#296).

## 8. Límites

- Datos sintéticos: ningún efecto biológico, ninguna recomendación de dieta o aditivo
  ([`final-scope.md`](final-scope.md), sección 5; README).
- Especie y segmento (`chicken`, `cecum`) son marcadores provisionales del generador, no una
  población ([`final-scope.md`](final-scope.md), sección 6).
- La corrida de la plataforma es de demostración: 20 animales, un fold y hasta 30 épocas
  ([`tests/fixtures/api/README.md`](../../tests/fixtures/api/README.md)).
- No hay umbral de «diferencia relevante»: es una pregunta abierta para Investigación
  ([`scenario-comparison.md`](../models/scenario-comparison.md), sección 6).
- La ruta plantada con efecto conocido no se agregó: cambiaría el contrato DS-01
  ([`scenario-comparison.md`](../models/scenario-comparison.md), sección 6).
