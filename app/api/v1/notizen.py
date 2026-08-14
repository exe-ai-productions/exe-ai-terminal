"""Notes and the document dock — the user's own pad beside the chat.

One router for both, because they share the panel and the rule behind it:
what is here belongs to the person, not to a conversation, and none of it
ever reaches the model.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.dock import PLAETZE, Dock
from app.notizen import MAX_INHALT, MAX_UEBERSCHRIFT, Notizen

router = APIRouter(prefix="/notizen", tags=["notizen"])


class NotizEingabe(BaseModel):
    ueberschrift: str = Field(default="", max_length=MAX_UEBERSCHRIFT)
    # Restricted HTML: the four kinds of emphasis. Whatever else arrives is
    # rebuilt away in app/notizen.py before anything is stored.
    inhalt: str = Field(default="", max_length=MAX_INHALT)


class NotizAntwort(BaseModel):
    id: str
    ueberschrift: str
    inhalt: str
    geaendert: str


class DockEintrag(BaseModel):
    id: str
    name: str
    typ: str = ""
    groesse: int = 0
    abgelegt: str = ""


def _notizen(request: Request) -> Notizen:
    return Notizen(request.app.state.config.datenverzeichnis)


def _dock(request: Request) -> Dock:
    return Dock(request.app.state.config.datenverzeichnis)


@router.get("", response_model=list[NotizAntwort], summary="Alle Notizen")
def liste(request: Request) -> list[NotizAntwort]:
    return [NotizAntwort(**n) for n in _notizen(request).alle()]


@router.post("", response_model=NotizAntwort, status_code=201, summary="Notiz anlegen")
def anlegen(daten: NotizEingabe, request: Request) -> NotizAntwort:
    return NotizAntwort(**_notizen(request).anlegen(daten.ueberschrift, daten.inhalt))


@router.put("/{notiz_id}", response_model=NotizAntwort, summary="Notiz ändern")
def aendern(notiz_id: str, daten: NotizEingabe, request: Request) -> NotizAntwort:
    notiz = _notizen(request).aendern(notiz_id, daten.ueberschrift, daten.inhalt)
    if notiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Notiz gibt es nicht")
    return NotizAntwort(**notiz)


@router.delete("/{notiz_id}", status_code=204, response_class=Response, summary="Notiz löschen")
def loeschen(notiz_id: str, request: Request) -> Response:
    if not _notizen(request).loeschen(notiz_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Notiz gibt es nicht")
    return Response(status_code=204)


# --- The dock ---------------------------------------------------------------


@router.get("/dock/alle", response_model=list[DockEintrag], summary="Was im Dock liegt")
def dock_liste(request: Request) -> list[DockEintrag]:
    return [DockEintrag(**e) for e in _dock(request).alle()]


@router.post("/dock", response_model=DockEintrag, status_code=201, summary="Datei ins Dock legen")
async def dock_ablegen(request: Request, name: str = "") -> DockEintrag:
    """Raw bytes, like the image and document uploads: the name travels as a
    parameter because the extension matters and the content type does not
    reliably carry it."""
    daten = await request.body()
    if not daten:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Datei ist leer")
    try:
        eintrag = _dock(request).ablegen(
            name, daten, request.headers.get("content-type", "")
        )
    except ValueError as fehler:
        raise HTTPException(status.HTTP_409_CONFLICT, str(fehler)) from fehler
    return DockEintrag(**eintrag)


@router.get("/dock/{kennung}", summary="Eine Datei aus dem Dock holen")
def dock_datei(kennung: str, request: Request) -> FileResponse:
    gefunden = _dock(request).holen(kennung)
    if gefunden is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Datei gibt es nicht")
    eintrag, pfad = gefunden
    return FileResponse(
        pfad,
        media_type=eintrag.get("typ") or "application/octet-stream",
        filename=eintrag.get("name") or "Datei",
    )


@router.delete(
    "/dock/{kennung}", status_code=204, response_class=Response, summary="Platz räumen"
)
def dock_entfernen(kennung: str, request: Request) -> Response:
    if not _dock(request).entfernen(kennung):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Datei gibt es nicht")
    return Response(status_code=204)


@router.get("/dock/plaetze/anzahl", response_model=int, summary="Wie viele Plätze es gibt")
def dock_plaetze() -> int:
    return PLAETZE
