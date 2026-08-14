"""The guardian's findings for a chat.

Two routes, and that is the whole surface: read what is standing, and throw
one away. There is no route for "send it" — sending is a message like any
other and goes down the path every message goes down, so the panel's button
does exactly what typing the sentence by hand would do.

Nothing is written to the database here. The findings live in memory with
the run they belong to (see ``app/waechter.py``).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app import waechter

router = APIRouter(prefix="/guardian", tags=["guardian"])


class BefundAntwort(BaseModel):
    id: int
    art: str
    werkzeug: str
    ergebnis: str
    vorschlag: str | None = None
    # Why there is no suggestion, when the reason is not the model's answer
    # but the guardian's own server being down. The KEY of a sentence, not
    # the sentence — a chat reopened in another language must not show the
    # note in the language it was written in.
    hinweis: str | None = None


@router.get("/{chat_id}", response_model=list[BefundAntwort], summary="Befunde eines Chats")
def befunde(chat_id: str) -> list[dict]:
    return [eintrag.als_daten() for eintrag in waechter.wache.liste(chat_id)]


@router.delete(
    "/{chat_id}/{befund_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    summary="Befund verwerfen",
)
def verwerfen(chat_id: str, befund_id: int) -> Response:
    if not waechter.wache.verwerfen(chat_id, befund_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diesen Befund gibt es nicht")
    return Response(status_code=204)
