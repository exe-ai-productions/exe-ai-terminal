"""Opening a folder in the system's file manager.

The counterpart of the folder dialog: that one brings a path in, this one
shows where a path leads. Whoever fetches models wants to see what has
accumulated — and the fastest honest answer is the folder itself, in the
file manager the system already has.

Three systems, three built-in commands:

* macOS   — ``open``
* Windows — ``explorer``
* Linux   — ``xdg-open``; may be missing on a machine without a desktop,
            which is why the caller gets a clean no instead of a stack trace.

The command is fired and forgotten. ``explorer`` in particular returns exit
codes that mean nothing, so nobody waits for one — the folder window either
appears or the system said no immediately.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


class OeffnenNichtMoeglich(Exception):
    """This system has no way to show a folder."""


def _befehl() -> list[str] | None:
    if sys.platform == "darwin":
        return ["open"]
    if sys.platform.startswith("win"):
        return ["explorer"]
    if shutil.which("xdg-open"):
        return ["xdg-open"]
    return None


def ordner_oeffnen(pfad: Path) -> None:
    """Shows the folder in the file manager, creating it if it is not there.

    Creating first is deliberate: the model folder exists only after the
    first download, but the button that leads here exists before — and a
    button that errors on a fresh machine would be wrong exactly once, at
    the worst moment.
    """
    befehl = _befehl()
    if befehl is None:
        raise OeffnenNichtMoeglich()
    ziel = Path(pfad).expanduser()
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.Popen(
            [*befehl, str(ziel)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as fehler:
        log.warning("Ordner nicht zu öffnen: %s", fehler)
        raise OeffnenNichtMoeglich() from None
