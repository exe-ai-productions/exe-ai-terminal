#!/usr/bin/env python3
"""The MCP protocol over standard input and output.

Its own module because every server in this folder speaks the same protocol
and differs only in the tools it offers. What is left here is the part with
no opinion: read a line, answer it, write it back.

A server built on this stays standalone — it depends on nothing from the
terminal and can be registered in any other MCP-capable program.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Awaitable, Callable

PROTOKOLL_VERSION = "2025-06-18"

Ausfuehrer = Callable[[str, dict[str, Any]], Awaitable[str]]


def _antwort(kennung: Any, ergebnis: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": kennung, "result": ergebnis}


def _fehler(kennung: Any, code: int, nachricht: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": kennung, "error": {"code": code, "message": nachricht}}


async def anfrage_behandeln(
    nachricht: dict[str, Any],
    servername: str,
    version: str,
    werkzeuge: list[dict[str, Any]],
    ausfuehren: Ausfuehrer,
) -> dict[str, Any] | None:
    methode = nachricht.get("method")
    kennung = nachricht.get("id")
    parameter = nachricht.get("params") or {}

    if methode == "initialize":
        return _antwort(
            kennung,
            {
                "protocolVersion": PROTOKOLL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": servername, "version": version},
            },
        )

    if methode in ("notifications/initialized", "initialized"):
        return None  # notifications are not answered

    if methode == "tools/list":
        return _antwort(kennung, {"tools": werkzeuge})

    if methode == "tools/call":
        name = parameter.get("name", "")
        argumente = parameter.get("arguments") or {}
        try:
            text = await ausfuehren(name, argumente)
            return _antwort(kennung, {"content": [{"type": "text", "text": text}]})
        except Exception as fehler:  # noqa: BLE001 - the error belongs in the result, not in a crash
            return _antwort(
                kennung,
                {
                    "content": [{"type": "text", "text": f"Error: {fehler}"}],
                    "isError": True,
                },
            )

    if methode == "ping":
        return _antwort(kennung, {})

    if kennung is None:
        return None
    return _fehler(kennung, -32601, f"Unbekannte Methode: {methode}")


async def _zeilen(): # -> AsyncIterator[bytes]
    """Standard input, line by line, on every system.

    Windows needs its own way in. Its event loop hands every read to the
    completion port, and a standard handle cannot be registered there —
    the attempt fails with "invalid handle" and the server stays mute until
    the caller's handshake times out. Reading the pipe in a worker thread
    sidesteps the completion port entirely; everywhere else the loop reads
    the pipe directly, which is cheaper and long proven.
    """
    if sys.platform == "win32":
        while True:
            zeile = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not zeile:
                return
            yield zeile
    else:
        schleife = asyncio.get_running_loop()
        leser = asyncio.StreamReader()
        await schleife.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(leser), sys.stdin
        )
        while True:
            zeile = await leser.readline()
            if not zeile:
                return
            yield zeile


async def bedienen(
    servername: str,
    version: str,
    werkzeuge: list[dict[str, Any]],
    ausfuehren: Ausfuehrer,
) -> None:
    """Serves requests until standard input closes."""
    async for rohzeile in _zeilen():
        text = rohzeile.decode("utf-8", "replace").strip()
        if not text:
            continue
        try:
            nachricht = json.loads(text)
        except json.JSONDecodeError:
            continue

        antwort = await anfrage_behandeln(
            nachricht, servername, version, werkzeuge, ausfuehren
        )
        if antwort is not None:
            sys.stdout.write(json.dumps(antwort, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def starten(
    servername: str,
    version: str,
    werkzeuge: list[dict[str, Any]],
    ausfuehren: Ausfuehrer,
) -> None:
    """The whole main program of a server in this folder."""
    try:
        asyncio.run(bedienen(servername, version, werkzeuge, ausfuehren))
    except KeyboardInterrupt:
        pass
