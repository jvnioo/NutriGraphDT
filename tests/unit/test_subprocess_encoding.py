"""Los tests que leen la salida de un script como UTF-8 se la piden en UTF-8 (#246).

En Windows, un proceso hijo de Python escribe stdout y stderr con la codificación de la consola
(por ejemplo cp1252), y leerla con `encoding="utf-8"` falla en el hilo lector con
`UnicodeDecodeError` ante la primera tilde. Por eso cada archivo de tests que llama a
`subprocess.run(..., encoding="utf-8")` debe pasar `PYTHONIOENCODING=utf-8` al proceso.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]


def _decodes_utf8(call: ast.Call) -> bool:
    return any(
        keyword.arg == "encoding"
        and isinstance(keyword.value, ast.Constant)
        and str(keyword.value.value).lower().replace("-", "") == "utf8"
        for keyword in call.keywords
    )


def test_every_utf8_subprocess_reader_sets_pythonioencoding() -> None:
    offenders = []
    for path in sorted(TESTS.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        calls = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and _decodes_utf8(node)
        ]
        if calls and "PYTHONIOENCODING" not in source:
            offenders.append(f"{path.relative_to(TESTS)}:{calls[0].lineno}")
    assert offenders == []
