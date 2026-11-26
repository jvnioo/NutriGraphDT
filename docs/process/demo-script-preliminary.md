# Guion preliminar de la demostración del prototipo (A123, #356)

- **Versión:** preliminar, 25-11-2026. La versión final es A134-P2 (#376) y se ensaya en A139.
- **Duración objetivo:** unos 12 minutos de demostración más preguntas.
- **Qué se usa:** la Web App (`streamlit run scripts/demo_app.py`) con la corrida sintética
  congelada y los escenarios de [`configs/scenarios/`](../../configs/scenarios/README.md).
- **Respuestas a preguntas previsibles:** [`technical-qa.md`](technical-qa.md).

> **Datos sintéticos.** Todo lo que se muestra es la cohorte sintética. Decirlo al empezar y
> repetirlo al mostrar un resultado: una diferencia entre escenarios describe al modelo, no un
> efecto biológico.

## Antes de empezar

1. `streamlit run scripts/demo_app.py` y abrir `http://localhost:8501`.
2. Abrir una vez Escenario, Grafo y Explicación para que el motor y el explicador queden en caché.
3. Pulsar **Reiniciar el escenario** en la barra lateral.

## Guion

| # | Min. | Página | Qué hacer | Qué decir |
|---|---:|---|---|---|
| 1 | 1,5 | Inicio | Mostrar el rótulo y la corrida activa. | El problema: predecir la composición de AGCC del ciego desde un grafo de dieta, aditivo, microbioma y huésped, y comparar un escenario con su basal. Es un prototipo académico de factibilidad, no un recomendador. |
| 2 | 2 | Sintético frente a D1 | Mostrar el esquema de cada grafo. | Por qué datos sintéticos: D1 reconstruye 3 de las 11 relaciones y no tiene el tramo dieta → sustrato → taxón ni aditivos ([`final-scope.md`](final-scope.md)). Lo que se puede y no se puede afirmar. |
| 3 | 2 | Escenario | Catálogo → «Proteína bruta 270 g/kg» → **Simular escenario**. | El escenario cambia una sola variable del animal 0017; el basal es el mismo animal sin cambios. Las dos predicciones salen del mismo modelo congelado. La advertencia de extrapolación: la cohorte solo tiene 215 g/kg. |
| 4 | 2 | Resultados | Gráfico, tabla de diferencias, panel de calidad, descarga JSON. | Barras de error: intervalo MC-dropout al 80 %, calibrado con el factor medido en la cohorte sintética (#391); su cobertura en el test de los folds queda entre 71 % y 78 %. Métricas leídas de los archivos de la corrida; restricción D-06 con tasa de violación 0 %. La diferencia describe al modelo. |
| 5 | 1,5 | Grafo | Filtrar por relación; mostrar la leyenda. | Los 8 tipos de nodo y las 11 relaciones; evidencia «sintética»; las relaciones hipotéticas tienen su propio trazo. |
| 6 | 1,5 | Explicación | Salida `ln T`; barras por tipo y subgrafo. | Qué partes del grafo usa el modelo; asociación no es causalidad; con `homo_sage` se explican nodos y atributos, no relaciones. |
| 7 | 1 | Escenario | Catálogo → «Dosis del aditivo 0 (control)» → **Simular escenario**. | «No estimable»: la predicción cae fuera de lo que la corrida vio; no se informa ningún número. |
| 8 | 0,5 | — | Cierre. | Límites: datos sintéticos, corrida de demostración, intervalo calibrado solo para la configuración de la corrida `synthetic` (#391), umbral de diferencia relevante sin definir. |

## Recorrido preliminar (25-11-2026)

El guion se recorrió paso a paso **en forma automatizada** con `streamlit.testing.v1.AppTest`
(`tests/e2e/test_demo_script.py`, marcador `e2e`): cada paso del guion es un paso de la prueba y
comprueba lo que la persona debería ver. Pasa completo en el commit de este cambio. No es un
ensayo con público ni cronometrado: los ensayos cronometrados son A139-P1 (#382).

## Faltantes detectados

| Faltante | Dónde queda |
|---|---|
| La app no abre con un escenario precargado: hay que elegirlo y simular en vivo. | A134-P2 (#376): guion final con escenarios precargados. |
| No hay video ni capturas de respaldo si la app falla durante la defensa. | A134-P3 (#377). |
| La explicación no da importancia por relación con `homo_sage`. | Límite declarado en la página y en [`demo.md`](../demo.md); no se agrega una corrida heterogénea. |
| No hay una prueba en el equipo de presentación ni sin red. | A134-P1 (#375). |
