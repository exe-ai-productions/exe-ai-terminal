"""Managing chats and messages (phase 1.3)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.abhaengigkeiten import (
    hole_benutzer_id,
    hole_config,
    hole_repositories,
    hole_sprache,
)
from app.config import Config
from app.api.v1.schemas import (
    ChatAendern,
    ChatAnlegen,
    ChatAntwort,
    NachrichtAnlegen,
    NachrichtAntwort,
)
from app.db import Repositories
from app.events import Ereignisse, bus
from app.i18n import t
from app import waechter

router = APIRouter(prefix="/chats", tags=["chats"])

# How many folders a chat may have shared at the same time. The number also
# lives in the frontend, where it disables the plus button — here it is the
# authoritative one.
ARBEITSORDNER_HOECHSTENS = 4


def _chat_oder_404(
    repositories: Repositories, chat_id: str, user_id: str, sprache: str
):
    chat = repositories.chats.holen(chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("fehler.chat_nicht_gefunden", sprache),
        )
    return chat


@router.post("", response_model=ChatAntwort, status_code=201, summary="Chat anlegen")
async def chat_anlegen(
    daten: ChatAnlegen,
    repositories: Repositories = Depends(hole_repositories),
    config: Config = Depends(hole_config),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> ChatAntwort:
    # No more copying on creation: the system prompt lives in a file and is
    # freshly prepended on every request, and model parameters come from the
    # settings cascade rather than being carried along per chat.
    chat = repositories.chats.erstellen(
        user_id=user_id,
        title=daten.title or t("chat.unbenannt", sprache),
        endpoint_id=daten.endpoint_id,
    )
    await bus.veroeffentlichen(Ereignisse.CHAT_ERSTELLT, chat_id=chat.id, user_id=user_id)
    return ChatAntwort.aus(chat)


@router.get("", response_model=list[ChatAntwort], summary="Chats auflisten")
def chats_auflisten(
    suche: str | None = Query(default=None, description="Filtert auf den Titel"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
) -> list[ChatAntwort]:
    chats = repositories.chats.auflisten(
        user_id=user_id, suche=suche, limit=limit, offset=offset
    )
    return [ChatAntwort.aus(chat) for chat in chats]


@router.get("/{chat_id}", response_model=ChatAntwort, summary="Chat holen")
def chat_holen(
    chat_id: str,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> ChatAntwort:
    return ChatAntwort.aus(_chat_oder_404(repositories, chat_id, user_id, sprache))


@router.patch("/{chat_id}", response_model=ChatAntwort, summary="Chat ändern")
def chat_aendern(
    chat_id: str,
    daten: ChatAendern,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> ChatAntwort:
    _chat_oder_404(repositories, chat_id, user_id, sprache)
    felder = daten.model_dump(exclude_unset=True)

    # The working folders are checked BEFORE saving: only absolute paths
    # to existing folders. ~ is expanded and the resolved path is stored —
    # what is in the database is exactly what will be worked in later. An
    # empty list deselects.
    #
    # More than four does not fit in the pill row above the field without it
    # becoming unreadable — and whoever shares more than four folders at once
    # no longer has a limit, only a habit. The rule lives here and not just in
    # the frontend: it belongs where it cannot be bypassed.
    if felder.get("working_dirs") is not None:
        gepruefte: list[str] = []
        for eintrag in felder["working_dirs"]:
            pfad = Path(eintrag).expanduser()
            if not pfad.is_absolute():
                raise HTTPException(400, t("fehler.arbeitsverzeichnis_relativ", sprache))
            if not pfad.exists():
                raise HTTPException(400, t("fehler.arbeitsverzeichnis_fehlt", sprache))
            if not pfad.is_dir():
                raise HTTPException(400, t("fehler.arbeitsverzeichnis_kein_ordner", sprache))
            aufgeloest = str(pfad.resolve())
            # Sharing the same folder twice is not an error, but it isn't a
            # second share either — merge silently.
            if aufgeloest not in gepruefte:
                gepruefte.append(aufgeloest)
        if len(gepruefte) > ARBEITSORDNER_HOECHSTENS:
            raise HTTPException(
                400,
                t("fehler.arbeitsverzeichnis_zu_viele", sprache).format(
                    anzahl=ARBEITSORDNER_HOECHSTENS
                ),
            )
        felder["working_dirs"] = gepruefte

    # Pinning runs separately because it must not change 'last used'.
    if (angeheftet := felder.pop("pinned", None)) is not None:
        repositories.chats.anheften(chat_id, angeheftet)

    if felder:
        return ChatAntwort.aus(repositories.chats.aktualisieren(chat_id, **felder))
    return ChatAntwort.aus(repositories.chats.holen(chat_id))


@router.delete(
    "/{chat_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    summary="Chat löschen",
)
async def chat_loeschen(
    chat_id: str,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> None:
    _chat_oder_404(repositories, chat_id, user_id, sprache)
    repositories.chats.loeschen(chat_id, user_id=user_id)
    # What the database holds goes with the row (foreign keys, cascade).
    # What lives in memory has to be told: the guardian's findings belong to
    # a conversation that no longer exists, and nobody would ever come to
    # collect them.
    waechter.wache.vergessen(chat_id)
    await bus.veroeffentlichen(Ereignisse.CHAT_GELOESCHT, chat_id=chat_id, user_id=user_id)


# --- Messages ------------------------------------------------------------


@router.get(
    "/{chat_id}/messages",
    response_model=list[NachrichtAntwort],
    summary="Nachrichten eines Chats",
)
def nachrichten_auflisten(
    chat_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> list[NachrichtAntwort]:
    _chat_oder_404(repositories, chat_id, user_id, sprache)
    nachrichten = repositories.messages.auflisten(
        chat_id=chat_id, limit=limit, offset=offset
    )

    # Document messages carry only the id — the server builds the meta card
    # for the window from the documents row (4.1).
    def meta(nachricht):
        if not nachricht.dokument:
            return None
        from app.api.v1.dokumente import meta_bauen

        dokument = repositories.documents.holen(nachricht.dokument)
        return meta_bauen(dokument).model_dump() if dokument else None

    return [NachrichtAntwort.aus(nachricht, meta(nachricht)) for nachricht in nachrichten]


@router.post(
    "/{chat_id}/messages",
    response_model=NachrichtAntwort,
    status_code=201,
    summary="Nachricht speichern",
)
async def nachricht_speichern(
    chat_id: str,
    daten: NachrichtAnlegen,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> NachrichtAntwort:
    _chat_oder_404(repositories, chat_id, user_id, sprache)
    nachricht = repositories.messages.speichern(
        chat_id=chat_id,
        role=daten.role,
        content=daten.content,
        reasoning=daten.reasoning,
        stats=daten.stats,
    )
    repositories.chats.zeitstempel_auffrischen(chat_id)
    await bus.veroeffentlichen(
        Ereignisse.NACHRICHT_GESPEICHERT, chat_id=chat_id, message_id=nachricht.id
    )
    return NachrichtAntwort.aus(nachricht)


@router.delete(
    "/{chat_id}/messages/{message_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    summary="Nachricht löschen",
)
def nachricht_loeschen(
    chat_id: str,
    message_id: str,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> None:
    _chat_oder_404(repositories, chat_id, user_id, sprache)
    nachricht = repositories.messages.holen(message_id)
    if nachricht is None or nachricht.chat_id != chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("fehler.nachricht_nicht_gefunden", sprache),
        )
    repositories.messages.loeschen(message_id)
