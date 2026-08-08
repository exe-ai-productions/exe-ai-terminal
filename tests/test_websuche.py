"""The shipped web search: what it offers, and where it must not reach.

Two servers can serve the search — the bundled library and a self-hosted
SearXNG. The point of the tests below is that swapping one for the other
stays invisible: same tool names, same guard.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

from app.tools import server_lesen

# The servers live next to each other in mcp/ and import each other by plain
# name, exactly as they do when started as a subprocess from the project root.
MCP_ORDNER = Path(__file__).resolve().parent.parent / "mcp"
if str(MCP_ORDNER) not in sys.path:
    sys.path.insert(0, str(MCP_ORDNER))

ddgs_server = importlib.import_module("ddgs_server")
searxng_server = importlib.import_module("searxng_server")
webseite_lesen = importlib.import_module("webseite_lesen")


# --- What is shipped ------------------------------------------------------


def test_die_suche_wird_angeschaltet_ausgeliefert():
    eintraege = server_lesen(Path("mcp_servers.json"))
    suche = next(e for e in eintraege if e.name == "websuche")
    # A search that ships switched off is a search nobody finds.
    assert suche.enabled is True
    assert suche.allowed_tools == ["web_search", "read_webpage"]


def test_die_suche_braucht_keine_geheimnisse():
    eintraege = server_lesen(Path("mcp_servers.json"))
    suche = next(e for e in eintraege if e.name == "websuche")
    # No placeholder in the environment means nothing to fill in before the
    # first search — that is the whole reason this variant is the shipped one.
    assert not any("${" in wert for wert in (suche.env or {}).values())


# --- The swap has to stay invisible ---------------------------------------


def test_beide_server_bieten_dieselben_werkzeuge():
    namen = ["web_search", "read_webpage"]
    assert [w["name"] for w in ddgs_server.WERKZEUGE] == namen
    assert [w["name"] for w in searxng_server.WERKZEUGE] == namen


def test_beide_server_teilen_sich_dieselbe_sperre():
    # Not two copies that drift apart: one module, used twice.
    assert ddgs_server.webseite_lesen is searxng_server.webseite_lesen


# --- Where read_webpage must not reach ------------------------------------


@pytest.mark.parametrize(
    "adresse",
    [
        "http://127.0.0.1:8090/api/v1/chats",
        "http://localhost:8090/",
        "http://[::1]:8090/",
        "http://192.168.1.1/",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data/",  # the cloud metadata address
        "http://100.64.111.94:8770/",  # a tailnet, outside is_private
    ],
)
def test_innen_bleibt_innen(adresse: str):
    assert webseite_lesen.zeigt_nach_innen(adresse) is True


def test_ein_name_der_nicht_aufloest_gilt_als_verdaechtig():
    assert webseite_lesen.zeigt_nach_innen("http://gibtsganzsicherhiernicht.invalid/") is True


def test_ohne_wirt_gilt_als_innen():
    assert webseite_lesen.zeigt_nach_innen("http:///pfad") is True


@pytest.mark.parametrize("adresse", ["ftp://example.org/datei", "file:///etc/passwd", "beispiel.de"])
def test_nur_http_und_https_werden_gelesen(adresse: str):
    antwort = asyncio.run(webseite_lesen.lesen(adresse))
    assert antwort.startswith("Error:")
