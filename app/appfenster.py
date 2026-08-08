"""Opening the interface as its own window instead of a browser tab.

Chromium-family browsers can show a page as a plain window — no address
bar, no tabs, an entry of its own in the Dock or task bar (``--app=``).
That is the difference between "a tab in my browser" and "a program on my
machine", and it costs nothing: no bundled engine, no new dependency,
only the browser the machine already has.

Windows always ships Edge, so the window is native there by default. On
macOS and Linux somebody without a Chromium-family browser gets the
normal browser tab instead — exactly what happened before, so nobody
ends up worse than today.

A second start opens a second window rather than fronting the first;
``--app`` windows have no single-window rule. That is the honest price
of the tab-less look, and a closed window costs one click.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# macOS keeps applications in fixed places; PATH knows nothing about them.
_MAC_KANDIDATEN = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

# Windows installs Edge with the system; Chrome lands in one of two places.
_WIN_KANDIDATEN = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# Everywhere else the PATH is the honest register.
_PATH_KANDIDATEN = [
    "chromium",
    "chromium-browser",
    "google-chrome",
    "microsoft-edge",
    "brave-browser",
]


def _programm() -> str | None:
    feste = (
        _MAC_KANDIDATEN
        if sys.platform == "darwin"
        else _WIN_KANDIDATEN if sys.platform == "win32" else []
    )
    for pfad in feste:
        if Path(pfad).is_file():
            return pfad
    for name in _PATH_KANDIDATEN:
        gefunden = shutil.which(name)
        if gefunden:
            return gefunden
    return None


def oeffnen(url: str) -> bool:
    """The page as its own window. True when such a window opened."""
    programm = _programm()
    if programm is None:
        return False
    try:
        subprocess.Popen(
            [programm, f"--app={url}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
