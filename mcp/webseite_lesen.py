#!/usr/bin/env python3
"""Fetching a single web page and turning it into readable text.

Its own module because every search server offers `read_webpage`, and the
guard inside is the reason it may not be copied: it keeps the model from
reaching *inward* through an address. A second copy would mean a second
place to remember the next time a hole is found — and this guard has had
one before.

Configuration via environment variable:
    ABRUF_MAX_ZEICHEN  how much text per page at most (default: 6000)
"""

from __future__ import annotations

import html
import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

import httpx

MAX_ZEICHEN = int(os.getenv("ABRUF_MAX_ZEICHEN", "6000"))

WERKZEUG = {
    "name": "read_webpage",
    "description": (
        "Fetches a web page and returns its text content. Useful for "
        "addresses from a previous web_search."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full address, starting with http:// or https://",
            }
        },
        "required": ["url"],
    },
}

_SKRIPT = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_LEERRAUM = re.compile(r"\n{3,}")

# `is_private` does NOT cover 100.64.0.0/10 in every Python version, and a
# tailnet lives exactly there — the gap was reachable, so the range is named
# explicitly. (Tailscale over IPv6 lives in fc00::/7 and is already covered.)
_ZUSATZ_NETZE = (ipaddress.ip_network('100.64.0.0/10'),)


def zeigt_nach_innen(adresse: str) -> bool:
    """Does the address point at the server itself or into our own network?

    Without this check, `read_webpage` is a door to the inside: the model
    can be asked to read `http://127.0.0.1:2019` or a private address, and
    the server dutifully fetches it — after all, it sits inside. Checking
    the scheme is not enough, because `http://` is both.

    The resolved IP is checked, not the name: `localtest.me` and a thousand
    other names point at 127.0.0.1. If a name does not resolve, it counts as
    suspicious — better one page too few than one too many.
    """
    wirt = urlparse(adresse).hostname
    if not wirt:
        return True
    try:
        infos = socket.getaddrinfo(wirt, None)
    except OSError:
        return True
    for eintrag in infos:
        ip = ipaddress.ip_address(eintrag[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return True
        if any(ip in netz for netz in _ZUSATZ_NETZE):
            return True
    return False


async def lesen(adresse: str) -> str:
    if not adresse.startswith(("http://", "https://")):
        return "Error: the address must start with http:// or https://."

    # Redirects are followed by hand. With `follow_redirects=True` the check
    # would be worthless: the first address is public, the redirect points at
    # 127.0.0.1, and httpx follows without asking.
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (kompatibel; Exe-AI-Terminal)"},
    ) as client:
        for _ in range(5):
            if zeigt_nach_innen(adresse):
                return "Error: this address is not publicly reachable."
            antwort = await client.get(adresse)
            if antwort.status_code in (301, 302, 303, 307, 308):
                ziel = antwort.headers.get("location")
                if not ziel:
                    break
                adresse = str(antwort.url.join(ziel))
                if not adresse.startswith(("http://", "https://")):
                    return "Error: the redirect does not lead to http or https."
                continue
            break
        else:
            return "Error: too many redirects."
        antwort.raise_for_status()
        inhaltstyp = antwort.headers.get("content-type", "")
        rohtext = antwort.text

    if "html" not in inhaltstyp and "text" not in inhaltstyp:
        return f"The address returns '{inhaltstyp}', which is not readable text."

    text = _SKRIPT.sub(" ", rohtext)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = "\n".join(zeile.strip() for zeile in text.splitlines())
    text = _LEERRAUM.sub("\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    if len(text) > MAX_ZEICHEN:
        text = text[:MAX_ZEICHEN] + f"\n\n[truncated after {MAX_ZEICHEN} characters]"
    return text or "The page contains no readable text."
