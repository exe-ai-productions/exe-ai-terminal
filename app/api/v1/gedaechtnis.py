"""The memory file — reading and writing.

Its own route beside the system prompt rather than a second mode on that one:
the two files carry different things and are switched independently. What
they share is only their nature — prompt material, freshly read on every
request, a file so it can be opened anywhere.

Whether the memory is sent along is NOT decided here. That is two switches in
the settings cascade (``gedaechtnis``, see app/gedaechtnis.py) — this route
only holds the text.

Writing by hand is the path that works on every model. Filling it by tool
call needs a model that can call tools; reading it needs nothing at all, so
a model without tool support still uses everything that is in here.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.api.v1.schemas import GedaechtnisAnfrage, GedaechtnisAntwort
from app.config import Config
from app.i18n import t

log = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=GedaechtnisAntwort, summary="Gedächtnis lesen")
def lesen(config: Config = Depends(hole_config)) -> GedaechtnisAntwort:
    return GedaechtnisAntwort(
        text=config.memory_lesen(),
        # The path travels so the window can say where it lives — and so it
        # can be found by hand, which is half the point of using a file.
        datei=config.app.memory_file,
    )


@router.put("", response_model=GedaechtnisAntwort, summary="Gedächtnis sichern")
def sichern(
    daten: GedaechtnisAnfrage,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> GedaechtnisAntwort:
    """Always saves, including empty.

    Empty means: forget everything. That has to work in one move and without
    a detour — whoever wants to wipe what a program knows about them should
    not have to hunt for the way to do it.
    """
    try:
        config.memory_schreiben(daten.text)
    except OSError as fehler:
        log.error("Gedächtnis ließ sich nicht schreiben: %s", fehler)
        raise HTTPException(500, t("fehler.prompt_nicht_schreibbar", sprache)) from fehler

    return GedaechtnisAntwort(text=config.memory_lesen(), datei=config.app.memory_file)
