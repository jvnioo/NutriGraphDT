# Demo de avance en Streamlit

`scripts/demo_app.py` es una aplicación local para mostrar el avance del proyecto (por ejemplo,
al profesor guía) a alguien que no conoce los grafos ni las GNN. Tiene tres páginas que se leen
en orden; cada una avanza en secciones numeradas, con un recuadro "Cómo leerlo" bajo cada
gráfico y un glosario en la barra lateral.

| Página | Pregunta que responde | Qué muestra |
|---|---|---|
| 1 · Explorador del grafo | ¿Cómo se representa un animal? | Cómo leer el dibujo; el grafo sintético completo, con los caminos que llevan a cada AGCC; un animal real de D1; y por qué los dos son tan distintos. |
| 2 · Partición y baselines | ¿Qué tan difícil es predecir los AGCC? | Cómo se separan los animales (por corral) y por qué; los cinco modelos de referencia; cuánto mejoran a "predecir la media" en D1 y en el sintético; qué significa para la GNN. |
| 3 · Entrenamiento | ¿Cómo aprende la GNN? | El proceso en cinco pasos; un entrenamiento en vivo (CPU o GPU); y la lectura del resultado: si aprendió, si le gana a la media y qué predice. |

## Principios

- **Todo sale del repositorio.** Cada página llama a `nutrigraphdt` o lee un reporte versionado;
  las lecturas automáticas ("el mejor modelo baja el error de…") se calculan de los datos.
- **Funciona sin la descarga completa de D1.** Usa la cohorte sintética (se genera al vuelo), el
  fixture de D1 (`tests/fixtures/holofood/`, 6 animales reales), la partición versionada y los
  reportes de `reports/baselines/`.
- **Cada número dice de dónde viene.** Las insignias "Datos sintéticos" y "Datos reales · D1" y
  las notas de cautela repiten las limitaciones de cada reporte. Lo que aún no existe (la GNN
  evaluada en D1) aparece como pendiente.
- **La diferencia entre el sintético y D1 se muestra, no se esconde.** En D1 los taxones no
  tienen relaciones (falta la anotación taxón → función), y el explorador lo explica con una
  comparación lado a lado.
- **Solo lectura.** La app no modifica el repositorio. El entrenamiento en vivo escribe en
  `runs/demo/`, que Git ignora.

## Instalación y ejecución

```bash
pip install -e ".[dev,graph,baselines,demo]"
streamlit run scripts/demo_app.py
```

Streamlit abre `http://localhost:8501`. El tema está en `.streamlit/config.toml`.

**Con GPU.** Para entrenar en vivo en GPU, lance la app desde un entorno con PyTorch para CUDA o
ROCm, como el que describe [gnn-training.md](models/gnn-training.md#gpu-opcional):

```bash
~/.venvs/nutrigraphdt-rocm/bin/pip install "streamlit>=1.50" "plotly>=5"
~/.venvs/nutrigraphdt-rocm/bin/streamlit run scripts/demo_app.py
```

La página "Entrenamiento" ofrece la GPU solo si PyTorch la ve. Antes de presentar conviene
entrenar una vez (desde la misma página o con
`python scripts/train_gnn.py --model hetero_gat --dataset synthetic`), para que haya una corrida
que mostrar aunque no se entrene en vivo.

## Guion sugerido (10 minutos)

1. **Explorador, sección 2 (2 min).** El sintético como el camino del alimento. Resaltar
   "Butirato": eso es lo que la GNN puede combinar.
2. **Explorador, secciones 3 y 4 (2 min).** Un animal real: casi todo son círculos vacíos. La
   tabla de la sección 4 explica por qué y qué implica para la GNN.
3. **Baselines (3 min).** La partición como un curso (estudiar, ensayar, examen), por qué por
   corral, y el gráfico contra la media: en D1 el piso es bajo y los datos, pocos.
4. **Entrenamiento (3 min).** Pulsar "Entrenar" con `hetero_gat` en GPU (unos 25 segundos) y
   recorrer a), b) y c): aprende, queda como los baselines en el sintético (lo esperado) y
   predice cerca del promedio. Cerrar con lo pendiente: la evaluación en D1 (A45-4).

## Pruebas

`tests/unit/test_demo_data.py` cubre las funciones de datos (vista del grafo, caminos,
comparación, partición, baselines y corridas) y `tests/integration/test_demo_app.py` dibuja cada
página con `streamlit.testing.v1.AppTest` (sin navegador). Ambos se omiten si faltan los extras.
