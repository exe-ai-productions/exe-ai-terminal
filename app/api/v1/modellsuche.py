"""Searching Hugging Face for a model that can run on this machine.

The program has always assumed a model server was already running. For
whoever installs it fresh, that assumption is the whole problem: nothing
happens, and nothing says why. Finding a model is the first half of the
answer — running it is the second, and that one belongs to the runner that
does not exist yet.

Only GGUF is offered, on purpose: it is the one kind the program can fetch
as a single file and start by itself. Everything else on Hugging Face needs
Python, a framework or a graphics card to be sorted out first — that is a
different program, not ours. MLX runs beautifully on Apple silicon and is
still out, for the same reason it left the runner: it cannot travel with an
installer.

The search runs on the server and not in the browser: the page would have
to talk to a foreign host itself, and then every user's address ends up in
someone else's log for a search they only wanted to type.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.abhaengigkeiten import hole_sprache
from app.i18n import t

router = APIRouter(prefix="/models", tags=["modellsuche"])

HF_ADRESSE = "https://huggingface.co/api/models"

# What we can do something with. The key is what the caller asks for, the
# value is what Hugging Face calls it.
ARTEN = {"gguf": "gguf"}

MAX_TREFFER = 24


class Fund(BaseModel):
    id: str
    name: str
    anbieter: str
    art: str
    ladungen: int
    beliebt: int
    aufgabe: str | None = None


def _fund_bauen(eintrag: dict[str, Any], art: str) -> Fund:
    kennung = eintrag.get("modelId") or eintrag.get("id") or ""
    anbieter, _, name = kennung.partition("/")
    return Fund(
        id=kennung,
        name=name or kennung,
        anbieter=anbieter if name else "",
        art=art,
        ladungen=int(eintrag.get("downloads") or 0),
        beliebt=int(eintrag.get("likes") or 0),
        aufgabe=eintrag.get("pipeline_tag"),
    )


@router.get("/search", response_model=list[Fund], summary="Modelle suchen")
async def suchen(
    q: str = Query(min_length=1, max_length=100),
    art: str = Query("gguf"),
    anzahl: int = Query(12, ge=1, le=MAX_TREFFER),
    sprache: str = Depends(hole_sprache),
) -> list[Fund]:
    if art not in ARTEN:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, t("fehler.modellsuche_art", sprache)
        )

    parameter = {
        "search": q,
        "filter": ARTEN[art],
        "sort": "downloads",
        "direction": "-1",
        "limit": anzahl,
    }

    try:
        import os

        kopf = {}
        wert = os.environ.get("HF_TOKEN", "").strip()
        if wert:
            kopf["Authorization"] = f"Bearer {wert}"
        async with httpx.AsyncClient(timeout=15, headers=kopf) as client:
            antwort = await client.get(HF_ADRESSE, params=parameter)
            antwort.raise_for_status()
            daten = antwort.json()
    except httpx.HTTPError:
        # The catalogue is somebody else's server. It being down is a normal
        # day, not an error in this program — and it says so instead of
        # showing an empty list that looks like "nothing found".
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, t("fehler.modellsuche_fern", sprache)
        ) from None

    if not isinstance(daten, list):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, t("fehler.modellsuche_fern", sprache)
        )

    return [_fund_bauen(eintrag, art) for eintrag in daten if isinstance(eintrag, dict)]
