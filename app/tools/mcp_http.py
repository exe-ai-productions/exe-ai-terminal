"""Client for MCP servers over HTTP ("Streamable HTTP", MCP 2025-06-18).

Hosted servers (GitHub, Notion, Recraft …) don't run as a subprocess but
somewhere on the network. The protocol is the same JSON-RPC as over
standard input, just as a POST to ONE address:

    POST <url>       one request; the answer comes directly as JSON or —
                     depending on the server — as text/event-stream (SSE)
    Mcp-Session-Id   assigned by the server at initialize and carried along
                     with every request from then on
    DELETE <url>     ends the session when stopping (best effort)

Deliberately NO permanently open connection:
request/response only. An open connection would be needed for a server to
report changes to its tool list on its own — but the list is captured at
connect time, so a report would go nowhere.

At this build stage, authentication uses a fixed key from the .env
(``api_key_env`` on the server entry) as ``Authorization: Bearer``. The
browser sign-in (OAuth) is the next build step and docks on here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.tools.mcp_client import (
    MCPFehler,
    MCPWerkzeug,
    PROTOKOLL_VERSION,
    ergebnis_zu_text,
    werkzeuge_aus_antwort,
)

log = logging.getLogger(__name__)


class _SitzungVerfallen(Exception):
    """The server no longer knows the Mcp-Session-Id (404) — sign in again."""


class _NichtAngemeldet(Exception):
    """The server rejects the access (401/403)."""

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


class MCPHttpClient:
    """Talks to a hosted MCP server over Streamable HTTP."""

    def __init__(
        self,
        name: str,
        url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        token_erneuern=None,
    ) -> None:
        self.name = name
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        # If the access dies mid-run (401), this callback fetches a fresh
        # one once — the registry's OAuth renewal. None means: fixed key,
        # there is nothing to renew.
        self.token_erneuern = token_erneuern
        # For tests only: an ASGITransport instead of a real network. This
        # way the proof runs against a real MCP server in the test process —
        # real protocol, no mock-up, no open port.
        self._transport = transport

        self._client: httpx.AsyncClient | None = None
        self._sitzung: str | None = None
        self._protokoll: str | None = None
        self._zaehler = 0
        self.werkzeuge: list[MCPWerkzeug] = []

    @property
    def laeuft(self) -> bool:
        return self._client is not None

    # --- Connection ------------------------------------------------------

    async def starten(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=self.timeout, transport=self._transport
        )
        antwort = await self._initialisieren()
        log.info(
            "MCP-Server '%s' verbunden (http): %s",
            self.name,
            (antwort.get("serverInfo") or {}).get("name", "unbekannt"),
        )
        self.werkzeuge = await self._werkzeuge_holen()

    async def _initialisieren(self) -> dict[str, Any]:
        """The handshake: initialize, remember the session, report initialized."""
        try:
            antwort = await self._einmal_aufrufen(
                "initialize",
                {
                    "protocolVersion": PROTOKOLL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "exe-ai-terminal", "version": "0.1.0"},
                },
            )
        except _NichtAngemeldet as fehler:
            # At startup the registry supplies the access fresh — if the
            # server rejects it anyway, another attempt won't help.
            raise self._anmeldefehler(fehler.status) from None
        # From now on every request carries the negotiated version in its
        # header — not yet on initialize itself, that's where it is
        # negotiated in the first place.
        self._protokoll = antwort.get("protocolVersion") or PROTOKOLL_VERSION
        await self._benachrichtigen("notifications/initialized")
        return antwort

    async def stoppen(self) -> None:
        if self._client is None:
            return
        if self._sitzung:
            # Best effort — if the DELETE fails, the session simply
            # expires by itself on the server side.
            try:
                await self._client.delete(self.url, headers=self._koepfe())
            except httpx.HTTPError:
                pass
        await self._client.aclose()
        self._client = None
        self._sitzung = None
        self._protokoll = None

    # --- JSON-RPC over HTTP ----------------------------------------------

    def _koepfe(self) -> dict[str, str]:
        koepfe = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._protokoll:
            koepfe["MCP-Protocol-Version"] = self._protokoll
        if self._sitzung:
            koepfe["Mcp-Session-Id"] = self._sitzung
        if self.api_key:
            koepfe["Authorization"] = f"Bearer {self.api_key}"
        return koepfe

    def _anmeldefehler(self, status: int) -> MCPFehler:
        return MCPFehler(
            f"MCP-Server '{self.name}': nicht angemeldet "
            f"(HTTP {status}) — Schlüssel bzw. Anmeldung prüfen"
        )

    async def _aufrufen(self, methode: str, parameter: dict[str, Any]) -> dict[str, Any]:
        sitzung_erneuert = False
        token_erneuert = False
        while True:
            try:
                return await self._einmal_aufrufen(methode, parameter)
            except _SitzungVerfallen:
                # The server discarded the session (restart, timeout).
                # Sign in again completely once and repeat the request —
                # if that fails too, the error is real and becomes visible.
                if sitzung_erneuert:
                    raise MCPFehler(
                        f"MCP-Server '{self.name}': die Sitzung lässt sich "
                        "nicht erneuern"
                    ) from None
                sitzung_erneuert = True
                log.info("MCP '%s': Sitzung verfallen — melde neu an", self.name)
                self._sitzung = None
                self._protokoll = None
                await self._initialisieren()
            except _NichtAngemeldet as fehler:
                # The access died mid-run (OAuth tokens usually last an
                # hour): renew silently once, then repeat. If that fails,
                # the CALLER gets the error text — the run does not die.
                if token_erneuert or self.token_erneuern is None:
                    raise self._anmeldefehler(fehler.status) from None
                token_erneuert = True
                neu = await self.token_erneuern()
                if not neu:
                    raise self._anmeldefehler(fehler.status) from None
                log.info("MCP '%s': Zugang erneuert nach HTTP %d", self.name, fehler.status)
                self.api_key = neu

    async def _einmal_aufrufen(self, methode: str, parameter: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise MCPFehler(f"MCP-Server '{self.name}' läuft nicht")
        self._zaehler += 1
        kennung = self._zaehler
        nachricht = {"jsonrpc": "2.0", "id": kennung, "method": methode, "params": parameter}

        # stream instead of post: an SSE response may be ended as soon as
        # our answer was in it — a server that keeps the connection open
        # would otherwise pin us down until the timeout.
        async with self._client.stream(
            "POST",
            self.url,
            content=json.dumps(nachricht, ensure_ascii=False).encode("utf-8"),
            headers=self._koepfe(),
        ) as antwort:
            sitzung = antwort.headers.get("mcp-session-id")
            if sitzung:
                self._sitzung = sitzung

            if antwort.status_code in (401, 403):
                raise _NichtAngemeldet(antwort.status_code)
            if antwort.status_code == 404 and self._sitzung and methode != "initialize":
                raise _SitzungVerfallen()
            if antwort.status_code >= 400:
                text = (await antwort.aread())[:300].decode("utf-8", "replace")
                raise MCPFehler(
                    f"{self.name}/{methode}: HTTP {antwort.status_code} — {text.strip()}"
                )

            typ = antwort.headers.get("content-type", "")
            if typ.startswith("text/event-stream"):
                daten = await self._sse_antwort(antwort, kennung)
            else:
                daten = json.loads(await antwort.aread())

        if "error" in daten:
            fehler = daten["error"]
            raise MCPFehler(f"{self.name}/{methode}: {fehler.get('message', fehler)}")
        return daten.get("result") or {}

    async def _sse_antwort(self, antwort: httpx.Response, kennung: int) -> dict[str, Any]:
        """Reads the event stream until the answer to OUR request arrives.

        Other messages in the stream (notifications, requests from the
        server) are skipped over — this variant works strictly
        request/response.
        """
        datenzeilen: list[str] = []
        async for zeile in antwort.aiter_lines():
            if zeile.startswith("data:"):
                datenzeilen.append(zeile[5:].lstrip())
                continue
            if zeile.strip():
                continue  # event:, id:, retry:, comments — not of interest
            if not datenzeilen:
                continue
            try:
                nachricht = json.loads("\n".join(datenzeilen))
            except json.JSONDecodeError:
                nachricht = None
            datenzeilen = []
            if (
                isinstance(nachricht, dict)
                and nachricht.get("id") == kennung
                and ("result" in nachricht or "error" in nachricht)
            ):
                return nachricht
        raise MCPFehler(
            f"{self.name}: der Ereignis-Strom endete ohne Antwort auf die Anfrage"
        )

    async def _benachrichtigen(self, methode: str, parameter: dict | None = None) -> None:
        if self._client is None:
            raise MCPFehler(f"MCP-Server '{self.name}' läuft nicht")
        antwort = await self._client.post(
            self.url,
            content=json.dumps(
                {"jsonrpc": "2.0", "method": methode, "params": parameter or {}},
                ensure_ascii=False,
            ).encode("utf-8"),
            headers=self._koepfe(),
        )
        # 202 Accepted is the spec's normal case.
        if antwort.status_code >= 400:
            raise MCPFehler(
                f"{self.name}/{methode}: HTTP {antwort.status_code} — "
                f"{antwort.text[:300].strip()}"
            )

    # --- Tools -----------------------------------------------------------

    async def _werkzeuge_holen(self) -> list[MCPWerkzeug]:
        ergebnis = await self._aufrufen("tools/list", {})
        return werkzeuge_aus_antwort(ergebnis, self.name)

    async def werkzeug_aufrufen(
        self, name: str, argumente: dict[str, Any], bild_senke=None
    ) -> str:
        """Executes a tool and returns the result as text."""
        ergebnis = await self._aufrufen(
            "tools/call", {"name": name, "arguments": argumente}
        )
        return ergebnis_zu_text(ergebnis, f"{self.name}/{name}", bild_senke)
