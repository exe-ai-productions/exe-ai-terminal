"""MCP over HTTP (Streamable HTTP): transport, session, authentication.

The proof runs against a real, tiny MCP server over the real protocol —
as an ASGI application directly in the test process, with no open port and
no network (httpx.ASGITransport). Same philosophy as test_werkzeuge.py:
protocol instead of mock.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app.tools.mcp_client import MCPFehler, ergebnis_zu_text
from app.tools.mcp_http import MCPHttpClient
from app.tools.registry import ServerEintrag, WerkzeugRegistry, konfiguration_pruefen


class EchoServer:
    """A tiny MCP server over Streamable HTTP.

    Switchable: key requirement, SSE responses, and a one-time 404 to prove
    that an expired session gets re-initialized.
    """

    def __init__(self, schluessel: str | None = None, als_sse: bool = False) -> None:
        self.schluessel = schluessel
        self.als_sse = als_sse
        self.einmal_404 = False
        self.initialisierungen = 0
        self.gesehene_protokollversionen: list[str | None] = []

    def app(self) -> Starlette:
        return Starlette(routes=[Route("/mcp", self.mcp, methods=["POST", "DELETE"])])

    @property
    def _sitzung(self) -> str:
        return f"sitzung-{self.initialisierungen}"

    async def mcp(self, request: Request) -> Response:
        if self.schluessel is not None:
            if request.headers.get("authorization") != f"Bearer {self.schluessel}":
                return Response(status_code=401)
        if request.method == "DELETE":
            return Response(status_code=204)

        nachricht = json.loads(await request.body())
        methode = nachricht.get("method")
        kennung = nachricht.get("id")

        if methode == "initialize":
            self.initialisierungen += 1
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": kennung,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "http-testserver"},
                    },
                },
                headers={"Mcp-Session-Id": self._sitzung},
            )

        # From here on: without the current session, the server doesn't know you.
        if request.headers.get("mcp-session-id") != self._sitzung:
            return Response(status_code=404)
        self.gesehene_protokollversionen.append(
            request.headers.get("mcp-protocol-version")
        )

        if methode == "notifications/initialized":
            return Response(status_code=202)

        if self.einmal_404:
            self.einmal_404 = False
            return Response(status_code=404)

        if methode == "tools/list":
            ergebnis = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Gibt den Text zurück.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                        },
                    }
                ]
            }
        elif methode == "tools/call":
            argumente = (nachricht.get("params") or {}).get("arguments") or {}
            if argumente.get("kaputt"):
                ergebnis = {
                    "content": [{"type": "text", "text": "absichtlich kaputt"}],
                    "isError": True,
                }
            elif argumente.get("als_bild"):
                # Like Recraft: text with a link plus a Base64 preview alongside.
                ergebnis = {
                    "content": [
                        {"type": "text", "text": "Generated 1 image."},
                        {
                            "type": "image",
                            "mimeType": "image/webp",
                            "data": base64.b64encode(b"winzige-webp-bytes").decode(),
                        },
                    ]
                }
            else:
                ergebnis = {
                    "content": [
                        {"type": "text", "text": f"echo: {argumente.get('text', '')}"}
                    ]
                }
        else:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": kennung,
                    "error": {"code": -32601, "message": f"unbekannt: {methode}"},
                }
            )

        antwort = {"jsonrpc": "2.0", "id": kennung, "result": ergebnis}
        if self.als_sse:
            koerper = f"event: message\ndata: {json.dumps(antwort)}\n\n"
            return Response(koerper, media_type="text/event-stream")
        return JSONResponse(antwort)


def klient(server: EchoServer, api_key: str | None = None) -> MCPHttpClient:
    return MCPHttpClient(
        name="test",
        url="http://testserver/mcp",
        api_key=api_key,
        transport=httpx.ASGITransport(app=server.app()),
    )


# --- The transport -------------------------------------------------------


async def test_start_holt_werkzeuge_und_fuehrt_sitzung():
    server = EchoServer()
    k = klient(server)
    await k.starten()
    try:
        assert [w.name for w in k.werkzeuge] == ["echo"]
        text = await k.werkzeug_aufrufen("echo", {"text": "hallo"})
        assert text == "echo: hallo"
        # After the handshake, every request carries the negotiated version.
        assert set(server.gesehene_protokollversionen) == {"2025-06-18"}
    finally:
        await k.stoppen()
    assert not k.laeuft


async def test_sse_antwort_wird_gelesen():
    server = EchoServer(als_sse=True)
    k = klient(server)
    await k.starten()
    try:
        text = await k.werkzeug_aufrufen("echo", {"text": "strom"})
        assert text == "echo: strom"
    finally:
        await k.stoppen()


async def test_schluessel_wird_als_bearer_mitgeschickt():
    server = EchoServer(schluessel="geheim")
    k = klient(server, api_key="geheim")
    await k.starten()
    try:
        assert [w.name for w in k.werkzeuge] == ["echo"]
    finally:
        await k.stoppen()


async def test_ohne_schluessel_kommt_eine_klare_meldung():
    server = EchoServer(schluessel="geheim")
    k = klient(server)
    with pytest.raises(MCPFehler, match="nicht angemeldet"):
        await k.starten()


async def test_verfallene_sitzung_wird_still_erneuert():
    server = EchoServer()
    k = klient(server)
    await k.starten()
    try:
        server.einmal_404 = True
        text = await k.werkzeug_aufrufen("echo", {"text": "wieder da"})
        assert text == "echo: wieder da"
        assert server.initialisierungen == 2
    finally:
        await k.stoppen()


async def test_toter_zugang_mitten_im_lauf_wird_einmal_erneuert():
    """OAuth case: the provider rotates the key, the call survives."""
    server = EchoServer(schluessel="alt")
    erneuert = []

    async def frisch():
        erneuert.append(True)
        return "neu"

    k = MCPHttpClient(
        name="test",
        url="http://testserver/mcp",
        api_key="alt",
        transport=httpx.ASGITransport(app=server.app()),
        token_erneuern=frisch,
    )
    await k.starten()
    try:
        server.schluessel = "neu"  # from now on the old access is dead
        text = await k.werkzeug_aufrufen("echo", {"text": "lebt noch"})
        assert text == "echo: lebt noch"
        assert erneuert == [True]
        assert k.api_key == "neu"
    finally:
        await k.stoppen()


async def test_toter_zugang_ohne_erneuerung_meldet_sich_klar():
    server = EchoServer(schluessel="alt")
    k = klient(server, api_key="alt")
    await k.starten()
    try:
        server.schluessel = "anders"
        with pytest.raises(MCPFehler, match="nicht angemeldet"):
            await k.werkzeug_aufrufen("echo", {"text": "x"})
    finally:
        await k.stoppen()


async def test_bild_wird_ueber_die_senke_gesichert():
    """The real chain: the server delivers an image block, the sink receives it."""
    server = EchoServer()
    k = klient(server)
    gesichert = []

    def senke(mime, daten):
        gesichert.append((mime, daten))
        return "werkzeug-test.webp"

    await k.starten()
    try:
        text = await k.werkzeug_aufrufen("echo", {"als_bild": True}, bild_senke=senke)
        assert "[image saved: werkzeug-test.webp]" in text
        assert "Generated 1 image." in text
        (eintrag,) = gesichert
        assert eintrag[0] == "image/webp"
        assert base64.b64decode(eintrag[1]) == b"winzige-webp-bytes"
    finally:
        await k.stoppen()


async def test_kaputte_senke_laesst_das_ergebnis_leben():
    server = EchoServer()
    k = klient(server)

    def senke(mime, daten):
        raise OSError("Platte voll")

    await k.starten()
    try:
        text = await k.werkzeug_aufrufen("echo", {"als_bild": True}, bild_senke=senke)
        assert "[image preview omitted, image/webp]" in text
    finally:
        await k.stoppen()


def test_bild_vorschau_wird_nicht_als_rohtext_durchgereicht():
    """Recraft's Base64 preview must flood neither the chat nor the model context."""
    ergebnis = {
        "content": [
            {"type": "text", "text": "Generated 1 image. Original: https://x.invalid/bild.webp"},
            {"type": "image", "mimeType": "image/webp", "data": "A" * 50_000},
        ]
    }
    text = ergebnis_zu_text(ergebnis, "recraft/generate_image")
    assert "AAAA" not in text
    assert "[image preview omitted, image/webp]" in text
    assert "https://x.invalid/bild.webp" in text


def test_binaer_ressource_wird_nicht_als_rohtext_durchgereicht():
    ergebnis = {
        "content": [
            {"type": "resource", "resource": {"uri": "res://datei", "blob": "B" * 10_000}},
        ]
    }
    text = ergebnis_zu_text(ergebnis, "test/lesen")
    assert "BBBB" not in text
    assert "[binary resource omitted, res://datei]" in text


async def test_kaputtes_werkzeug_meldet_fehler():
    server = EchoServer()
    k = klient(server)
    await k.starten()
    try:
        with pytest.raises(MCPFehler, match="absichtlich kaputt"):
            await k.werkzeug_aufrufen("echo", {"kaputt": True})
    finally:
        await k.stoppen()


# --- The registry knows the build type ------------------------------------


def test_registry_baut_http_client(monkeypatch):
    monkeypatch.setenv("TEST_MCP_SCHLUESSEL", "geheim")
    registry = WerkzeugRegistry([])
    client = registry._client_bauen(
        ServerEintrag(
            name="gehostet",
            type="http",
            url="https://beispiel.invalid/mcp",
            api_key_env="TEST_MCP_SCHLUESSEL",
        )
    )
    assert isinstance(client, MCPHttpClient)
    assert client.api_key == "geheim"


def test_registry_ueberspringt_http_ohne_gesetzten_schluessel(monkeypatch):
    monkeypatch.delenv("TEST_MCP_SCHLUESSEL", raising=False)
    registry = WerkzeugRegistry([])
    client = registry._client_bauen(
        ServerEintrag(
            name="gehostet",
            type="http",
            url="https://beispiel.invalid/mcp",
            api_key_env="TEST_MCP_SCHLUESSEL",
        )
    )
    assert client is None


def test_registry_ueberspringt_http_ohne_url():
    registry = WerkzeugRegistry([])
    assert registry._client_bauen(ServerEintrag(name="kaputt", type="http")) is None


def test_registry_ueberspringt_unbekannten_typ():
    registry = WerkzeugRegistry([])
    assert registry._client_bauen(ServerEintrag(name="fremd", type="websocket")) is None


# --- The form validation knows the new fields ------------------------------


def _konfig(server: dict) -> str:
    return json.dumps({"mcpServers": {"eintrag": server}})


def test_pruefung_erlaubt_http_mit_url_und_schluesselname():
    text = _konfig(
        {"type": "http", "url": "https://beispiel.invalid/mcp", "api_key_env": "KEY"}
    )
    assert konfiguration_pruefen(text) is None


def test_pruefung_meldet_unbekannten_typ():
    meldung = konfiguration_pruefen(_konfig({"type": "websocket"}))
    assert meldung is not None and "unbekannter Typ" in meldung


def test_pruefung_meldet_http_ohne_url():
    meldung = konfiguration_pruefen(_konfig({"type": "http"}))
    assert meldung is not None and "braucht eine 'url'" in meldung


def test_pruefung_meldet_falsche_feldarten():
    meldung = konfiguration_pruefen(_konfig({"type": "http", "url": 5}))
    assert meldung is not None and "'url'" in meldung
    meldung = konfiguration_pruefen(
        _konfig({"type": "http", "url": "https://x.invalid", "api_key_env": 5})
    )
    assert meldung is not None and "'api_key_env'" in meldung
