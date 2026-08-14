"""`ask_user` — the model asks, the run waits.

Two halves, and both matter:

* the **check**, because a question with six options would arrive in a
  window that can only show four, and the two missing ones would silently
  never be offered,
* the **flow**, because the answer has to come back as the tool's result —
  a click and a typed sentence alike. If that link broke, the model would
  ask and then carry on as if nobody had said anything.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.providers import MockProvider, mock_endpunkt
from app.providers.base import Werkzeugaufruf
from app.tools import frage_werkzeug
from tests.conftest import provider_setzen


# --- The check -------------------------------------------------------------


def test_eine_frage_ohne_optionen_ist_erlaubt():
    frage, optionen = frage_werkzeug.gepruefte_frage({"question": "Welcher Weg?"})
    assert frage == "Welcher Weg?"
    assert optionen == []


def test_optionen_behalten_ihre_reihenfolge():
    _, optionen = frage_werkzeug.gepruefte_frage(
        {
            "question": "Welcher Weg?",
            "options": [
                {"label": "A", "description": "empfohlen"},
                {"label": "B"},
            ],
        }
    )
    assert [o["label"] for o in optionen] == ["A", "B"]
    assert optionen[0]["description"] == "empfohlen"
    assert optionen[1]["description"] == ""


def test_ohne_frage_geht_nichts():
    with pytest.raises(frage_werkzeug.FrageUngueltig):
        frage_werkzeug.gepruefte_frage({"question": "   "})


def test_mehr_als_vier_optionen_werden_abgelehnt():
    """Refused, not trimmed: trimming would show the user four of six and
    tell nobody about the other two."""
    with pytest.raises(frage_werkzeug.FrageUngueltig) as fehler:
        frage_werkzeug.gepruefte_frage(
            {
                "question": "Welcher Weg?",
                "options": [{"label": str(n)} for n in range(5)],
            }
        )
    assert "4" in str(fehler.value)


def test_eine_option_ohne_beschriftung_ist_keine():
    with pytest.raises(frage_werkzeug.FrageUngueltig):
        frage_werkzeug.gepruefte_frage(
            {"question": "Welcher Weg?", "options": [{"description": "ohne Namen"}]}
        )


# --- The flow through the chat ---------------------------------------------


class FrageRegistry:
    """Offers ask_user and nothing else. It is never executed — that is the
    point of the tool."""

    def __init__(self, client=None, antwort=None):
        self.ausgefuehrt = []
        self._client = client
        self._antwort = antwort

    def als_openai_werkzeuge(self):
        return [{"type": "function", "function": {"name": "ask_user", "parameters": {}}}]

    def braucht_bestaetigung(self, name, argumente=None, ordner=None):
        # The answer is armed from in here, because this is the first thing
        # the run asks while its event loop is turning.
        if self._antwort is not None:
            _spaeter_antworten(self._client, self._antwort)
        return False

    def server_von(self, name):
        return "shell"

    def bestaetigungsgrund(self, name, argumente=None, ordner=None):
        return ""

    async def ausfuehren(self, name, argumente, bild_senke=None, ordner=None, chat_id=None):
        self.ausgefuehrt.append(name)
        return "sollte nie passieren"


def _spaeter_antworten(client, antwort):
    """Simulates the click, or the typed sentence — both travel one route."""
    verwaltung = client.app.state.generierungen

    def versuchen():
        for generierung in verwaltung.laufende():
            for aufruf_id in list(generierung.bestaetigungen):
                verwaltung.bestaetigen(generierung.id, aufruf_id, True, antwort)
                return True
        return False

    def takt():
        if not versuchen():
            asyncio.get_running_loop().call_later(0.01, takt)

    asyncio.get_running_loop().call_later(0.01, takt)


def _fragendes_modell(client, argumente, antwort=None):
    registry = FrageRegistry(client, antwort)
    client.app.state.werkzeuge = registry
    client.app.state.config.features.mcp = True
    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"),
            haeppchen=["Gut."],
            werkzeugaufrufe=[Werkzeugaufruf(id="a1", name="ask_user", argumente=argumente)],
        ),
    )
    return registry


def _ereignisse(antwort):
    return [
        json.loads(z[5:].strip()) for z in antwort.text.splitlines() if z.startswith("data:")
    ]


def test_die_frage_geht_raus_und_die_antwort_kommt_zurueck(client, chat_id):
    registry = _fragendes_modell(
        client,
        {"question": "Welcher Weg?", "options": [{"label": "Links"}, {"label": "Rechts"}]},
        antwort="Links",
    )

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "entscheide"},
    )
    ereignisse = _ereignisse(antwort)

    frage = next(e for e in ereignisse if e["typ"] == "user_ask")
    assert frage["frage"] == "Welcher Weg?"
    assert [o["label"] for o in frage["optionen"]] == ["Links", "Rechts"]

    ergebnis = next(e for e in ereignisse if e["typ"] == "tool_result")
    assert ergebnis["text"] == "Links"
    assert ergebnis["fehlgeschlagen"] is False
    # Never executed: there is nothing to execute.
    assert registry.ausgefuehrt == []


def test_freier_text_zaehlt_genauso(client, chat_id):
    _fragendes_modell(
        client,
        {"question": "Welcher Weg?", "options": [{"label": "Links"}]},
        antwort="Keins von beidem, nimm den dritten",
    )

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "entscheide"},
    )
    ergebnis = next(e for e in _ereignisse(antwort) if e["typ"] == "tool_result")
    assert ergebnis["text"] == "Keins von beidem, nimm den dritten"


def test_eine_kaputte_frage_wird_dem_modell_gesagt(client, chat_id):
    """Five options never reach the window — the model is told why instead."""
    _fragendes_modell(
        client,
        {"question": "Welcher Weg?", "options": [{"label": str(n)} for n in range(5)]},
    )

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "entscheide"},
    )
    ereignisse = _ereignisse(antwort)
    assert not any(e["typ"] == "user_ask" for e in ereignisse)
    ergebnis = next(e for e in ereignisse if e["typ"] == "tool_result")
    assert ergebnis["fehlgeschlagen"] is True
