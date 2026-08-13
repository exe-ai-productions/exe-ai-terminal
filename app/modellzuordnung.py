"""The declared bond between a model and its companions.

A vision projector and a draft module belong to one particular model, and
until now that bond was guessed anew on every start — from shared name
prefixes, which is exactly where it fails: a catalogue can hold two draft
modules that begin with the same word and belong to different sizes, and the
guess then hands the wrong one to a server that runs for hours.

So the bond is written down where the model lies, at the moment the companion
is fetched next to it. A small JSON sidecar in the model folder maps a model
file to the names of its projector and its draft. The runner reads it instead
of guessing, and the note outlives a restart, which the in-memory state never
did.

The folder boundary is a security line, the same as in the runner and the
download: a value out of the sidecar is a plain ``.gguf`` basename or it is
dropped. A slash, a ``..`` or a leading dot would point somewhere other than
the model folder, and nothing here follows such a name.
"""

from __future__ import annotations

import json
from pathlib import Path

# The sidecar in the model folder. It sits next to the models, so it travels
# with them and is found without a path from outside.
ZUORDNUNG_DATEI = "zuordnung.json"
ENDUNG = ".gguf"
UNFERTIG = ".teil"

# The two places a companion can take next to a model. Anything else is not a
# role this manifest knows and is left alone.
ROLLEN = ("mmproj", "mtp")


def _sicher(name: str | None) -> str | None:
    """A plain ``.gguf`` basename, or nothing when the name reaches outside.

    Mirrors the guard in ``modellrunner.starten`` and ``Modelldownload._pruefen``:
    a slash, a backslash, a ``..`` or a leading dot would leave the model
    folder, so such a value is refused rather than trusted as a path.
    """
    if not name or not isinstance(name, str):
        return None
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        return None
    if not name.lower().endswith(ENDUNG):
        return None
    return name


def lade(ordner: Path) -> dict:
    """The whole sidecar as a dict, or an empty one on missing or corrupt.

    Never raises: a note that cannot be read is treated as a note that is
    not there, and the runner falls back to its name heuristic.
    """
    datei = Path(ordner) / ZUORDNUNG_DATEI
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _schreiben(ordner: Path, daten: dict) -> None:
    """Writes the sidecar in one atomic step, tolerating a folder that refuses.

    A ``.teil`` file takes the bytes and is only then renamed onto the real
    name, so a reader never catches a half-written note. A folder that will
    not take the file costs the association after a restart, never the
    download itself.
    """
    try:
        ordner = Path(ordner)
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = ordner / ZUORDNUNG_DATEI
        halb = ordner / (ZUORDNUNG_DATEI + UNFERTIG)
        halb.write_text(
            json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        halb.replace(ziel)
    except OSError:
        pass


def eintragen(ordner: Path, modell: str, rolle: str, datei: str) -> None:
    """Upserts one companion of one model under its role.

    For the parent ``modell`` the given ``rolle`` ('mmproj' or 'mtp') is set
    to ``datei``. An unknown role, or any of the three names that is not a
    safe basename, is dropped silently rather than written.
    """
    if rolle not in ROLLEN:
        return
    m = _sicher(modell)
    d = _sicher(datei)
    if m is None or d is None:
        return
    daten = lade(ordner)
    eintrag = daten.get(m)
    if not isinstance(eintrag, dict):
        eintrag = {}
    eintrag[rolle] = d
    daten[m] = eintrag
    _schreiben(ordner, daten)


def fuer(ordner: Path, modell: str) -> dict:
    """The companions declared for one model, only those still in the folder.

    A deleted projector or draft disappears from the answer, so the runner
    never attaches a file that is no longer there.
    """
    ordner = Path(ordner)
    eintrag = lade(ordner).get(modell)
    ergebnis: dict[str, str | None] = {"mmproj": None, "mtp": None}
    if not isinstance(eintrag, dict):
        return ergebnis
    for rolle in ROLLEN:
        name = _sicher(eintrag.get(rolle))
        if name and (ordner / name).is_file():
            ergebnis[rolle] = name
    return ergebnis


def entfernen(ordner: Path, modell: str) -> None:
    """Drops the whole entry for one model, if there is one."""
    daten = lade(ordner)
    if modell in daten:
        del daten[modell]
        _schreiben(ordner, daten)
