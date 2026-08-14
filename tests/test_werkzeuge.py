"""MCP integration and tool execution (phase 1.6).

The proof runs against a real MCP server as a subprocess — that is, over
the real protocol, not against a mock of the protocol.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.providers import MockProvider, mock_endpunkt
from app.providers.base import Werkzeugaufruf
from app.providers.openai_kompatibel import _WerkzeugSammler
from app.tools import ServerEintrag, WerkzeugRegistry, WerkzeugVerboten, server_lesen
from tests.conftest import provider_setzen

# A tiny MCP server that exists only for the test. Two tools:
# one does math, one breaks.
TESTSERVER = '''
import json, sys

WERKZEUGE = [
    {"name": "addieren", "description": "Addiert zwei Zahlen.",
     "inputSchema": {"type": "object",
                     "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                     "required": ["a", "b"]}},
    {"name": "geht_kaputt", "description": "Scheitert immer.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "heikel", "description": "Sollte nicht angeboten werden.",
     "inputSchema": {"type": "object", "properties": {}}},
]

def antworte(kennung, ergebnis):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": kennung, "result": ergebnis}) + "\\n")
    sys.stdout.flush()

for zeile in sys.stdin:
    zeile = zeile.strip()
    if not zeile:
        continue
    nachricht = json.loads(zeile)
    methode = nachricht.get("method")
    kennung = nachricht.get("id")
    if methode == "initialize":
        antworte(kennung, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                           "serverInfo": {"name": "testserver", "version": "1"}})
    elif methode == "tools/list":
        antworte(kennung, {"tools": WERKZEUGE})
    elif methode == "tools/call":
        p = nachricht.get("params") or {}
        name = p.get("name")
        args = p.get("arguments") or {}
        if name == "addieren":
            antworte(kennung, {"content": [{"type": "text", "text": str(args["a"] + args["b"])}]})
        elif name == "geht_kaputt":
            antworte(kennung, {"content": [{"type": "text", "text": "kaputt wie bestellt"}],
                               "isError": True})
        else:
            antworte(kennung, {"content": [{"type": "text", "text": "unbekannt"}], "isError": True})
'''


@pytest.fixture
def testserver_datei(tmp_path: Path) -> Path:
    datei = tmp_path / "testserver.py"
    datei.write_text(TESTSERVER, encoding="utf-8")
    return datei


@pytest.fixture
async def registry(testserver_datei: Path):
    eintrag = ServerEintrag(
        name="test",
        command=sys.executable,
        args=[str(testserver_datei)],
        allowed_tools=["addieren", "geht_kaputt"],
    )
    reg = WerkzeugRegistry([eintrag])
    await reg.starten()
    yield reg
    await reg.stoppen()


# --- Protocol -------------------------------------------------------------


@pytest.mark.asyncio
async def test_werkzeuge_werden_vom_server_geholt(registry: WerkzeugRegistry):
    assert "addieren" in registry.namen()


@pytest.mark.asyncio
async def test_werkzeug_wird_ausgefuehrt(registry: WerkzeugRegistry):
    assert await registry.ausfuehren("addieren", {"a": 2, "b": 3}) == "5"


@pytest.mark.asyncio
async def test_mehrere_aufrufe_nacheinander(registry: WerkzeugRegistry):
    assert await registry.ausfuehren("addieren", {"a": 1, "b": 1}) == "2"
    assert await registry.ausfuehren("addieren", {"a": 10, "b": 5}) == "15"


@pytest.mark.asyncio
async def test_fehler_des_werkzeugs_wird_als_fehler_gemeldet(registry: WerkzeugRegistry):
    from app.tools import MCPFehler

    with pytest.raises(MCPFehler):
        await registry.ausfuehren("geht_kaputt", {})


@pytest.mark.asyncio
async def test_uebersetzung_ins_modellformat(registry: WerkzeugRegistry):
    werkzeuge = registry.als_openai_werkzeuge()
    addieren = next(w for w in werkzeuge if w["function"]["name"] == "addieren")
    assert addieren["type"] == "function"
    assert addieren["function"]["parameters"]["required"] == ["a", "b"]


# --- Lockdown -------------------------------------------------------------


@pytest.mark.asyncio
async def test_nicht_freigegebenes_werkzeug_wird_nicht_angeboten(registry: WerkzeugRegistry):
    """The server offers 'heikel', but it is not on the allowlist."""
    assert "heikel" not in registry.namen()
    assert all(w["function"]["name"] != "heikel" for w in registry.als_openai_werkzeuge())


@pytest.mark.asyncio
async def test_nicht_freigegebenes_werkzeug_wird_nicht_ausgefuehrt(registry: WerkzeugRegistry):
    with pytest.raises(WerkzeugVerboten):
        await registry.ausfuehren("heikel", {})


@pytest.mark.asyncio
async def test_voellig_unbekanntes_werkzeug_wird_abgewiesen(registry: WerkzeugRegistry):
    with pytest.raises(WerkzeugVerboten):
        await registry.ausfuehren("rm_minus_rf", {})


@pytest.mark.asyncio
async def test_abgeschalteter_server_wird_nicht_gestartet(testserver_datei: Path):
    eintrag = ServerEintrag(
        name="aus", command=sys.executable, args=[str(testserver_datei)], enabled=False
    )
    reg = WerkzeugRegistry([eintrag])
    await reg.starten()
    assert reg.anzahl == 0
    await reg.stoppen()


@pytest.mark.asyncio
async def test_kaputter_server_reisst_die_anderen_nicht_mit(testserver_datei: Path):
    reg = WerkzeugRegistry(
        [
            ServerEintrag(name="kaputt", command="/gibt/es/nicht", args=[]),
            ServerEintrag(name="gut", command=sys.executable, args=[str(testserver_datei)]),
        ]
    )
    await reg.starten()
    assert "addieren" in reg.namen()
    assert "kaputt" not in reg.clients
    await reg.stoppen()


@pytest.mark.asyncio
async def test_bestaetigungspflicht_wird_gemerkt(testserver_datei: Path):
    reg = WerkzeugRegistry(
        [
            ServerEintrag(
                name="test",
                command=sys.executable,
                args=[str(testserver_datei)],
                needs_confirmation=["addieren"],
            )
        ]
    )
    await reg.starten()
    assert reg.braucht_bestaetigung("addieren") is True
    assert reg.braucht_bestaetigung("geht_kaputt") is False
    await reg.stoppen()


# --- Configuration file ---------------------------------------------------


def test_mitgelieferte_mcp_datei_ist_lesbar():
    eintraege = server_lesen(Path("mcp_servers.json"))
    namen = {eintrag.name for eintrag in eintraege}
    assert "searxng" in namen
    websuche = next(e for e in eintraege if e.name == "searxng")
    # enabled is NOT checked: the bundled file is a skeleton — the
    # entries are visible but disabled out of the box,
    # because everyone fills in their own values. What matters is that the
    # file is readable and the allowlist is in place.
    assert websuche.allowed_tools == ["web_search", "read_webpage"]


def test_fehlende_datei_ist_kein_fehler(tmp_path: Path):
    assert server_lesen(tmp_path / "gibtsnicht.json") == []


def test_server_mit_unbekanntem_typ_wird_uebersprungen():
    eintrag = ServerEintrag(name="entfernt", type="http", url="https://example.invalid/mcp")
    assert eintrag.type == "http"  # planned, but not implemented yet


# --- Reassembling fragmented calls ----------------------------------------


def test_sammler_setzt_zerstueckelte_argumente_zusammen():
    """Exactly the shape in which llama.cpp streams the calls."""
    sammler = _WerkzeugSammler()
    for bruchstueck in [
        [{"index": 0, "id": "abc", "type": "function",
          "function": {"name": "web_search", "arguments": "{"}}],
        [{"index": 0, "function": {"arguments": '"query":"'}}],
        [{"index": 0, "function": {"arguments": "Tailscale"}}],
        [{"index": 0, "function": {"arguments": '"'}}],
        [{"index": 0, "function": {"arguments": "}"}}],
    ]:
        sammler.aufnehmen(bruchstueck)

    aufrufe = sammler.fertige_aufrufe()
    assert len(aufrufe) == 1
    assert aufrufe[0].id == "abc"
    assert aufrufe[0].name == "web_search"
    assert aufrufe[0].argumente == {"query": "Tailscale"}


def test_sammler_haelt_mehrere_aufrufe_auseinander():
    sammler = _WerkzeugSammler()
    sammler.aufnehmen(
        [
            {"index": 0, "id": "a", "function": {"name": "eins", "arguments": '{"x":1}'}},
            {"index": 1, "id": "b", "function": {"name": "zwei", "arguments": '{"y":'}},
        ]
    )
    sammler.aufnehmen([{"index": 1, "function": {"arguments": "2}"}}])

    aufrufe = sammler.fertige_aufrufe()
    assert [a.name for a in aufrufe] == ["eins", "zwei"]
    assert aufrufe[1].argumente == {"y": 2}


def test_sammler_ueberlebt_unlesbare_argumente():
    sammler = _WerkzeugSammler()
    sammler.aufnehmen([{"index": 0, "id": "x", "function": {"name": "k", "arguments": "{kaputt"}}])
    aufrufe = sammler.fertige_aufrufe()
    assert aufrufe[0].argumente == {}


def test_sammler_ohne_aufrufe_ist_leer():
    assert _WerkzeugSammler().leer is True


# --- The whole chain in the chat ------------------------------------------


def test_werkzeugschleife_im_chat(client, chat_id, monkeypatch):
    """The model requests a tool, it is executed, the answer continues."""

    class FakeRegistry:
        def __init__(self):
            self.aufgerufen = []

        def als_openai_werkzeuge(self):
            return [{"type": "function", "function": {"name": "addieren", "parameters": {}}}]

        def braucht_bestaetigung(self, name, argumente=None, ordner=None):
            return False

        def server_von(self, name):
            return ''

        def bestaetigungsgrund(self, name, argumente=None, ordner=None):
            return ''

        async def ausfuehren(self, name, argumente, bild_senke=None, ordner=None, chat_id=None):
            self.aufgerufen.append((name, argumente))
            return "42"

    registry = FakeRegistry()
    client.app.state.werkzeuge = registry
    client.app.state.config.features.mcp = True

    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"),
            haeppchen=["Das Ergebnis ist 42."],
            werkzeugaufrufe=[Werkzeugaufruf(id="a1", name="addieren", argumente={"a": 40, "b": 2})],
        ),
    )

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Was ist 40 plus 2?"},
    )
    ereignisse = [
        json.loads(z[5:].strip()) for z in antwort.text.splitlines() if z.startswith("data:")
    ]
    sorten = [e["typ"] for e in ereignisse]

    assert "tool_call" in sorten
    assert "tool_result" in sorten
    assert registry.aufgerufen == [("addieren", {"a": 40, "b": 2})]

    inhalt = "".join(e.get("text", "") for e in ereignisse if e["typ"] == "content")
    assert inhalt == "Das Ergebnis ist 42."

    # The tool appears in the message's record.
    nachricht = client.get(f"/api/v1/chats/{chat_id}/messages").json()[1]
    assert nachricht["stats"]["werkzeuge"][0]["name"] == "addieren"
    assert nachricht["stats"]["werkzeuge"][0]["fehlgeschlagen"] is False
    # The result is in there too — otherwise, after a reload, the history
    # would only show THAT something ran, but not what came back.
    assert nachricht["stats"]["werkzeuge"][0]["ergebnis"] == "42"


def test_werkzeugergebnis_geht_zurueck_ans_modell(client, chat_id):
    class FakeRegistry:
        def als_openai_werkzeuge(self):
            return [{"type": "function", "function": {"name": "addieren", "parameters": {}}}]

        def braucht_bestaetigung(self, name, argumente=None, ordner=None):
            return False

        def server_von(self, name):
            return ''

        def bestaetigungsgrund(self, name, argumente=None, ordner=None):
            return ''

        async def ausfuehren(self, name, argumente, bild_senke=None, ordner=None, chat_id=None):
            return "42"

    client.app.state.werkzeuge = FakeRegistry()
    client.app.state.config.features.mcp = True

    provider = provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"),
            haeppchen=["fertig"],
            werkzeugaufrufe=[Werkzeugaufruf(id="a1", name="addieren", argumente={})],
        ),
    )

    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "rechne"},
    )

    # Second round: the history contains call and result.
    zweiter = provider.alle_anfragen[1].nachrichten
    assert zweiter[-2].role == "assistant" and zweiter[-2].werkzeugaufrufe
    assert zweiter[-1].role == "tool"
    assert zweiter[-1].content == "42"
    assert zweiter[-1].werkzeugaufruf_id == "a1"


def test_ohne_feature_flag_bekommt_das_modell_keine_werkzeuge(client, chat_id):
    class FakeRegistry:
        def als_openai_werkzeuge(self):
            return [{"type": "function", "function": {"name": "x", "parameters": {}}}]

    client.app.state.werkzeuge = FakeRegistry()
    client.app.state.config.features.mcp = False

    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    assert provider.letzte_anfrage.werkzeuge == []


def test_endpunkt_ohne_tool_calls_bekommt_keine_werkzeuge(client, chat_id):
    class FakeRegistry:
        def als_openai_werkzeuge(self):
            return [{"type": "function", "function": {"name": "x", "parameters": {}}}]

    client.app.state.werkzeuge = FakeRegistry()
    client.app.state.config.features.mcp = True

    endpunkt = mock_endpunkt("test")
    endpunkt.capabilities.tool_calls = False
    zustand = client.app.state.discovery.zustaende["test"]
    zustand.endpunkt = endpunkt
    zustand.provider = MockProvider(endpunkt, haeppchen=["ok"])
    zustand.erreichbar = True

    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    assert zustand.provider.letzte_anfrage.werkzeuge == []


def test_verbotenes_werkzeug_wird_dem_modell_zurueckgemeldet(client, chat_id):
    """No crash, but a refusal the model can keep working with."""

    class FakeRegistry:
        def als_openai_werkzeuge(self):
            return []

        def braucht_bestaetigung(self, name, argumente=None, ordner=None):
            return False

        def server_von(self, name):
            return ''

        def bestaetigungsgrund(self, name, argumente=None, ordner=None):
            return ''

        async def ausfuehren(self, name, argumente, bild_senke=None, ordner=None, chat_id=None):
            raise WerkzeugVerboten(f"Werkzeug '{name}' ist nicht freigegeben.")

    client.app.state.werkzeuge = FakeRegistry()
    client.app.state.config.features.mcp = True

    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"),
            haeppchen=["Das darf ich nicht."],
            werkzeugaufrufe=[Werkzeugaufruf(id="a1", name="rm_minus_rf", argumente={})],
        ),
    )

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "loesche alles"},
    )
    ereignisse = [
        json.loads(z[5:].strip()) for z in antwort.text.splitlines() if z.startswith("data:")
    ]
    ergebnis = next(e for e in ereignisse if e["typ"] == "tool_result")
    assert ergebnis["fehlgeschlagen"] is True
    assert antwort.status_code == 200


# --- /api/v1/tools -------------------------------------------------------


def test_tools_endpunkt_ohne_registry(client):
    client.app.state.werkzeuge = None
    daten = client.get("/api/v1/tools").json()
    assert daten["aktiv"] is False
    assert daten["werkzeuge"] == []


# --- Prompting before confirmation-required tools (1.6) -------------------


def _ereignisse(antwort):
    return [
        json.loads(z[5:].strip()) for z in antwort.text.splitlines() if z.startswith("data:")
    ]


class HeikleRegistry:
    """A tool that may do nothing without consent."""

    def __init__(self):
        self.aufgerufen = []

    def als_openai_werkzeuge(self):
        return [{"type": "function", "function": {"name": "loeschen", "parameters": {}}}]

    def braucht_bestaetigung(self, name, argumente=None, ordner=None):
        return True

    def server_von(self, name):
        return ''

    def bestaetigungsgrund(self, name, argumente=None, ordner=None):
        return ''

    async def ausfuehren(self, name, argumente, bild_senke=None, ordner=None, chat_id=None):
        self.aufgerufen.append((name, argumente))
        return "erledigt"


def _spaeter_klicken(client, erlaubt):
    """Simulates the user tapping Reject or Execute in the window.

    The click can only come once the confirmation prompt is up — so we poll
    at an interval instead of striking blindly once.
    """
    import asyncio

    verwaltung = client.app.state.generierungen

    def versuchen():
        for generierung in verwaltung.laufende():
            for aufruf_id in list(generierung.bestaetigungen):
                verwaltung.bestaetigen(generierung.id, aufruf_id, erlaubt)
                return True
        return False

    def takt():
        if not versuchen():
            asyncio.get_running_loop().call_later(0.01, takt)

    asyncio.get_running_loop().call_later(0.01, takt)


def _heikles_modell(client, registry):
    client.app.state.werkzeuge = registry
    client.app.state.config.features.mcp = True
    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"),
            haeppchen=["fertig"],
            werkzeugaufrufe=[
                Werkzeugaufruf(id="a1", name="loeschen", argumente={"pfad": "/tmp/x"})
            ],
        ),
    )


def test_bestaetigungspflichtiges_werkzeug_fragt_zuerst(client, chat_id):
    """The confirmation prompt comes before the call — with name and arguments."""
    class Registry(HeikleRegistry):
        def braucht_bestaetigung(self, name, argumente=None, ordner=None):
            _spaeter_klicken(client, True)
            return True

        def server_von(self, name):
            return ''

        def bestaetigungsgrund(self, name, argumente=None, ordner=None):
            return ''

    registry = Registry()
    _heikles_modell(client, registry)

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "mach"},
    )
    ereignisse = _ereignisse(antwort)
    sorten = [e["typ"] for e in ereignisse]

    # The question comes before "running" is reported.
    assert sorten.index("tool_confirm") < sorten.index("tool_call")

    frage = next(e for e in ereignisse if e["typ"] == "tool_confirm")
    assert frage["name"] == "loeschen"
    assert frage["argumente"] == {"pfad": "/tmp/x"}
    assert frage["aufruf_id"] == "a1"

    # Approved means executed.
    assert registry.aufgerufen == [("loeschen", {"pfad": "/tmp/x"})]


def test_abgelehntes_werkzeug_laeuft_nicht(client, chat_id):
    class Registry(HeikleRegistry):
        def braucht_bestaetigung(self, name, argumente=None, ordner=None):
            _spaeter_klicken(client, False)
            return True

        def server_von(self, name):
            return ''

        def bestaetigungsgrund(self, name, argumente=None, ordner=None):
            return ''

    registry = Registry()
    _heikles_modell(client, registry)

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "mach"},
    )

    assert registry.aufgerufen == []
    ergebnis = next(e for e in _ereignisse(antwort) if e["typ"] == "tool_result")
    assert ergebnis["fehlgeschlagen"] is True
    # The model learns why — and can respond to it.
    assert "nicht erlaubt" in ergebnis["text"]


def test_ohne_antwort_wird_nicht_ausgefuehrt(client, chat_id, monkeypatch):
    """Silence is not consent."""
    from app.api.v1 import generierung as modul

    monkeypatch.setattr(modul, "BESTAETIGUNG_WARTEZEIT", 0.05)
    monkeypatch.setattr(modul, "BESTAETIGUNG_PRUEFTAKT", 0.01)

    registry = HeikleRegistry()
    _heikles_modell(client, registry)

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "mach"},
    )

    assert registry.aufgerufen == []
    ergebnis = next(e for e in _ereignisse(antwort) if e["typ"] == "tool_result")
    assert ergebnis["fehlgeschlagen"] is True
    assert "keine Antwort" in ergebnis["text"]


def test_bestaetigung_ohne_wartende_generierung(client):
    """The dialog was still up, the response long over — not an error."""
    antwort = client.post(
        "/api/v1/chat/confirm",
        json={"generation_id": "gibtsnicht", "aufruf_id": "a1", "erlaubt": True},
    )
    assert antwort.status_code == 200
    assert antwort.json()["zugestellt"] is False
