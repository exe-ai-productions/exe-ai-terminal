"""Client for MCP servers (Model Context Protocol).

MCP servers are standalone programs that offer tools. The protocol is
JSON-RPC 2.0, line by line over standard input and output. The flow is
always the same:

    initialize            -> handshake, who can do what
    notifications/initialized
    tools/list            -> which tools exist
    tools/call            -> execute a tool

The second variant — hosted servers over HTTP — lives in ``mcp_http.py``
and speaks the same JSON-RPC. What both variants share (tool type, error
type, translating the responses) lives here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

PROTOKOLL_VERSION = "2025-06-18"


class MCPFehler(Exception):
    """Error while talking to an MCP server."""


@dataclass
class MCPWerkzeug:
    """A tool as the server offers it."""

    name: str
    beschreibung: str
    schema: dict[str, Any] = field(default_factory=dict)
    server: str = ""

    def als_openai_werkzeug(self) -> dict[str, Any]:
        """Translates into the format the models understand."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.beschreibung,
                "parameters": self.schema or {"type": "object", "properties": {}},
            },
        }


def werkzeuge_aus_antwort(ergebnis: dict[str, Any], server: str) -> list[MCPWerkzeug]:
    """Translates a ``tools/list`` response — the same for both variants."""
    return [
        MCPWerkzeug(
            name=eintrag["name"],
            beschreibung=eintrag.get("description", ""),
            schema=eintrag.get("inputSchema") or {},
            server=server,
        )
        for eintrag in ergebnis.get("tools", [])
    ]


def ergebnis_zu_text(ergebnis: dict[str, Any], quelle: str, bild_senke=None) -> str:
    """Turns a ``tools/call`` response into text for the model.

    ``quelle`` is "server/tool" — it appears in the error message when the
    server reports ``isError``.

    ``bild_senke``: accepts (mimeType, base64 data), saves the image and
    returns the file name — the chat run attaches it to the message.
    Without a sink (jobs, tests) only a short note remains.
    """
    teile: list[str] = []
    for eintrag in ergebnis.get("content", []):
        if eintrag.get("type") == "text":
            teile.append(eintrag.get("text", ""))
        elif eintrag.get("type") == "image":
            # Recraft and co. attach previews as base64. These must NEVER
            # be passed through as raw text: tens of thousands of characters
            # flood the chat and eat the model context. With a sink the
            # image is saved and displayed, without one the note remains.
            name = None
            if bild_senke is not None:
                try:
                    name = bild_senke(
                        eintrag.get("mimeType") or "image/png",
                        eintrag.get("data") or "",
                    )
                except Exception:  # noqa: BLE001 - a broken image must not shoot down the result
                    log.exception("Werkzeug-Bild von %s ließ sich nicht sichern", quelle)
            if name:
                teile.append(f"[image saved: {name}]")
            else:
                teile.append(
                    f"[image preview omitted, {eintrag.get('mimeType', 'image')}]"
                )
        elif isinstance((eintrag.get("resource") or {}).get("blob"), str):
            # The same for embedded binary resources.
            teile.append(f"[binary resource omitted, {eintrag['resource'].get('uri', '')}]")
        else:
            teile.append(json.dumps(eintrag, ensure_ascii=False))
    text = "\n".join(teile) if teile else json.dumps(ergebnis, ensure_ascii=False)

    if ergebnis.get("isError"):
        raise MCPFehler(f"{quelle}: {text}")
    return text


class MCPStdioClient:
    """Talks to an MCP server running as a subprocess."""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        arbeitsverzeichnis: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.arbeitsverzeichnis = arbeitsverzeichnis
        self.timeout = timeout

        self._prozess: asyncio.subprocess.Process | None = None
        self._zaehler = 0
        self._schreibsperre = asyncio.Lock()
        self.werkzeuge: list[MCPWerkzeug] = []

    @property
    def laeuft(self) -> bool:
        return self._prozess is not None and self._prozess.returncode is None

    # --- Connection ------------------------------------------------------

    async def starten(self) -> None:
        umgebung = {**os.environ, **self.env}
        self._prozess = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=umgebung,
            cwd=self.arbeitsverzeichnis,
            # JSON-RPC is line-based, and a tool list arrives as ONE line —
            # over 64 KiB for the Notion server, more than asyncio's default
            # buffer. Without the higher limit, readline() breaks off with
            # LimitOverrunError and the server counts as broken.
            limit=10 * 1024 * 1024,
        )

        antwort = await self._aufrufen(
            "initialize",
            {
                "protocolVersion": PROTOKOLL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "exe-ai-terminal", "version": "0.1.0"},
            },
        )
        log.info(
            "MCP-Server '%s' verbunden: %s",
            self.name,
            (antwort.get("serverInfo") or {}).get("name", "unbekannt"),
        )
        await self._benachrichtigen("notifications/initialized")
        self.werkzeuge = await self._werkzeuge_holen()

    async def stoppen(self) -> None:
        if self._prozess is None:
            return
        if self._prozess.returncode is None:
            self._prozess.terminate()
            try:
                await asyncio.wait_for(self._prozess.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._prozess.kill()
                await self._prozess.wait()
        self._prozess = None

    # --- JSON-RPC --------------------------------------------------------

    async def _senden(self, nachricht: dict[str, Any]) -> None:
        if self._prozess is None or self._prozess.stdin is None:
            raise MCPFehler(f"MCP-Server '{self.name}' läuft nicht")
        zeile = json.dumps(nachricht, ensure_ascii=False) + "\n"
        self._prozess.stdin.write(zeile.encode("utf-8"))
        await self._prozess.stdin.drain()

    async def _zeile_lesen(self) -> dict[str, Any]:
        if self._prozess is None or self._prozess.stdout is None:
            raise MCPFehler(f"MCP-Server '{self.name}' läuft nicht")
        while True:
            rohzeile = await self._prozess.stdout.readline()
            if not rohzeile:
                fehlertext = ""
                if self._prozess.stderr is not None:
                    fehlertext = (await self._prozess.stderr.read(2000)).decode(
                        "utf-8", "replace"
                    )
                raise MCPFehler(
                    f"MCP-Server '{self.name}' hat die Verbindung beendet. {fehlertext.strip()}"
                )
            text = rohzeile.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Some servers write log lines to standard output.
                log.debug("MCP '%s' — keine JSON-Zeile: %r", self.name, text[:200])

    async def _aufrufen(self, methode: str, parameter: dict[str, Any]) -> dict[str, Any]:
        async with self._schreibsperre:
            self._zaehler += 1
            kennung = self._zaehler
            await self._senden(
                {"jsonrpc": "2.0", "id": kennung, "method": methode, "params": parameter}
            )

            while True:
                antwort = await asyncio.wait_for(self._zeile_lesen(), timeout=self.timeout)
                if antwort.get("id") != kennung:
                    continue  # notification or answer to something else
                if "error" in antwort:
                    fehler = antwort["error"]
                    raise MCPFehler(
                        f"{self.name}/{methode}: {fehler.get('message', fehler)}"
                    )
                return antwort.get("result") or {}

    async def _benachrichtigen(self, methode: str, parameter: dict | None = None) -> None:
        async with self._schreibsperre:
            await self._senden(
                {"jsonrpc": "2.0", "method": methode, "params": parameter or {}}
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
