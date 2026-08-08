"""The system's folder dialog — Finder, Explorer or GTK/KDE.

Why this works at all: the browser deliberately never hands out a real path
(`showDirectoryPicker` only yields the folder name). The service, however, runs
on the same machine as the user — and it may open the system dialog. What comes
back is a full absolute path.

As a side effect this settles the question of creating folders: every one of
these dialogs brings its own "New Folder" button. We don't have to build one.

Three systems, three built-in tools:

* macOS   — `osascript` with `choose folder`; present on every Mac.
* Windows — PowerShell with the FolderBrowserDialog from System.Windows.Forms;
            present on every Windows. Needs `-STA`, otherwise the dialog does
            not open at all (Windows Forms requires a single-threaded
            apartment thread).
* Linux   — `zenity` (GNOME) or `kdialog` (KDE). Either may be missing, which
            is exactly why the path field in the UI stays the way that works
            everywhere: in a container, on a machine without a screen, on a
            Linux without a dialog tool.

The dialog blocks for as long as it is open. It must therefore never run in
FastAPI's event loop — the caller provides a worker thread, and there is a
time limit here on top.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# How long an open dialog may wait at most. Whoever leaves it standing should
# not tie up a thread forever.
ZEITGRENZE_SEKUNDEN = 180


class DialogAbgebrochen(Exception):
    """The user closed the dialog without choosing anything."""


class DialogNichtVerfuegbar(Exception):
    """This system has no folder dialog."""


class DialogZeitueberschreitung(Exception):
    """The dialog was left open too long."""


def dialog_verfuegbar() -> str | None:
    """Name of the available dialog tool, or None.

    The UI asks this before showing the button: a button that clicks into
    nothing is worse than no button at all.
    """
    if sys.platform == "darwin":
        return "finder" if shutil.which("osascript") else None
    if sys.platform == "win32":
        return "explorer" if _windows_powershell() else None
    # Linux and everything else: without a graphical session there is nothing
    # to open, even if the tool is installed.
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    if shutil.which("zenity"):
        return "zenity"
    if shutil.which("kdialog"):
        return "kdialog"
    return None


def _windows_powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("pwsh.exe")


def ordner_waehlen(titel: str, startpfad: str | None = None) -> str:
    """Opens the system dialog and returns the chosen folder.

    Raises DialogAbgebrochen, DialogNichtVerfuegbar or
    DialogZeitueberschreitung. The returned path is absolute and resolved — it
    is still checked again on saving, because the disk may have changed
    between choosing and storing.
    """
    werkzeug = dialog_verfuegbar()
    if werkzeug is None:
        raise DialogNichtVerfuegbar()

    bauer = {
        "finder": _befehl_macos,
        "explorer": _befehl_windows,
        "zenity": _befehl_zenity,
        "kdialog": _befehl_kdialog,
    }[werkzeug]
    befehl = bauer(titel, startpfad)

    try:
        ergebnis = subprocess.run(
            befehl,
            capture_output=True,
            text=True,
            timeout=ZEITGRENZE_SEKUNDEN,
        )
    except subprocess.TimeoutExpired as fehler:
        raise DialogZeitueberschreitung() from fehler

    ausgabe = (ergebnis.stdout or "").strip()
    if ergebnis.returncode != 0 or not ausgabe:
        # All four tools report cancellation through the return code;
        # osascript additionally writes "User canceled." to stderr. An empty
        # path with return code 0 happens with the FolderBrowserDialog when it
        # is closed via Cancel.
        fehlertext = (ergebnis.stderr or "").strip()
        if fehlertext and "cancel" not in fehlertext.lower():
            log.warning("Folder dialog (%s) reported: %s", werkzeug, fehlertext)
        raise DialogAbgebrochen()

    # The macOS dialog returns the path with a trailing slash.
    return str(Path(ausgabe.rstrip("/") if ausgabe != "/" else "/").resolve())


def _befehl_macos(titel: str, startpfad: str | None) -> list[str]:
    # `activate` brings the dialog to the front — otherwise it opens behind the
    # window that was just clicked in and looks like a freeze. It refers to
    # osascript itself, not a foreign app: no automation prompt.
    voreinstellung = ""
    if startpfad and Path(startpfad).is_dir():
        # POSIX file … turns the path into a folder reference that
        # `choose folder` accepts as its starting point.
        sicher = startpfad.replace("\\", "\\\\").replace('"', '\\"')
        voreinstellung = f' default location (POSIX file "{sicher}")'
    schrift = (
        "tell me to activate\n"
        f'set derOrdner to choose folder with prompt "{titel}"{voreinstellung}\n'
        "POSIX path of derOrdner"
    )
    return ["osascript", "-e", schrift]


def _befehl_windows(titel: str, startpfad: str | None) -> list[str]:
    # -STA is mandatory: without a single-threaded apartment a Windows Forms
    # dialog does not open. -NoProfile keeps foreign profile scripts out.
    start = ""
    if startpfad and Path(startpfad).is_dir():
        sicher = startpfad.replace("'", "''")
        start = f"$dialog.SelectedPath = '{sicher}'; "
    titel_sicher = titel.replace("'", "''")
    schrift = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        f"$dialog.Description = '{titel_sicher}'; "
        # The new style is the Explorer dialog with a path bar and the
        # "New Folder" button; the old one would be a tree view from 2001.
        "$dialog.UseDescriptionForTitle = $true; "
        f"{start}"
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ Write-Output $dialog.SelectedPath } else { exit 1 }"
    )
    return [_windows_powershell() or "powershell.exe", "-STA", "-NoProfile", "-Command", schrift]


def _befehl_zenity(titel: str, startpfad: str | None) -> list[str]:
    befehl = ["zenity", "--file-selection", "--directory", f"--title={titel}"]
    if startpfad and Path(startpfad).is_dir():
        befehl.append(f"--filename={startpfad.rstrip('/')}/")
    return befehl


def _befehl_kdialog(titel: str, startpfad: str | None) -> list[str]:
    start = startpfad if startpfad and Path(startpfad).is_dir() else str(Path.home())
    return ["kdialog", "--title", titel, "--getexistingdirectory", start]
