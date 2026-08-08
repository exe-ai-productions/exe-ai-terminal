#!/usr/bin/env python3
"""MCP server for web search without any instance of our own.

Offers the same two tools as every search server here:

    web_search      searches and returns hits with title, snippet, address
    read_webpage    fetches one of those addresses and returns the text

The difference from the SearXNG server is only where the hits come from.
This one carries its search inside: a library in the same process, no
second service, no address to configure, nothing for the user to install.
That is what makes it the one that ships — it works on the first start, on
every system.

It asks several search engines and merges what comes back. None of them
promises to answer: on too many requests in a short time they refuse, and
the tool says so instead of pretending the web is empty. One person at a
terminal is far away from those limits; a server hammering in a loop is not.

Configuration via environment variables:
    SUCHE_MAX_TREFFER  how many hits at most (default: 8)
    SUCHE_QUELLEN      which engines to ask, comma separated
    ABRUF_MAX_ZEICHEN  how much text per page at most (see webseite_lesen)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import mcp_schleife
import webseite_lesen
from ddgs import DDGS

MAX_TREFFER = int(os.getenv("SUCHE_MAX_TREFFER", "8"))

# Several engines rather than one: if a single one refuses or goes quiet,
# the others still answer. Left to itself the library picks per request, and
# that pick has a habit of running into limits.
QUELLEN = os.getenv("SUCHE_QUELLEN", "duckduckgo, brave, mojeek")

# The library wants a market, not a language. Anything unlisted searches the
# whole world, which is the honest answer for a language we cannot place.
_MAERKTE = {
    "de": "de-de",
    "en": "us-en",
    "fr": "fr-fr",
    "es": "es-es",
    "it": "it-it",
    "nl": "nl-nl",
    "pt": "pt-pt",
    "pl": "pl-pl",
}

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


def _suchen(suchbegriff: str, markt: str, grenze: int) -> list[dict[str, Any]]:
    """The blocking search, meant for a worker thread."""
    return DDGS().text(
        suchbegriff,
        region=markt,
        backend=QUELLEN,
        max_results=grenze,
    )


async def websuche(
    suchbegriff: str, sprache: str | None = None, anzahl: int | None = None
) -> str:
    grenze = min(anzahl or MAX_TREFFER, MAX_TREFFER)
    markt = _MAERKTE.get((sprache or "").lower(), "wt-wt")

    # The library brings its own HTTP client and blocks. Without the thread
    # it would stop the event loop for the whole duration of the search.
    treffer = await asyncio.to_thread(_suchen, suchbegriff, markt, grenze)

    if not treffer:
        return f"No results for: {suchbegriff}"

    zeilen = [f"Results for “{suchbegriff}”:", ""]
    for nummer, eintrag in enumerate(treffer[:grenze], start=1):
        zeilen.append(f"{nummer}. {eintrag.get('title', 'untitled')}")
        zeilen.append(f"   {eintrag.get('href', '')}")
        if ausschnitt := (eintrag.get("body") or "").strip():
            zeilen.append(f"   {ausschnitt[:300]}")
        zeilen.append("")

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
    mcp_schleife.starten("exe-web-search", "0.1.0", WERKZEUGE, werkzeug_ausfuehren)
