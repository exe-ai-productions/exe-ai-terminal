"""The command runs of a chat — what has run, and what is running right now.

Its own channel, not part of the answer stream, and for one reason: a
background run outlives the answer that started it. Hanging its lines on the
generation would mean they stop arriving the moment the model is done
talking, which is precisely when a long build is still going.

Two routes, and they belong together: the window asks once for what is there
and then keeps listening.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.abhaengigkeiten import hole_benutzer_id, hole_repositories, hole_sprache
from app.api.v1.schemas import BefehlAusfuehren
from app.db import Repositories
from app.i18n import t
from app.tools import shell
from app.tools.hintergrund import Lauf, laeufe

log = logging.getLogger(__name__)

router = APIRouter(prefix="/laeufe", tags=["laeufe"])

# A comment line often enough that a proxy or a sleeping laptop does not
# quietly drop the connection.
HERZSCHLAG_SEKUNDEN = 20.0


def _als_daten(lauf: Lauf) -> dict:
    return {
        "lauf": lauf.nummer,
        "befehl": lauf.befehl,
        "hintergrund": lauf.hintergrund,
        "zustand": lauf.zustand,
        "code": lauf.code,
        "ausgabe": lauf.ausgabe,
        "art": lauf.art,
        "dauer_sekunden": lauf.dauer_sekunden,
    }


@router.get("/{chat_id}", summary="Die Befehlsläufe eines Chats")
def laeufe_auflisten(chat_id: str) -> list[dict]:
    return [_als_daten(lauf) for lauf in laeufe.laeufe(chat_id)]


@router.get("/{chat_id}/stream", summary="Den Befehlsläufen zusehen (SSE)")
async def zusehen(chat_id: str) -> StreamingResponse:
    async def strom() -> AsyncIterator[str]:
        quelle = laeufe.zuschauen(chat_id)
        try:
            while True:
                try:
                    ereignis = await asyncio.wait_for(
                        quelle.__anext__(), timeout=HERZSCHLAG_SEKUNDEN
                    )
                except asyncio.TimeoutError:
                    yield ": still here\n\n"
                    continue
                yield f"data: {json.dumps(ereignis, ensure_ascii=False)}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            raise
        finally:
            await quelle.aclose()

    return StreamingResponse(
        strom(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{chat_id}/befehl", summary="Einen Befehl aus dem CLI-Modul ausführen")
async def befehl_ausfuehren(
    chat_id: str,
    daten: BefehlAusfuehren,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> dict:
    """Runs one command for the CLI module — the same runner the model uses.

    Same folders, same block list, same limits: there is one way to run a
    command in this program, and the CLI is not a second one.

    One difference, and it is deliberate: a path outside the shared folders
    is refused here instead of asked about. The confirmation belongs to a
    running answer, which is what holds the call open and can wait for a
    click. The CLI has no such run, so it says no and names the path —
    whoever wants it anyway shares the folder or asks in the chat.
    """
    chat = repositories.chats.holen(chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.allgemein", sprache))

    ordner = list(chat.working_dirs or [])
    argumente = {"command": daten.command}
    aussen = shell.aussenpfad(argumente, ordner)
    if aussen:
        return {
            "text": t("cli.ausserhalb", sprache, pfad=aussen),
            "fehlgeschlagen": True,
        }

    try:
        text = await shell.ausfuehren(argumente, ordner, chat_id)
    except shell.ShellVerboten as fehler:
        return {"text": str(fehler), "fehlgeschlagen": True}
    return {"text": text, "fehlgeschlagen": False}
