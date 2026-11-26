# Verificación de reproducibilidad de la entrega (A115, #343)

- **Fecha:** 25-11-2026. **Equipo:** Windows 11 (10.0.26300), CPU, Python 3.13.17.
- **Qué se reproduce:** la entrega sintética de A117 (`python scripts/run_delivery.py`,
  [`delivery.md`](delivery.md)) y la suite E2E de la Web App (`pytest -m e2e`).

> **Datos sintéticos.** Reproducir la entrega no requiere D1, red ni `data/raw/`.

## 1. Clon y entorno nuevos (A115-P1)

Procedimiento seguido, con un clon de `main` en `a51cfec` y un entorno virtual nuevo:

```bash
git clone https://github.com/jvnioo/NutriGraphDT.git repo && cd repo
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -e ".[dev,graph,baselines,demo]"
.venv/Scripts/python scripts/run_delivery.py --output ../delivery-clean --work-dir ../work
.venv/Scripts/python -m pytest -m e2e
```

| Comprobación | Resultado |
|---|---|
| Predicciones de `synthetic` y `synthetic_constrained` frente a las corridas congeladas | Iguales (diferencia máxima 0) |
| Métricas de test frente a `reports/delivery/results.json` | Iguales |
| Escenarios del catálogo con su estado esperado | 6 de 6 en cada corrida |
| Datos, validación y grafo (`data`, `graph` del registro) | Iguales |
| Suite E2E | 17 de 17 pasan |

Lo que faltaba o fallaba, y cómo quedó:

| Hallazgo | Corrección |
|---|---|
| Un clon dentro de una ruta profunda de Windows supera el límite de 260 caracteres y `pip` no puede instalar PyTorch (`OSError: [Errno 2]`). | Documentado en [`development.md`](development.md): clonar en una ruta corta o activar las rutas largas. |
| El SHA-256 de `configs/delivery.json` cambiaba en un clon de Windows (`core.autocrlf` escribe CRLF), aunque el contenido era el mismo. | `nutrigraphdt.delivery` normaliza los fines de línea antes del hash; prueba en `tests/unit/test_delivery_config.py`. |
| La guía de desarrollo no decía cómo reproducir la entrega ni que la app necesita el extra `demo`. | Sección «Reproducing the delivery» en [`development.md`](development.md). |

## 2. Versiones exactas y semillas (A115-P2)

- **Versiones:** [`requirements-lock.txt`](../../requirements-lock.txt), generado con
  `pip freeze --exclude-editable` en el entorno nuevo (85 paquetes; `colorama` solo en Windows).
- **Semillas:** bloque `seeds` de [`configs/delivery.json`](../../configs/delivery.json): semilla de
  la cohorte (1), de entrenamiento (287), de MC-dropout (0) y del explicador (0). Una prueba
  verifica que coinciden con las configuraciones de entrenamiento y con el motor.
- **Python:** 3.13 verificado (3.13.17); el proyecto admite 3.11 o más nuevo.

Instalar desde el archivo de versiones en otro clon nuevo (`pip install -r requirements-lock.txt`
y `pip install -e . --no-deps`) y correr `scripts/run_delivery.py` dio otra vez predicciones
iguales a las congeladas (diferencia máxima 0), las mismas métricas y 6 de 6 escenarios en cada
corrida.

**Límite:** la verificación se hizo en Windows. En Linux o macOS el archivo de versiones debería
instalar lo mismo (los marcadores de plataforma excluyen `colorama`), pero no se probó. Si se
reproduce en otro sistema, agregue el resultado aquí.

## 3. Figuras y consultas (A115-P3)

Toda figura de la entrega sale de un script del repositorio y registra el comando y el commit:
ver [`figures.md`](figures.md). No hubo consultas de Documentación ni de Investigación durante esta
actividad; las que lleguen se registran en #346 con su respuesta.
