"""Showing a shared working folder in the file manager.

One route, and the whole point of it is what it refuses. The client never
says which path to open — it says which chat and which of that chat's shared
folders. The path itself comes out of the chat row, so a request cannot ask
for a folder the user never shared, however it is spelled.

The opening itself is ``app/ordner_oeffnen.py``, the same one the model
folder uses.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.abhaengigkeiten import hole_benutzer_id, hole_repositories, hole_sprache
from app.api.v1.schemas import OrdnerOeffnen
from app.db import Repositories
from app.i18n import t
from app.ordner_oeffnen import OeffnenNichtMoeglich, ordner_oeffnen

router = APIRouter(prefix="/ordner", tags=["ordner"])


@router.post("/oeffnen", response_model=bool, summary="Einen Arbeitsordner zeigen")
def oeffnen(
    daten: OrdnerOeffnen,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> bool:
    chat = repositories.chats.holen(daten.chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.allgemein", sprache))

    freigaben = list(chat.working_dirs or [])
    if daten.pfad not in freigaben:
        # Not "not found": the folder may well exist. It is simply not one
        # this chat shared, and that is the whole boundary.
        raise HTTPException(status.HTTP_403_FORBIDDEN, t("fehler.allgemein", sprache))

    try:
        ordner_oeffnen(Path(daten.pfad))
    except OeffnenNichtMoeglich:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, t("fehler.ordner_oeffnen", sprache)
        ) from None
    return True
