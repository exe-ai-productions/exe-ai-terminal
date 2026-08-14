"""The endpoint behind the "Enhance" button in the picture window.

It is its own router and not a route in ``bild.py`` because it talks to a
different machine entirely: everything in ``bild.py`` speaks to the local
image generator, this one speaks to whichever language model the user has
loaded. Sharing a file would mean sharing imports and a mental model that
have nothing to do with each other.

The endpoint refuses rather than falls back. If no language model is
reachable, the honest answer is "there is nothing here to ask" — quietly
returning the prompt unchanged would look like a button that did nothing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app import denkschalter
from app.api.abhaengigkeiten import hole_sprache
from app.bildprompt import PromptFehler, verbessern
from app.discovery import Discovery
from app.i18n import t
from app.providers import ProviderFehler

router = APIRouter(tags=["bild"])


def hole_discovery(request: Request) -> Discovery:
    return request.app.state.discovery


class PromptWunsch(BaseModel):
    prompt: str = Field(min_length=1)
    # Which language model to ask. Empty means: whichever one is reachable —
    # the picture window has no model picker of its own and should not grow
    # one for this.
    endpoint_id: str | None = None


class PromptAntwort(BaseModel):
    prompt: str


@router.post(
    "/bild/prompt",
    response_model=PromptAntwort,
    summary="Bildprompt verbessern",
)
async def prompt_verbessern(
    wunsch: PromptWunsch,
    discovery: Discovery = Depends(hole_discovery),
    sprache: str = Depends(hole_sprache),
) -> PromptAntwort:
    zustand, modellname = _sprachmodell(discovery, wunsch.endpoint_id, sprache)
    try:
        ergebnis = await verbessern(
            zustand.provider, modellname, wunsch.prompt, denkschalter.zusatz(False, zustand)
        )
    except PromptFehler as fehler:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, t("bild.prompt_fehlgeschlagen", sprache)
        ) from fehler
    except ProviderFehler as fehler:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, t("bild.prompt_fehlgeschlagen", sprache)
        ) from fehler
    return PromptAntwort(prompt=ergebnis)


def _sprachmodell(discovery: Discovery, kennung: str | None, sprache: str):
    """The model to ask, or a 503 saying there is none.

    A named endpoint is honoured if it answers; without one the first
    reachable endpoint is taken. Embedding servers never appear among these
    — they are not registered as chat endpoints — so no filter is needed to
    keep the call away from one.
    """
    if kennung:
        gefunden = discovery.aufloesen(kennung)
        if gefunden is not None and gefunden[0].erreichbar:
            return gefunden
    for zustand in discovery.erreichbare():
        # The reported name, not None: a provider that is handed no model at
        # all leaves the field out of the request body, and the hosted ones
        # answer that with a 400 rather than with a prompt.
        return zustand, zustand.gemeldeter_name
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE, t("bild.prompt_kein_modell", sprache)
    )
