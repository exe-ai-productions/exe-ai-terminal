"""Which models are currently reachable (phase 1.4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.abhaengigkeiten import hole_sprache
from app.api.v1.schemas import ModellAntwort
from app.discovery import Discovery

router = APIRouter(tags=["modelle"])


def hole_discovery(request: Request) -> Discovery:
    return request.app.state.discovery


@router.get("/models", response_model=list[ModellAntwort], summary="Verfügbare Modelle")
async def modelle(
    alle: bool = Query(
        default=False,
        description="Auch nicht erreichbare Kandidaten mit ausgeben (für Diagnose).",
    ),
    jetzt_pruefen: bool = Query(
        default=False, description="Vor der Antwort einen frischen Health-Check machen."
    ),
    discovery: Discovery = Depends(hole_discovery),
    sprache: str = Depends(hole_sprache),
) -> list[ModellAntwort]:
    if jetzt_pruefen:
        await discovery.einmal_pruefen()

    zustaende = discovery.alle() if alle else discovery.erreichbare()
    # One entry per model, not per address: a provider with a catalogue
    # appears once for each model it offers.
    return [
        ModellAntwort(**zustand.als_dict(modell, sprache))
        for zustand, modell in discovery.aufgefaechert(zustaende)
    ]
