# Guía de reproducibilidad: del clon a la app (A120-P1, #352)

Pasos para obtener, en un equipo nuevo y sin ayuda, el estado de entrega de NutriGraphDT:

1. instalar el proyecto;
2. verificarlo;
3. correr la entrega (datos, grafo, modelo, simulación y explicación);
4. abrir la Web App.

Cada comando se ejecutó en el estado final de esta rama. Los tiempos medidos están en la
sección 7.

> **Datos sintéticos.** La entrega, la plataforma y sus reportes usan la cohorte sintética y no
> necesitan red, D1 ni `data/raw/`. Los targets sintéticos no dependen de la dieta ni del aditivo:
> una diferencia entre escenarios describe al modelo, no un efecto biológico
> ([alcance](final-scope.md)). D1 (HoloFood) queda como anexo opcional (sección 9).

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Sistema | Windows 10 u 11, Linux o macOS. No hace falta GPU. |
| Python | 3.11 o más nuevo; la versión verificada es la 3.13. |
| Git | Cualquier versión reciente. |
| Disco | Unos 3 GB para el entorno virtual (PyTorch es la mayor parte). |
| Red | Solo para clonar e instalar. |
| Servicios pagos | Ninguno ([política de costos](cost-policy.md)). |

**Windows: clone en una ruta corta.** PyTorch trae archivos con rutas muy largas. Si el clon
queda dentro de una carpeta profunda, como `AppData\Local\Temp\...` o una subcarpeta de OneDrive,
se supera el límite de 260 caracteres y `pip` falla con `OSError` o `WinError 206`. Use una ruta
como `C:\Users\<usuario>\NutriGraphDT`.

## 2. Clonar e instalar

**Windows (PowerShell):**

```powershell
git clone https://github.com/jvnioo/NutriGraphDT.git C:\Users\<usuario>\NutriGraphDT
cd C:\Users\<usuario>\NutriGraphDT
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,graph,baselines,demo]"
```

Si `Activate.ps1` responde que la ejecución de scripts está deshabilitada, ejecute antes
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Solo afecta a esa ventana.

**Linux o macOS:**

```bash
git clone https://github.com/jvnioo/NutriGraphDT.git
cd NutriGraphDT
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,graph,baselines,demo]"
```

**Con las versiones exactas de la entrega.** En lugar de las dos últimas líneas, use el archivo
de versiones de A115 ([`reproducibility.md`](reproducibility.md) §2):

```bash
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
```

Todo comando de esta guía se ejecuta **con el entorno virtual activo** y desde la carpeta del
repositorio. El indicador `(.venv)` al inicio de la línea muestra que el entorno está activo.

## 3. Verificar la instalación

```bash
python -m pytest -m e2e -q
```

Corre la suite E2E de la Web App (A105): abrir, elegir un escenario, simular, exportar, ver el
grafo y la explicación, sin navegador. Debe terminar con `17 passed`.

Las verificaciones completas del repositorio, que exige todo PR:

```bash
ruff check .
ruff format --check .
mypy src
python -m pytest -q
```

Use `python -m pytest` y no `pytest` solo: algunas pruebas importan `scripts/` y necesitan la
carpeta del repositorio en `sys.path`.

## 4. Correr la entrega

```bash
python scripts/run_delivery.py
```

- **Qué hace:** pipeline sintético completo con [`configs/delivery.json`](../../configs/delivery.json).
  1. genera y valida la cohorte;
  2. construye los grafos;
  3. vuelve a entrenar las dos corridas de la plataforma desde cero (`synthetic` y
     `synthetic_constrained`);
  4. comprueba que sus predicciones son iguales a las de las corridas congeladas;
  5. simula los 6 escenarios del catálogo y explica uno.
- **Dónde deja el resultado:** `reports/delivery/report.md` y `results.json`. Las corridas nuevas
  quedan en `artifacts/delivery/`, que no se versiona.
- **Cómo se lee el resultado:** termina con código `0` si todo se reprodujo. Si una corrida no se
  reproduce o un escenario cambia de estado, termina con código `1` y el reporte dice cuál
  ([`delivery.md`](delivery.md)).

Para no tocar los reportes versionados, use carpetas propias:

```bash
python scripts/run_delivery.py --output ../delivery-out --work-dir ../delivery-work
```

## 5. Abrir la Web App

```bash
streamlit run scripts/demo_app.py
```

1. Streamlit imprime una dirección local, `http://localhost:8501`, y abre el navegador. Si no lo
   abre, copie la dirección. Las direcciones `Network URL` y `External URL` que también imprime
   no hacen falta.
2. La página de inicio muestra la **corrida activa** (`synthetic`, de
   [`configs/platform.json`](../../configs/platform.json)).
3. En **Escenario**, elija un escenario de referencia (por ejemplo `crude-protein-270`) y
   simúlelo.
4. En **Resultados** aparecen el gráfico basal frente a intervenido, las advertencias y la
   exportación a JSON y CSV.
5. Para cerrar la app, presione `Ctrl+C` en la terminal.

La variable de entorno `NUTRIGRAPHDT_RUN` cambia la corrida activa sin tocar el código; por
ejemplo, `synthetic_constrained`. Manual de la app: [`demo.md`](../demo.md).

## 6. Regenerar los reportes versionados (opcional)

Cada reporte de la entrega sale de un script y registra el comando y el commit
([`figures.md`](figures.md)):

| Comando | Escribe |
|---|---|
| `python scripts/run_delivery.py` | `reports/delivery/report.md`, `results.json` |
| `python scripts/plot_delivery.py` | `reports/delivery/figures/` |
| `python scripts/report_e2e.py` | `reports/e2e/report.md`, `results.json` |

Un reporte regenerado con el árbol limpio (`git status` vacío) registra `"dirty": false`.

## 7. Tiempos medidos

Medidos en el estado final de esta rama. Un equipo distinto tardará distinto; el orden de
magnitud es lo que sirve.

| Paso | Windows, CPU (Sergio) | Linux, 2 CPU (nube) |
|---|---:|---:|
| Clonar | — | ≈ 1 s |
| Crear el entorno e instalar | — | no comparable¹ |
| `pytest -m e2e` | ≈ 1 min 30 s | ≈ 30 s |
| `run_delivery.py` | ≈ 30 s | ≈ 10 s |
| `pytest -q` (suite completa) | ≈ 19 min | ≈ 9 min |
| Abrir la app (hasta que responde el servidor) | — | ≈ 2 s |

¹ La nube instala desde otro índice y con caché; el tiempo de instalación depende sobre todo de
la red. En una conexión doméstica, la descarga de PyTorch CPU (unos 200 MB) es lo más lento.
Los «—» de Windows se completan con la prueba desde un clon nuevo (sección 10).

## 8. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `pip` falla instalando PyTorch con `OSError`, `[Errno 2]` o `WinError 206` | Ruta demasiado larga en Windows: clone en una ruta corta (sección 1). |
| `Defaulting to user installation because normal site-packages is not writeable` | El entorno virtual no está activo: `pip` está instalando en el Python del sistema. Active `.venv` y repita. |
| `ruff`, `mypy` o `pytest` «no se reconoce como nombre de un cmdlet» | El mismo caso: active `.venv`. |
| `No module named 'scripts'` al correr las pruebas | Se usó `pytest` en lugar de `python -m pytest`. |
| `KeyboardInterrupt` mientras arranca Python | El arranque fue lento (por ejemplo, con el repositorio dentro de OneDrive) y se presionó una tecla. Repita el comando y espere. |
| Avisos `FutureWarning`, `DeprecationWarning` o `node types {'additive'} are isolated` de PyTorch o PyG | Son de las bibliotecas y no afectan el resultado. |
| Letras con tilde mal escritas en la consola de Windows (`sintÚtica`, `simulaci¾n`) | La consola no usa UTF-8. Solo afecta a la pantalla, no a los reportes. Para verlas bien, ejecute antes `$env:PYTHONIOENCODING="utf-8"`. |

## 9. Anexo opcional: resultados exploratorios de D1

D1 (HoloFood, pollo) no es parte de la entrega. Estos pasos regeneran los resultados
exploratorios, necesitan red y tardan bastante más:

```bash
python scripts/fetch_holofood.py                          # descarga D1 en data/raw/ (30–60 min)
python scripts/build_graph.py --save-graphs --overwrite   # 185 grafos en artifacts/graphs/
```

`data/raw/` y `artifacts/` no se versionan. Cada resultado de D1 tiene su comando y su tiempo en
su documento:
- [baselines](../models/baselines-d1-composition.md);
- [GNN](../models/gnn-d1-composition.md) e [identidad de taxones](../models/gnn-taxon-identity.md);
- [restricciones](../models/constraints-comparison-a73.md);
- [incertidumbre](../models/uncertainty.md);
- [explicaciones fuera de fold](../models/out-of-fold-explanations.md).

## 10. Registro de la prueba por alguien fuera de Desarrollo (A120-P4, #355)

La guía la escribió Desarrollo, que no ve los pasos que da por sabidos. Una persona de otra
célula la sigue en su equipo, sin ayuda, de la sección 2 a la 5, y registra el resultado aquí o
en #355:

| Campo | Valor |
|---|---|
| Quién (célula) | |
| Fecha | |
| Sistema y Python | |
| Hasta dónde llegó | |
| Pasos que fallaron o confundieron | |
| Corrección o Issue | |
