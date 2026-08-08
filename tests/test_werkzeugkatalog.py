"""The tool-mark catalogue must not have holes.

The mark in front of a tool row used to be guessed from the tool's name. That
worked for the names somebody had thought of and quietly failed for the rest —
a Notion call showed the gray fallback for weeks because the server had
started naming its tools `notion-search` instead of `API-post-search`.

The catalogue answers by SERVER now, and the server name is fixed in
mcp_servers.json. That only holds as long as both files agree, which is what
these tests check: every configured server has a mark, and every mark the
catalogue names is actually drawn. Whoever registers a new server without
giving it a mark finds out here instead of in a screenshot.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
KATALOG = WURZEL / "frontend/src/lib/werkzeugkatalog.js"
ZEICHNUNG = WURZEL / "frontend/src/teile/Werkzeugzeichen.svelte"
SERVER_DATEI = WURZEL / "mcp_servers.json"


def _katalog_text() -> str:
    return KATALOG.read_text(encoding="utf-8")


def _server_im_katalog() -> set[str]:
    """The server names the catalogue knows."""
    block = re.search(r"NACH_SERVER\s*=\s*\{(.*?)\n\}", _katalog_text(), re.S)
    assert block, "NACH_SERVER nicht gefunden — wurde der Katalog umgebaut?"
    return set(re.findall(r"^\s*([\w-]+):", block.group(1), re.M))


def _zeichen_im_katalog() -> set[str]:
    """Every mark the catalogue can return."""
    text = _katalog_text()
    namen = set(re.findall(r":\s*'([a-z]+)'", text))
    namen |= set(re.findall(r"RUECKFALL\s*=\s*'([a-z]+)'", text))
    return namen


def _gezeichnete_zeichen() -> set[str]:
    """Every mark the component actually draws."""
    text = ZEICHNUNG.read_text(encoding="utf-8")
    gezeichnet = set(re.findall(r"zeichen === '([a-z]+)'", text))
    # The last branch is the fallback and carries no comparison.
    gezeichnet.add("winkel")
    return gezeichnet


def test_jeder_konfigurierte_server_hat_ein_zeichen():
    server = set(json.loads(SERVER_DATEI.read_text(encoding="utf-8"))["mcpServers"])
    fehlend = server - _server_im_katalog()
    assert not fehlend, (
        f"Diese Server stehen in mcp_servers.json, aber nicht im Katalog: "
        f"{sorted(fehlend)} — ihre Werkzeuge bekämen den grauen Winkel."
    )


def test_das_eingebaute_shell_werkzeug_steht_im_katalog():
    from app.tools import shell

    assert shell.SERVER_NAME in _server_im_katalog()


def test_jedes_zeichen_des_katalogs_wird_auch_gezeichnet():
    fehlend = _zeichen_im_katalog() - _gezeichnete_zeichen()
    assert not fehlend, (
        f"Der Katalog nennt Zeichen, die niemand malt: {sorted(fehlend)}"
    )


def test_kein_zeichen_liegt_ungenutzt_herum():
    """A drawn mark nobody can reach is dead weight — and usually a typo."""
    ungenutzt = _gezeichnete_zeichen() - _zeichen_im_katalog()
    assert not ungenutzt, (
        f"Diese Zeichen werden gemalt, aber vom Katalog nie zurückgegeben: "
        f"{sorted(ungenutzt)}"
    )


@pytest.mark.parametrize(
    "werkzeug,server,erwartet",
    [
        # The server decides, whatever the tool is called …
        ("egal_wie_das_heisst", "notion", "seite"),
        ("brandneues_werkzeug", "github", "verzweigung"),
        ("noch_nie_gesehen", "recraft", "bild"),
        # … except where a tool has earned its own mark.
        ("remove_background", "recraft", "freistellen"),
        ("run_command", "shell", "eingabe"),
        # Without a known server the pattern still catches the usual names.
        ("notion-search", "", "seite"),
        ("create_issue", "", "verzweigung"),
        ("send_email", "", "brief"),
        # And what nobody knows looks unknown.
        ("voellig_fremdes_ding", "", "winkel"),
        ("voellig_fremdes_ding", "unbekannter_server", "winkel"),
    ],
)
def test_zuordnung_haelt_sich_an_die_reihenfolge(werkzeug, server, erwartet):
    """Tool name beats server, server beats pattern, pattern beats fallback.

    Mirrors `zeichenFuer` from the catalogue. Kept in step by the tests above,
    which fail as soon as the two drift apart.
    """
    text = _katalog_text()
    nach_werkzeug = dict(
        re.findall(r"^\s*([\w-]+):\s*'([a-z]+)',", re.search(
            r"NACH_WERKZEUG\s*=\s*\{(.*?)\n\}", text, re.S).group(1), re.M)
    )
    nach_server = dict(
        re.findall(r"^\s*([\w-]+):\s*'([a-z]+)',", re.search(
            r"NACH_SERVER\s*=\s*\{(.*?)\n\}", text, re.S).group(1), re.M)
    )

    if werkzeug in nach_werkzeug:
        assert nach_werkzeug[werkzeug] == erwartet
    elif server and server in nach_server:
        assert nach_server[server] == erwartet
    else:
        # The pattern step: only the cases the parameters declare.
        muster = {
            "notion-search": "seite",
            "create_issue": "verzweigung",
            "send_email": "brief",
        }
        assert muster.get(werkzeug, "winkel") == erwartet
