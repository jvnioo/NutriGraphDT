"""Tests del registro de fuentes `configs/sources.json` (A34-1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.loaders import SourceMetadata

SOURCES_PATH = Path(__file__).resolve().parents[2] / "configs" / "sources.json"


def test_every_registered_source_is_valid() -> None:
    sources = load_sources(SOURCES_PATH)
    assert "synthetic-v1" in sources
    for source_id, metadata in sources.items():
        assert isinstance(metadata, SourceMetadata)
        assert metadata.source_id == source_id
        assert metadata.path_or_url
        assert metadata.format


def test_default_source_is_registered() -> None:
    data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    assert data["default_source"] in load_sources(SOURCES_PATH)


def test_key_must_match_source_id(tmp_path: Path) -> None:
    data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    data["sources"]["renamed"] = data["sources"].pop("synthetic-v1")
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="renamed"):
        load_sources(path)


def test_sources_must_be_an_object(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text('{"sources": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="sources"):
        load_sources(path)
