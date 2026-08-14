"""Wiring the section search into a chat.

Two moments, and they are deliberately far apart:

* **On upload** a document past the threshold is cut up and every section
  gets its vector. That is the expensive half, it happens once, and it
  happens while the user is still looking at the upload.
* **On every question** the question itself gets one vector and the closest
  sections travel with it. That is one call for the whole request, however
  many documents hang in the conversation.

Everything here answers None when anything is missing — no embedding
program, no embedding model, no sections, the switch off. None means "carry
on as before", and carrying on as before is a document sent whole. A
feature that cannot run must not take the old behaviour down with it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app import einbettung, einbettungsserver, einbettungwahl

log = logging.getLogger(__name__)


def _ueber_server(einbettungsrunner, texte: list[str]) -> list[list[float]] | None:
    """The fast way, if it is standing. None means: use the one-shot call.

    A running embedding server answers in milliseconds because it is already
    holding its model. Without one, nothing is lost — the one-shot call does
    the same work and pays for a model load doing it.
    """
    if einbettungsrunner is None or not einbettungsrunner.laeuft():
        return None
    lauf = einbettungsrunner.lauf()
    if lauf is None:
        return None
    return einbettungsserver.vektoren(lauf.port, einbettungsrunner.schluessel, texte)


def _werkzeuge(config, modellrunner) -> tuple[Path, Path] | None:
    """The embedding program and model, or nothing if either is missing."""
    daten = config.datenverzeichnis
    programm = einbettung.programm_finden(
        daten, neben=getattr(modellrunner, "programm", None)
    )
    if programm is None:
        return None
    modell = einbettung.modell_finden(
        config.pfad(config.app.einbettungsmodelle_verzeichnis)
    )
    if modell is None:
        return None
    return programm, modell


def _rechnen(einbettungsrunner, programm, modell, texte: list[str]) -> list[list[float]]:
    """Vectors — over the server when it stands, otherwise one-shot."""
    ueber_server = _ueber_server(einbettungsrunner, texte)
    if ueber_server is not None:
        return ueber_server
    return einbettung.vektoren(programm, modell, texte)


def einbetten(config, modellrunner, repositories, dokument, einbettungsrunner=None) -> int:
    """Cut a document up and store its vectors. Returns how many sections.

    Zero means: not done, and the document keeps travelling whole. That is
    the honest outcome for a machine without the program — better than an
    upload that fails over a feature nobody asked for by name.
    """
    text = dokument.extracted_text or ""
    if len(text) <= einbettung.SCHWELLE:
        return 0
    werkzeuge = _werkzeuge(config, modellrunner)
    if werkzeuge is None:
        return 0
    programm, modell = werkzeuge
    abschnitte = einbettung.zerlegen(text)
    if not abschnitte:
        return 0
    try:
        vektoren = _rechnen(einbettungsrunner, programm, modell, abschnitte)
    except einbettung.EinbettungFehler:
        log.warning("Dokument %s konnte nicht eingebettet werden", dokument.id)
        return 0
    return repositories.abschnitte.speichern(
        document_id=dokument.id,
        abschnitte=list(zip(abschnitte, vektoren)),
        # The file name, not the path: the folder can move, the model that
        # wrote these numbers cannot become a different one.
        modell=modell.name,
    )


def kontext_waehler(
    config, modellrunner, repositories, frage: str, modell=None, chat=None,
    einbettungsrunner=None,
):
    """Build the function that decides what a document contributes.

    Returns a callable ``(dokument) -> str | None``. None means: nothing was
    selected, use the whole text — which is what happens for every document
    below the threshold, and for all of them when anything is missing.

    The question is embedded ONCE here, not per document: the vector does
    not depend on which document it is compared against.
    """
    # The same scope the upload asked in — model and chat, not just the
    # global default. A switch that answers differently depending on where
    # it is read is not one switch.
    if not frage.strip() or not einbettungwahl.zerlegt(repositories, modell=modell, chat=chat):
        return lambda _dokument: None
    werkzeuge = _werkzeuge(config, modellrunner)
    if werkzeuge is None:
        return lambda _dokument: None
    programm, modellpfad = werkzeuge
    try:
        vektor = _rechnen(einbettungsrunner, programm, modellpfad, [frage])[0]
    except (einbettung.EinbettungFehler, IndexError):
        return lambda _dokument: None

    def waehlen(dokument) -> str | None:
        # Only the sections this same model wrote. Sections from another one
        # are not weaker matches, they are numbers from another scale — and
        # asking the database for them keeps that decision in one place
        # instead of relying on the vectors happening to differ in length.
        gespeichert = repositories.abschnitte.auflisten(dokument.id, modell=modellpfad.name)
        if not gespeichert:
            return None
        treffer = einbettung.naechste(vektor, gespeichert)
        return einbettung.als_kontext(dokument.filename, treffer) or None

    return waehlen
