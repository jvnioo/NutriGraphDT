"""Enlaces del README y del índice de `docs/` (A120-P3, #354).

- Ningún enlace relativo de `README.md` ni de `docs/README.md` está roto.
- Todo documento Markdown de `docs/` aparece en el índice `docs/README.md`.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
LINK = re.compile(r"\]\((<[^>]+>|[^)\s]+)")


def _targets(text: str) -> list[str]:
    targets = []
    for raw in LINK.findall(text):
        target = raw[1:-1] if raw.startswith("<") else raw
        target = unquote(target.split("#", 1)[0])
        if target and not re.match(r"^[a-z]+:", target):
            targets.append(target)
    return targets


def _broken(document: Path) -> list[str]:
    text = document.read_text(encoding="utf-8")
    return [t for t in _targets(text) if not (document.parent / t).exists()]


def test_readme_links_resolve() -> None:
    assert _broken(REPO_ROOT / "README.md") == []


def test_docs_index_links_resolve() -> None:
    assert _broken(DOCS / "README.md") == []


def test_every_document_is_in_the_index() -> None:
    linked = {
        (DOCS / target).resolve() for target in _targets((DOCS / "README.md").read_text("utf-8"))
    }
    documents = {p.resolve() for p in DOCS.rglob("*.md") if p != DOCS / "README.md"}
    missing = sorted(str(p.relative_to(DOCS)) for p in documents - linked)
    assert missing == []
