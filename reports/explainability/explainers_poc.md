# Prueba de concepto de explicadores de PyG (#157)

Generado con `python scripts/explainers_poc.py`. **Compatibilidad técnica, no interpretación**: modelos sin entrenar (semilla 157), salida `butyrate` de la instancia sintética `synthetic:graph:0001`; 30 épocas por explicador.

Versiones: Python 3.13.14, torch 2.14.1+cpu, torch_geometric 2.8.0.post1, captum 0.9.0.

Estados: `ok` (devuelve las máscaras pedidas y, si son de aristas, llegan al modelo), `error` (falla de forma explícita), `invalid` (devuelve algo, pero no sirve como explicación), `not_available` (falta una dependencia opcional).

Combinaciones compatibles: 16.

## Cómo leer las máscaras

- **Importancia de atributos** (`node_mask_type = attributes`): un valor por nodo y columna de `x`, forma `[nodos, columnas]`.
- **Importancia de nodos** (`node_mask_type = object`): un valor por nodo, `[nodos, 1]`. Se obtiene también sumando la de atributos por fila.
- **Importancia de aristas** (`edge_mask_type = object`): un valor por arista, `[aristas]`, por tipo de relación.

**Advertencias.** La importancia mide asociación dentro del modelo, no causalidad, y no es evidencia del dominio. Los pesos de atención (`AttentionExplainer`) no se interpretan como explicación por omisión. Aquí los modelos están sin entrenar y los datos son sintéticos: los valores no tienen significado biológico.

## `homo_sage`

- Capas que reciben máscara de aristas: 0; la predicción cambia al pasar las máscaras de 1 a 0: no.
- Tripletas sin convolución (no influyen; se omiten): `host|exhibits|phenotype`, `metabolite|associated_with|phenotype`; quitarlas no cambia la predicción: sí.

| Método | Estado | Máscara de nodos | Máscara de aristas | Valores no nulos (nodos · aristas) | Detalle |
|---|---|---|---|---|---|
| GNNExplainer | error | attributes | object | — | ValueError: Could not compute gradients for edge masks of type '('diet', 'provides', 'substrate')'. Please make sure that edge masks are used inside the model or disable it via `edge_mask_type=None`. |
| GNNExplainer (solo atributos) | ok | attributes | — | 31/39 · 0/0 | — |
| GNNExplainer (solo nodos) | ok | object | — | 25/25 · 0/0 | — |
| Captum IntegratedGradients | error | attributes | object | — | RuntimeError: The differentiated Tensor at index 6 appears to not have been used in the graph. Set allow_unused=True if this is the desired behavior. |
| Captum Saliency | ok | attributes | — | 39/39 · 0/0 | — |
| AttentionExplainer | error | — | object | — | ValueError: Could not collect any attention coefficients. Please ensure that your model is using attention-based GNN layers. |
| PGExplainer | invalid | — | object | 0/0 · 68/91 | las máscaras de aristas no llegan a ninguna capa del modelo (o no cambian la predicción): los valores devueltos no explican la predicción. |

## `hetero_sage`

- Capas que reciben máscara de aristas: 17; la predicción cambia al pasar las máscaras de 1 a 0: sí.
- Tripletas sin convolución (no influyen; se omiten): `host|exhibits|phenotype`, `metabolite|associated_with|phenotype`; quitarlas no cambia la predicción: sí.

| Método | Estado | Máscara de nodos | Máscara de aristas | Valores no nulos (nodos · aristas) | Detalle |
|---|---|---|---|---|---|
| GNNExplainer | ok | attributes | object | 31/39 · 91/91 | — |
| GNNExplainer (solo atributos) | ok | attributes | — | 31/39 · 0/0 | — |
| GNNExplainer (solo nodos) | ok | object | — | 25/25 · 0/0 | — |
| Captum IntegratedGradients | ok | attributes | object | 31/39 · 91/91 | — |
| Captum Saliency | ok | attributes | — | 39/39 · 0/0 | — |
| AttentionExplainer | invalid | — | object | 0/0 · 0/0 | se pidió máscara de aristas, pero la explicación no la contiene. |
| PGExplainer | ok | — | object | 0/0 · 68/91 | — |

## `hetero_gat`

- Capas que reciben máscara de aristas: 17; la predicción cambia al pasar las máscaras de 1 a 0: sí.
- Tripletas sin convolución (no influyen; se omiten): `host|exhibits|phenotype`, `metabolite|associated_with|phenotype`; quitarlas no cambia la predicción: sí.

| Método | Estado | Máscara de nodos | Máscara de aristas | Valores no nulos (nodos · aristas) | Detalle |
|---|---|---|---|---|---|
| GNNExplainer | ok | attributes | object | 31/39 · 91/91 | — |
| GNNExplainer (solo atributos) | ok | attributes | — | 31/39 · 0/0 | — |
| GNNExplainer (solo nodos) | ok | object | — | 25/25 · 0/0 | — |
| Captum IntegratedGradients | ok | attributes | object | 31/39 · 91/91 | — |
| Captum Saliency | ok | attributes | — | 39/39 · 0/0 | — |
| AttentionExplainer | ok | — | object | 0/0 · 91/91 | — |
| PGExplainer | ok | — | object | 0/0 · 89/91 | — |

