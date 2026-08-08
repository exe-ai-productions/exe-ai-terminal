"""Where things are when the program is a single file.

Frozen, three assumptions of everyday development stop holding:

* **There is no Python.** Nothing can be started with `.venv/bin/python`,
  because there is no interpreter lying around — the program *is* the
  interpreter. Whatever it used to start as a separate script it now has to
  be itself, which is what the ``--mcp`` switch is for.
* **The folder is read-only.** A packaged program may not write beside
  itself; on macOS it sits in a signed bundle, and elsewhere in a place the
  user has no business writing to.
* **The working directory is somebody else's.** Started from the desktop it
  can be anything at all, so no relative path may be trusted.

So there are two folders instead of one: what ships with the program and is
only ever read, and what belongs to the user and is only ever written.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ist_eingefroren() -> bool:
    """Are we running as a packaged program rather than from source?"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def programmpfad() -> Path:
    """The program itself — what has to be called to start it again.

    Frozen this is the packaged file, in development the interpreter of the
    virtual environment. Either way it is the thing that can serve as its own
    tool server.
    """
    return Path(sys.executable)


def ressourcen() -> Path:
    """What ships with the program: interface, translations, shipped skills.

    Read only. An update replaces this folder wholesale, so nothing the user
    made may ever be kept here.
    """
    if ist_eingefroren():
        return Path(sys._MEIPASS)  # noqa: SLF001 - the name PyInstaller gives it
    return Path(__file__).resolve().parent.parent


def daten() -> Path:
    """What belongs to the user: database, settings, models, their own skills.

    In the place each system keeps such things, so a backup finds it and an
    uninstall does not take it along by accident.
    """
    if not ist_eingefroren():
        return Path(__file__).resolve().parent.parent

    if sys.platform == "darwin":
        wurzel = Path.home() / "Library" / "Application Support" / "Exe AI Terminal"
    elif sys.platform == "win32":
        wurzel = Path.home() / "AppData" / "Roaming" / "Exe AI Terminal"
    else:
        wurzel = Path.home() / ".local" / "share" / "exe-ai-terminal"

    wurzel.mkdir(parents=True, exist_ok=True)
    return wurzel


def aufloesen(pfad: str | Path, *, schreibbar: bool = False) -> Path:
    """A path from the configuration, made absolute against the right folder.

    An absolute path is left alone — somebody who wrote one meant it.
    """
    p = Path(pfad).expanduser()
    if p.is_absolute():
        return p
    return (daten() if schreibbar else ressourcen()) / p
