"""Lets an existing config.yaml grow with the program.

The database has solved this for a long time: ``schema.sql`` describes the
target state, it runs on every start, every statement is
``CREATE TABLE IF NOT EXISTS`` — so an existing database picks up new tables
without anybody losing a row. The configuration had no such thing. A setting
added by an update did have a default in the schema, so nothing crashed, but
it never appeared in the user's file: invisible, undocumented, unchangeable.
A feature nobody can find is a feature that is not there.

This module is that missing half. On every start the user's file is compared
against the shipped template and whatever is missing is written in, with the
template's own explanatory comment above it.

Three properties matter, in this order:

* **A value the user set is never touched.** Not the value, not the comment
  next to it, not its place in the file. Only missing keys are added, and
  they are added as text lines — the file is never re-serialised, because
  that is what destroys comments.
* **A migration never changes behaviour.** The value written for a missing
  key is the schema default, not the template's value — the schema default
  is exactly what the program was already using while the key was absent.
  The template can differ on purpose (it is the state a *fresh* install
  starts in), and that difference must not travel into a running one.
* **A migration never prevents a start.** Unreadable file, unparsable YAML,
  read-only folder: all of them mean the file stays as it is and the program
  goes on with what it can read.

Before anything is written the old file is copied aside, and the new one is
written next to it and renamed into place, so an interruption mid-write
leaves either the old file or the new one, never half of each.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

log = logging.getLogger(__name__)

# `name:` at any indentation, with whatever follows the colon.
SCHLUESSEL_MUSTER = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_.-]*)\s*:(.*)$")

SICHERUNG_ENDUNG = ".sicherung"
NEBEN_ENDUNG = ".wanderung"

# Marker for "the schema knows no default here", distinct from a default
# that happens to be None (``timezone`` has one).
_KEIN_WERT = object()


# --- reading the template -----------------------------------------------


class _Abschnitt:
    """One top-level section of the template, kept as raw text lines.

    Text rather than parsed values, because the comments are the point: a
    key is only useful to somebody who can read what it does.
    """

    def __init__(self, kopf: list[str], inline: str) -> None:
        self.kopf = kopf
        # What stands right of the colon on the section line. Empty means a
        # block follows; anything else ("[]", "{a: 1}") means the section is
        # written inline and must not be edited line by line.
        self.inline = inline
        self.kinder: dict[str, list[str]] = {}
        self.reihenfolge: list[str] = []
        self.einzug: int | None = None

    def zeilen(self) -> list[str]:
        alles = list(self.kopf)
        for name in self.reihenfolge:
            alles.extend(self.kinder[name])
        return alles


def _ist_leer_oder_kommentar(zeile: str) -> bool:
    return not zeile.strip() or zeile.lstrip().startswith("#")


def _wartend_teilen(wartend: list[str]) -> tuple[list[str], list[str]]:
    """Splits buffered comment lines at the point a new section begins.

    An indented comment belongs to the section above it — the commented-out
    examples under ``endpoints:`` are the case that made this necessary.
    Everything from the first unindented line onwards introduces what comes
    next.
    """
    letzte_eingerueckte = -1
    for stelle, zeile in enumerate(wartend):
        if zeile.strip() and zeile[:1].isspace():
            letzte_eingerueckte = stelle
    return wartend[: letzte_eingerueckte + 1], wartend[letzte_eingerueckte + 1 :]


def _vorlage_zerlegen(text: str) -> tuple[list[str], dict[str, _Abschnitt]]:
    """Template text to sections, each section to keys, each key to its lines."""
    reihenfolge: list[str] = []
    abschnitte: dict[str, _Abschnitt] = {}
    wartend: list[str] = []
    aktuell: _Abschnitt | None = None
    kind: str | None = None

    for zeile in text.splitlines():
        if _ist_leer_oder_kommentar(zeile):
            wartend.append(zeile)
            continue

        treffer = SCHLUESSEL_MUSTER.match(zeile)
        if treffer is not None:
            einzug, name, rest = treffer.groups()
            if not einzug:
                zurueck, vor = _wartend_teilen(wartend)
                if zurueck and aktuell is not None:
                    ziel = aktuell.kinder[kind] if kind else aktuell.kopf
                    ziel.extend(zurueck)
                aktuell = _Abschnitt([*vor, zeile], rest.strip())
                abschnitte[name] = aktuell
                reihenfolge.append(name)
                wartend = []
                kind = None
                continue
            if aktuell is not None and aktuell.einzug in (None, len(einzug)):
                aktuell.einzug = len(einzug)
                kind = name
                aktuell.kinder[name] = [*wartend, zeile]
                aktuell.reihenfolge.append(name)
                wartend = []
                continue

        # Neither a section nor a key at its level: a list item or the
        # continuation of a block. It belongs to whatever is open.
        if aktuell is not None:
            ziel = aktuell.kinder[kind] if kind else aktuell.kopf
            ziel.extend(wartend)
            ziel.append(zeile)
        wartend = []

    return reihenfolge, abschnitte


# --- reading the user's file --------------------------------------------


def _abschnitt_grenzen(zeilen: list[str]) -> dict[str, tuple[int, int]]:
    """Line range of every top-level section in the user's file."""
    grenzen: dict[str, tuple[int, int]] = {}
    aktuell: str | None = None
    start = 0
    for stelle, zeile in enumerate(zeilen):
        if not zeile[:1].strip() or zeile.lstrip().startswith("#"):
            continue
        treffer = SCHLUESSEL_MUSTER.match(zeile)
        if treffer is None or treffer.group(1):
            continue
        if aktuell is not None:
            grenzen[aktuell] = (start, stelle)
        aktuell = treffer.group(2)
        start = stelle
    if aktuell is not None:
        grenzen[aktuell] = (start, len(zeilen))
    return grenzen


def _einfuegestelle(zeilen: list[str], bereich: tuple[int, int]) -> int:
    """Behind the last real line of a section, in front of its trailing comments.

    Trailing comments at the end of a block usually introduce the next
    section, and a new key pushed between them and their section would read
    as if it belonged to the other one.
    """
    start, ende = bereich
    stelle = start
    for lauf in range(start, ende):
        if not _ist_leer_oder_kommentar(zeilen[lauf]):
            stelle = lauf
    return stelle + 1


# --- schema defaults ----------------------------------------------------


def _untermodell(schema: type[BaseModel], abschnitt: str) -> type[BaseModel] | None:
    feld = schema.model_fields.get(abschnitt)
    if feld is None:
        return None
    annotation = feld.annotation
    try:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation
    except TypeError:
        return None
    return None


def _feldvorgabe(modell: type[BaseModel] | None, name: str) -> Any:
    if modell is None:
        return _KEIN_WERT
    feld = modell.model_fields.get(name)
    if feld is None or feld.is_required():
        return _KEIN_WERT
    return feld.get_default(call_default_factory=True)


# --- writing values back into a template line ---------------------------


def _wert_text(wert: Any) -> str:
    if isinstance(wert, str):
        text = yaml.safe_dump(wert, default_style='"', allow_unicode=True, width=10**6)
    else:
        text = yaml.safe_dump(wert, default_flow_style=True, allow_unicode=True, width=10**6)
    text = text.strip()
    if text.endswith("\n..."):
        text = text[: -len("\n...")].strip()
    return text


def _inline_kommentar(rest: str) -> str:
    """The trailing comment of a key line, including the space before it."""
    in_hochkomma = False
    in_anfuehrung = False
    for stelle, zeichen in enumerate(rest):
        if zeichen == "'" and not in_anfuehrung:
            in_hochkomma = not in_hochkomma
        elif zeichen == '"' and not in_hochkomma:
            in_anfuehrung = not in_anfuehrung
        elif zeichen == "#" and not in_hochkomma and not in_anfuehrung:
            anfang = stelle
            while anfang > 0 and rest[anfang - 1].isspace():
                anfang -= 1
            return rest[anfang:]
    return ""


def _zeilen_mit_vorgabe(zeilen: list[str], wert: Any) -> list[str]:
    """The template's lines for one key, with the schema default put in.

    Only the key line itself is rewritten; its comments travel unchanged. A
    key whose template value spans several lines is taken as it stands —
    rewriting that safely is not worth the guesswork.
    """
    if wert is _KEIN_WERT:
        return list(zeilen)
    stelle = len(zeilen) - 1
    treffer = SCHLUESSEL_MUSTER.match(zeilen[stelle])
    if treffer is None:
        return list(zeilen)
    einzug, name, rest = treffer.groups()
    if not rest.strip() or rest.strip().startswith("#"):
        # A block value follows on the next lines; leave it alone.
        return list(zeilen)
    neu = list(zeilen)
    neu[stelle] = f"{einzug}{name}: {_wert_text(wert)}{_inline_kommentar(rest)}"
    return neu


# --- the migration itself -----------------------------------------------


def _lesen(datei: Path) -> str | None:
    # newline="" so the file's own line endings survive the round trip
    # instead of being translated on the way in and back out.
    try:
        with datei.open(encoding="utf-8", newline="") as offen:
            return offen.read()
    except OSError as fehler:
        log.warning("Konfiguration nicht lesbar (%s): %s", datei, fehler)
        return None


def _schreiben(ziel: Path, text: str) -> bool:
    """Backup, side file, rename. Any failure leaves the old file untouched."""
    neben = ziel.with_suffix(ziel.suffix + NEBEN_ENDUNG)
    try:
        shutil.copy2(ziel, ziel.with_suffix(ziel.suffix + SICHERUNG_ENDUNG))
        with neben.open("w", encoding="utf-8", newline="") as offen:
            offen.write(text)
        neben.replace(ziel)
    except OSError as fehler:
        log.warning("Konfiguration nicht fortschreibbar (%s): %s", ziel, fehler)
        try:
            neben.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def wandern(ziel: Path, vorlage: Path, schema: type[BaseModel]) -> list[str]:
    """Writes every known key that is missing into the user's configuration.

    Returns the names that were added, as ``section.key``. An empty list
    means the file was already complete, or that nothing could be done —
    both are a good outcome for a start-up step.
    """
    ziel = Path(ziel)
    vorlage = Path(vorlage)
    if not ziel.exists() or not vorlage.exists() or ziel == vorlage:
        return []

    text = _lesen(ziel)
    vorlagetext = _lesen(vorlage)
    if text is None or vorlagetext is None:
        return []

    try:
        bestand = yaml.safe_load(text)
    except yaml.YAMLError as fehler:
        # A broken file is the user's to repair. Rewriting it would replace
        # a fixable typo with a silent loss of everything below it.
        log.warning("Konfiguration nicht auswertbar, bleibt unverändert: %s", fehler)
        return []
    if bestand is None:
        bestand = {}
    if not isinstance(bestand, dict):
        log.warning("Konfiguration ist keine Zuordnung, bleibt unverändert: %s", ziel)
        return []

    reihenfolge, abschnitte = _vorlage_zerlegen(vorlagetext)
    zeilen = text.splitlines()
    grenzen = _abschnitt_grenzen(zeilen)

    nachgetragen: list[str] = []
    einfuegungen: list[tuple[int, list[str]]] = []
    anhang: list[str] = []

    for name in reihenfolge:
        abschnitt = abschnitte[name]
        untermodell = _untermodell(schema, name)

        if name not in bestand:
            block = list(abschnitt.kopf)
            if abschnitt.inline and not abschnitt.inline.startswith("#"):
                block = _zeilen_mit_vorgabe(block, _feldvorgabe(schema, name))
            for kind in abschnitt.reihenfolge:
                block.extend(
                    _zeilen_mit_vorgabe(abschnitt.kinder[kind], _feldvorgabe(untermodell, kind))
                )
            anhang.append("")
            anhang.extend(block)
            nachgetragen.append(name)
            continue

        if not abschnitt.reihenfolge or name not in grenzen:
            continue
        if abschnitt.inline and not abschnitt.inline.startswith("#"):
            continue

        vorhanden = bestand[name]
        if vorhanden is not None and not isinstance(vorhanden, dict):
            continue
        treffer = SCHLUESSEL_MUSTER.match(zeilen[grenzen[name][0]])
        rest = treffer.group(3).strip() if treffer is not None else ""
        if rest and not rest.startswith("#"):
            # The user wrote this section inline. Adding indented lines
            # under it would produce a file that no longer parses.
            log.warning("Abschnitt '%s' steht einzeilig und wird nicht ergänzt", name)
            continue

        fehlend: list[str] = []
        for kind in abschnitt.reihenfolge:
            if vorhanden and kind in vorhanden:
                continue
            fehlend.extend(
                _zeilen_mit_vorgabe(abschnitt.kinder[kind], _feldvorgabe(untermodell, kind))
            )
            nachgetragen.append(f"{name}.{kind}")
        if fehlend:
            einfuegungen.append((_einfuegestelle(zeilen, grenzen[name]), fehlend))

    if not nachgetragen:
        return []

    for stelle, block in sorted(einfuegungen, key=lambda eintrag: eintrag[0], reverse=True):
        zeilen[stelle:stelle] = block
    zeilen.extend(anhang)

    # Keep the line endings the file already had: rewriting a Windows file
    # in Unix endings would show up as a change on every single line.
    umbruch = "\r\n" if "\r\n" in text else "\n"
    if not _schreiben(ziel, umbruch.join(zeilen) + umbruch):
        return []

    log.info("Konfiguration ergänzt: %s", ", ".join(nachgetragen))
    return nachgetragen
