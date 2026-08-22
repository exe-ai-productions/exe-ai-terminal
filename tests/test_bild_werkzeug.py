"""The drawing tool — offered like the built-ins, honest without a painter."""

from __future__ import annotations

import asyncio

import pytest

from app.tools import bild_werkzeug
from app.tools.registry import WerkzeugRegistry


def test_registry_bietet_draw_image_mit_zugang(tmp_path):
    registry = WerkzeugRegistry([], bild_zugang=("http://127.0.0.1:1/api/v1", tmp_path))
    assert bild_werkzeug.WERKZEUG_NAME in registry.namen()
    offen = [w["function"]["name"] for w in registry.als_openai_werkzeuge()]
    assert bild_werkzeug.WERKZEUG_NAME in offen
    assert registry.server_von(bild_werkzeug.WERKZEUG_NAME) == bild_werkzeug.SERVER_NAME
    zeile = next(
        e for e in registry.uebersicht() if e["name"] == bild_werkzeug.WERKZEUG_NAME
    )
    assert zeile["needs_confirmation"] is False


def test_ohne_zugang_gibt_es_das_werkzeug_nicht():
    registry = WerkzeugRegistry([])
    assert bild_werkzeug.WERKZEUG_NAME not in registry.namen()
    assert registry.server_von(bild_werkzeug.WERKZEUG_NAME) == ""


def test_leerer_prompt_wird_abgewiesen(tmp_path):
    with pytest.raises(bild_werkzeug.BildWerkzeugFehler):
        asyncio.run(bild_werkzeug.ausfuehren({}, "http://127.0.0.1:1", tmp_path))


class _Antwort:
    def __init__(self, daten):
        self._daten = daten
        self.status_code = 200
        self.text = ""

    def json(self):
        return self._daten


class _Client:
    """Answers the tool's GET calls from a fixed table, no network."""

    def __init__(self, modelle):
        self._modelle = modelle

    async def __aenter__(self):
        return self

    async def __aexit__(self, *ausnahme):
        return False

    async def get(self, url, **_):
        return _Antwort(self._modelle)


def test_ohne_maler_kommt_ein_ehrlicher_satz(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bild_werkzeug.httpx,
        "AsyncClient",
        lambda timeout: _Client({"programm_da": False, "modelle": []}),
    )
    text = asyncio.run(
        bild_werkzeug.ausfuehren({"prompt": "a dog"}, "http://x", tmp_path)
    )
    assert "No image generator" in text


def test_ohne_modell_kommt_ein_ehrlicher_satz(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bild_werkzeug.httpx,
        "AsyncClient",
        lambda timeout: _Client({"programm_da": True, "modelle": []}),
    )
    text = asyncio.run(
        bild_werkzeug.ausfuehren({"prompt": "a dog"}, "http://x", tmp_path)
    )
    assert "No image model" in text
