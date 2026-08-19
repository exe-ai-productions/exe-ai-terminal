#!/usr/bin/env python3
"""The one program, in whichever role it was asked for.

Packaged into a single file there is no interpreter left to start a helper
with — so the program is its own helper. Called plainly it serves the
terminal and opens the interface; called with ``--mcp <name>`` it becomes the
tool server it would otherwise have started as a separate script.

That is why this file exists at all and why it stays this short: it is the
only place that decides which of the two the program is going to be, and it
must decide before anything heavy is imported.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Packaged without a console — the normal case on Windows, where a double
# click opens no terminal — Python hands out None for the standard streams
# instead of a file. Everything that asks a stream a question then dies on
# it: uvicorn's log formatter asks isatty() before the service ever starts.
# A sink costs nothing and keeps every later import honest, so it happens
# here, before anything heavy is imported.
if sys.stdout is None or sys.stderr is None:
    import os

    _leerlauf = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _leerlauf
    if sys.stderr is None:
        sys.stderr = _leerlauf

# The tool servers live next to each other and import each other by plain
# name, exactly as they do when started as separate scripts.
WURZEL = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
for ordner in (WURZEL, WURZEL / "mcp"):
    if str(ordner) not in sys.path:
        sys.path.insert(0, str(ordner))

# Which name reaches which server. A list and not a guess from the name: a
# switch that accepts anything would let a command line pick what runs.
MCP_SERVER = {
    "websuche": "ddgs_server",
    "searxng": "searxng_server",
}


def _mcp_bedienen(name: str) -> int:
    modul_name = MCP_SERVER.get(name)
    if modul_name is None:
        print(f"Unbekannter Werkzeugserver: {name}", file=sys.stderr)
        return 2

    import importlib

    import mcp_schleife

    modul = importlib.import_module(modul_name)
    mcp_schleife.starten(
        name, "0.1.0", modul.WERKZEUGE, modul.werkzeug_ausfuehren
    )
    return 0


def _orte_zeigen() -> int:
    """Where this program keeps things — asked more often than one expects.

    A packaged program hides its folders by design, and the first question
    when something is missing is always the same one.
    """
    from app import paketierung

    print(f"eingefroren: {paketierung.ist_eingefroren()}")
    print(f"programm:    {paketierung.programmpfad()}")
    print(f"mitgeliefert:{paketierung.ressourcen()}")
    print(f"eigene Daten:{paketierung.daten()}")
    return 0


def _antwortet(port: int) -> bool:
    """Is something already serving on that port?"""
    import socket

    with socket.socket() as verbindung:
        verbindung.settimeout(0.4)
        return verbindung.connect_ex(("127.0.0.1", port)) == 0


def _browser_oeffnen(port: int) -> None:
    """Opens the interface once the service answers.

    Started by a double click, the program has to show something — a window
    that only prints log lines looks like a program that failed. Waiting for
    the port and not for a fixed number of seconds: a first start sets up a
    database and takes longer than a second one.

    Preferably as a window of its own (app/appfenster.py); the plain
    browser tab is the fallback for machines without one.
    """
    import os
    import time
    import webbrowser

    from app.appfenster import oeffnen

    # The native shell sets this when it starts the service as its sidecar:
    # the shell already is the window, a second one would greet every user
    # twice.
    if os.environ.get("EXE_AI_TERMINAL_HEADLESS"):
        return

    ende = time.time() + 30
    while time.time() < ende:
        if _antwortet(port):
            adresse = f"http://127.0.0.1:{port}/app/"
            if not oeffnen(adresse):
                webbrowser.open(adresse)
            return
        time.sleep(0.3)


def _terminal_bedienen() -> int:
    import threading

    import uvicorn

    from app.config import get_config

    konfiguration = get_config()
    port = konfiguration.app.port

    # A second double click should not start a second service and fail on the
    # port. It brings the window forward instead — which is what somebody
    # clicking again actually wants.
    if _antwortet(port):
        _browser_oeffnen(port)
        return 0

    threading.Thread(target=_browser_oeffnen, args=(port,), daemon=True).start()
    uvicorn.run(
        "app.main:app",
        host=konfiguration.app.host,
        port=port,
        reload=False,
    )
    return 0


def main(argumente: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argumente is None else argumente)
    if argv and argv[0] == "--wo":
        return _orte_zeigen()
    if argv and argv[0] == "--mcp":
        if len(argv) < 2:
            print("--mcp braucht einen Namen", file=sys.stderr)
            return 2
        return _mcp_bedienen(argv[1])
    return _terminal_bedienen()


if __name__ == "__main__":
    raise SystemExit(main())
