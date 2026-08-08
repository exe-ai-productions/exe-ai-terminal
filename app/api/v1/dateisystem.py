"""The system's folder dialog.

A route only the UI ever takes — never the model. The model gets folders
assigned, it does not pick them; this is where the share is granted, and that
is an act of the user.

The dialog opens on the machine the SERVICE runs on. If the user sits
somewhere else (container, another machine on the network), a window would
open that nobody sees — hence local access only. For every other case there
is the path field in the dialog window.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_sprache
from app.i18n import t
from app.ordner_dialog import (
    DialogAbgebrochen,
    DialogNichtVerfuegbar,
    DialogZeitueberschreitung,
    dialog_verfuegbar,
    ordner_waehlen,
)

router = APIRouter(prefix="/filesystem", tags=["filesystem"])

# Where the dialog makes sense at all.
LOKAL = {"127.0.0.1", "::1", "localhost"}


class DialogAuskunft(BaseModel):
    verfuegbar: bool
    werkzeug: str | None = None


class OrdnerWunsch(BaseModel):
    titel: str = Field(default="", max_length=200)
    # Where the dialog should open — usually the folder chosen last.
    start: str | None = Field(default=None, max_length=1000)


class OrdnerAntwort(BaseModel):
    # None means the user cancelled. That is not an error.
    pfad: str | None = None


def _ist_lokal(request: Request) -> bool:
    return bool(request.client and request.client.host in LOKAL)


@router.get(
    "/folder-dialog",
    response_model=DialogAuskunft,
    summary="Does this system have a folder dialog?",
)
def dialog_auskunft(request: Request) -> DialogAuskunft:
    """The UI asks this before showing the button.

    A button that clicks into nothing is worse than none at all — without a
    dialog only the path field remains in the window.
    """
    if not _ist_lokal(request):
        return DialogAuskunft(verfuegbar=False)
    werkzeug = dialog_verfuegbar()
    return DialogAuskunft(verfuegbar=werkzeug is not None, werkzeug=werkzeug)


@router.post(
    "/choose-folder",
    response_model=OrdnerAntwort,
    summary="Opens the system's folder dialog",
)
def ordner_dialog_oeffnen(
    wunsch: OrdnerWunsch,
    request: Request,
    sprache: str = Depends(hole_sprache),
) -> OrdnerAntwort:
    """Opens Finder or Explorer and returns the chosen path.

    Deliberately `def` and not `async def`: FastAPI pushes plain functions onto
    a worker thread. The dialog blocks for as long as it is open — in the event
    loop the whole service would stand still meanwhile.
    """
    if not _ist_lokal(request):
        raise HTTPException(400, t("fehler.ordnerdialog_fern", sprache))

    titel = wunsch.titel or t("arbeitsordner.dialog_titel", sprache)
    try:
        pfad = ordner_waehlen(titel, wunsch.start)
    except DialogAbgebrochen:
        return OrdnerAntwort(pfad=None)
    except DialogNichtVerfuegbar:
        raise HTTPException(400, t("fehler.ordnerdialog_fehlt", sprache))
    except DialogZeitueberschreitung:
        raise HTTPException(408, t("fehler.ordnerdialog_zeit", sprache))
    return OrdnerAntwort(pfad=pfad)
