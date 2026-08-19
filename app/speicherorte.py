"""The named storage locations, in one place.

Every folder the terminal writes the user's things into — the pictures it
draws, the picture models, the language models — is a NAMED location here,
not a path spelled out at each call site. One function answers "where does
X live", so the places that need a folder ask by name instead of building
the path by hand.

Why a module of its own: the same wish ("let me put this somewhere else",
"open that folder", "show me the path") turned up for pictures, for models
and for the catalogue's downloads. Four scattered answers would be four
things to keep in step; one place is one truth.

Two layers decide where a location lives:

  * the DEFAULT, a field in config.yaml (``bilder_verzeichnis`` and its
    siblings) — the as-installed place, next to the other data;
  * the OVERRIDE, a line in ``speicherorte.json`` in the data folder,
    written when the user moves a location elsewhere.

The override wins when present. It lives in its own small file on purpose:
config.yaml is full of explaining comments, and rewriting it would strip
every one of them — a JSON file the module owns can be rewritten freely.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Config

log = logging.getLogger(__name__)

# Serialises the read-modify-write on the overrides file. FastAPI runs the
# sync route handlers in a threadpool, so two saves can land at once; without
# this, both read the same starting file and the second write drops the
# first's entry.
_SCHLOSS = threading.Lock()

# The overrides file, kept in the data folder — isolated per installation
# and never mixed into the commented config.yaml.
UEBERSCHREIBUNGEN_DATEI = "speicherorte.json"


class SpeicherortFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself —
    same shape as the other runtime errors, so the route can localise it."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


@dataclass(frozen=True)
class Ort:
    """One named location: its key, the config field that holds its default
    path, and whether a running process is bound to it at startup (so a move
    takes hold only after a restart) or it is read fresh each time it is
    needed (so a move takes hold at once)."""

    name: str
    feld: str
    neustart_noetig: bool


# The known locations, in the order the settings screen lists them. The
# database file is deliberately NOT here: moving an open database is its own
# undertaking, and until it is one, its place stays fixed.
ORTE: tuple[Ort, ...] = (
    # The pictures are written and read fresh per request — a move is felt at
    # once, no restart.
    Ort("bilder", "bilder_verzeichnis", neustart_noetig=False),
    # The model folders are handed to running servers and the download router
    # at startup — a move needs a restart to take full hold.
    Ort("bildmodelle", "bildmodelle_verzeichnis", neustart_noetig=True),
    Ort("modelle", "modelle_verzeichnis", neustart_noetig=True),
    Ort("einbettung", "einbettungsmodelle_verzeichnis", neustart_noetig=True),
)

_NACH_NAME = {o.name: o for o in ORTE}


def _ueberschreibungen_datei(config: "Config") -> Path:
    return config.datenverzeichnis / UEBERSCHREIBUNGEN_DATEI


def ueberschreibungen(config: "Config") -> dict[str, str]:
    """The stored overrides, name → absolute path. Empty when the file is
    missing (the as-shipped state) or unreadable (counts as none, so a
    broken file never takes a location down — the next save overwrites it)."""
    datei = _ueberschreibungen_datei(config)
    if not datei.exists():
        return {}
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as fehler:
        log.warning("Speicherorte-Überschreibungen nicht lesbar (%s): %s", datei, fehler)
        return {}
    if not isinstance(roh, dict):
        return {}
    # Only known names, only string paths — a stale or hand-edited entry for
    # a location that no longer exists is ignored, not carried around.
    return {
        name: wert
        for name, wert in roh.items()
        if name in _NACH_NAME and isinstance(wert, str) and wert
    }


def standard(config: "Config", name: str) -> Path:
    """The as-installed folder for a location, ignoring any override — what
    'reset to default' returns to.

    An empty config field means "under the data folder": the location follows
    a moved data_dir exactly as ``datenverzeichnis / name`` did, instead of a
    hardcoded path that would strand old files when someone set data_dir."""
    eintrag = _NACH_NAME.get(name)
    if eintrag is None:
        raise KeyError(f"Unbekannter Speicherort: {name!r}")
    wert = getattr(config.app, eintrag.feld)
    if not wert:
        return config.datenverzeichnis / name
    return config.pfad(wert)


def ort(config: "Config", name: str) -> Path:
    """The absolute folder for a named location: the override if one is set,
    otherwise the installed default. Raises ``KeyError`` for an unknown name
    so a typo fails loud, not silently at some wrong folder."""
    if name not in _NACH_NAME:
        raise KeyError(f"Unbekannter Speicherort: {name!r}")
    ueber = ueberschreibungen(config).get(name)
    if ueber:
        return Path(ueber).expanduser().resolve()
    return standard(config, name)


def _gleicher_ort(a: Path, b: Path) -> bool:
    """Do two paths point at the same real folder? ``samefile`` follows
    symlinks and matches the case-insensitive filesystem on macOS, where a
    plain string compare would call ``/Users/x/Bilder`` and ``.../bilder``
    different. It needs both to exist; when one does not, fall back to a
    case-folded string compare."""
    try:
        return a.samefile(b)
    except OSError:
        return os.path.normcase(str(a)) == os.path.normcase(str(b))


def _verschachtelt(a: Path, b: Path) -> bool:
    """Does one folder sit inside the other? Case-folded so a nesting is not
    missed on a case-insensitive filesystem."""
    na, nb = os.path.normcase(str(a)), os.path.normcase(str(b))
    if na == nb:
        return False
    return na.startswith(nb + os.sep) or nb.startswith(na + os.sep)


def _pruefen(config: "Config", name: str, pfad: str | Path) -> Path:
    """A path fit to store this location's things in: absolute, a folder that
    exists or can be made, writable, and not colliding with another location.
    Raises ``SpeicherortFehler`` with a specific key otherwise — a path the
    program cannot use must be refused where it is set, not discovered as a
    failed picture later."""
    ziel = Path(pfad).expanduser()
    if not str(ziel).strip():
        raise SpeicherortFehler("speicherorte.leer")
    ziel = ziel.resolve()
    if ziel.exists() and not ziel.is_dir():
        raise SpeicherortFehler("speicherorte.kein_ordner")
    try:
        ziel.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise SpeicherortFehler("speicherorte.nicht_anlegbar")
    if not os.access(ziel, os.W_OK):
        raise SpeicherortFehler("speicherorte.nicht_schreibbar")
    # No location may share a folder with another, nor sit inside it: two
    # kinds of files in one folder would mix, and a cleanup of one kind could
    # take the other's files with it.
    for anderer in ORTE:
        if anderer.name == name:
            continue
        fremd = ort(config, anderer.name)
        if _gleicher_ort(ziel, fremd) or _verschachtelt(ziel, fremd):
            raise SpeicherortFehler("speicherorte.ueberschneidung")
    return ziel


def setzen(config: "Config", name: str, pfad: str | Path) -> Path:
    """Point a location at a new folder. The path is checked first (see
    ``_pruefen``); a path equal to the installed default removes the override
    instead of storing it, so 'back to default' leaves no dead line behind.
    Returns the resolved folder now in force."""
    if name not in _NACH_NAME:
        raise KeyError(f"Unbekannter Speicherort: {name!r}")
    ziel = _pruefen(config, name, pfad)
    if _gleicher_ort(ziel, standard(config, name)):
        loeschen(config, name)
        return ziel
    with _SCHLOSS:
        daten = ueberschreibungen(config)
        daten[name] = str(ziel)
        _schreiben(config, daten)
    return ziel


def loeschen(config: "Config", name: str) -> Path:
    """Drop a location's override, back to the installed default. Returns the
    default now in force. Doing nothing when there was no override is fine —
    the end state is the same."""
    if name not in _NACH_NAME:
        raise KeyError(f"Unbekannter Speicherort: {name!r}")
    with _SCHLOSS:
        daten = ueberschreibungen(config)
        if name in daten:
            del daten[name]
            _schreiben(config, daten)
    return standard(config, name)


def _schreiben(config: "Config", daten: dict[str, str]) -> None:
    """Write the overrides — side file first, then rename, so an interrupted
    write leaves the old file intact rather than a half-written one."""
    datei = _ueberschreibungen_datei(config)
    datei.parent.mkdir(parents=True, exist_ok=True)
    neben = datei.with_suffix(datei.suffix + ".neu")
    neben.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    neben.replace(datei)


def uebersicht(config: "Config") -> list[dict]:
    """Every location for the settings screen: its name, the folder in force,
    the installed default, whether it currently sits on the default, and
    whether a move needs a restart to take full hold."""
    ueber = ueberschreibungen(config)
    zeilen = []
    for eintrag in ORTE:
        std = standard(config, eintrag.name)
        gilt = Path(ueber[eintrag.name]).expanduser().resolve() if eintrag.name in ueber else std
        zeilen.append({
            "name": eintrag.name,
            "pfad": str(gilt),
            "standard": str(std),
            "ist_standard": _gleicher_ort(gilt, std),
            "neustart_noetig": eintrag.neustart_noetig,
        })
    return zeilen
