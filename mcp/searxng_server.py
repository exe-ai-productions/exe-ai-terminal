#!/usr/bin/env python3
"""MCP server for web search via a self-hosted SearXNG instance.

Offers the same two tools as every search server here:

    web_search      searches and returns hits with title, snippet, address
    read_webpage    fetches one of those addresses and returns the text

Search first, then decide what is interesting, then read up — that is the
difference from a plain page fetch.

This is the variant for anyone running their own instance. It reaches
further than the shipped one — a SearXNG asks hundreds of engines instead
of a handful — but it needs that instance to exist, so it is not what a
fresh installation starts with.

The server is deliberately standalone with no dependency on the terminal:
it speaks MCP over standard input and output and can therefore be
registered in any other MCP-capable program as well.

Configuration via environment variables:
    SEARXNG_URL        address of the instance (default: http://127.0.0.1:8888)
    SUCHE_MAX_TREFFER  how many hits at most (default: 8)
    ABRUF_MAX_ZEICHEN  how much text per page at most (see webseite_lesen)
"""

from __future__ import annotations

import os
from typing import Any

import httpx

import mcp_schleife
import webseite_lesen

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8888").rstrip("/")
MAX_TREFFER = int(os.getenv("SUCHE_MAX_TREFFER", "8"))

WERKZEUGE = [
    {
        "name": "web_search",
        "description": (
            "Searches the web and returns a list of results with title, snippet "
            "and address. For current events, facts, and anything that happened "
            "after the model's knowledge cutoff."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for.",
                },
                "language": {
                    "type": "string",
                    "description": "Language code such as 'de' or 'en'. Default: all.",
                },
                "count": {
                    "type": "integer",
                    "description": f"How many results, at most {MAX_TREFFER}.",
                },
            },
            "required": ["query"],
        },
    },
    webseite_lesen.WERKZEUG,
]


async def websuche(suchbegriff: str, sprache: str | None = None, anzahl: int | None = None) -> str:
    grenze = min(anzahl or MAX_TREFFER, MAX_TREFFER)
    parameter: dict[str, Any] = {"q": suchbegriff, "format": "json"}
    if sprache:
        parameter["language"] = sprache

    async with httpx.AsyncClient(timeout=20) as client:
        antwort = await client.get(f"{SEARXNG_URL}/search", params=parameter)
        antwort.raise_for_status()
        daten = antwort.json()

    treffer = daten.get("results", [])[:grenze]
    if not treffer:
        return f"No results for: {suchbegriff}"

    zeilen = [f"Results for “{suchbegriff}”:", ""]
    for nummer, eintrag in enumerate(treffer, start=1):
        zeilen.append(f"{nummer}. {eintrag.get('title', 'untitled')}")
        zeilen.append(f"   {eintrag.get('url', '')}")
        if ausschnitt := (eintrag.get("content") or "").strip():
            zeilen.append(f"   {ausschnitt[:300]}")
        zeilen.append("")

    if antworten := daten.get("answers"):
        zeilen.append("Direct answers: " + "; ".join(str(a) for a in antworten))

    return "\n".join(zeilen).strip()


async def werkzeug_ausfuehren(name: str, argumente: dict[str, Any]) -> str:
    # English identifier on the outside, German source code on the inside.
    if name == "web_search":
        return await websuche(
            argumente["query"],
            argumente.get("language"),
            argumente.get("count"),
        )
    if name == "read_webpage":
        return await webseite_lesen.lesen(argumente["url"])
    raise ValueError(f"Unbekanntes Werkzeug: {name}")


if __name__ == "__main__":
    mcp_schleife.starten("searxng-web", "0.1.0", WERKZEUGE, werkzeug_ausfuehren)
