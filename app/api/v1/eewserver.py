"""Extended Workflow, from outside.

Three questions, and deliberately no more: which small models are there, is
the guardian's own one running, and switch it on or off. Everything that
decides HOW it runs — window, temperature, answer budget — is derived in
`waechter.py` from what the guardian's code can produce, and is not offered
here. A page cannot ask a better question about it than the code already
answers.

Its own route rather than a mode of the runner route next door, for the same
reason the embedding server has one: the servers must be startable
independently, and a shared route is how they end up sharing a port.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.config import Config
from app.eewserver import MODELL_VORGABE
from app.i18n import t
from app.modellrunner import RunnerFehler, modelle_auflisten
from app.waechter import KONTEXT

router = APIRouter(prefix="/eew", tags=["eew"])


class Auskunft(BaseModel):
    programm: str | None = None
    ordner: str
    # The models this server could be given. The same folder the chat model
    # uses — a small model is a model.
    modelle: list[str]
    laeuft: bool
    modell: str | None = None
    port: int | None = None
    # What is chosen when nobody has chosen: the model the six checkpoints
    # were measured on.
    vorgabe: str = MODELL_VORGABE


class Start(BaseModel):
    modell: str = Field(min_length=1, max_length=200)


def _runner(request: Request):
    return request.app.state.eewrunner


def _auskunft(request: Request) -> Auskunft:
    runner = _runner(request)
    lauf = runner.lauf()
    return Auskunft(
        programm=str(runner.programm) if runner.programm else None,
        ordner=str(runner.ordner),
        modelle=[m.name for m in modelle_auflisten(runner.ordner)],
        laeuft=runner.laeuft(),
        modell=lauf.modell if lauf else None,
        port=lauf.port if lauf else runner.port_vorgabe,
    )


@router.get("", response_model=Auskunft, summary="Extended Workflow — Auskunft")
def auskunft(request: Request) -> Auskunft:
    return _auskunft(request)


@router.get("/log", response_model=list[str], summary="Was der Server sagt")
def protokoll(request: Request) -> list[str]:
    return _runner(request).protokoll()


@router.post("/start", response_model=Auskunft, summary="Extended Workflow einschalten")
def starten(
    daten: Start,
    request: Request,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> Auskunft:
    try:
        # The window travels as a start value, not as an extra flag — one
        # `--ctx-size` on the command line, written by the one place that
        # writes command lines.
        _runner(request).starten(daten.modell, kontext=KONTEXT)
    except RunnerFehler as fehler:
        lage = {
            "laeuft_schon": status.HTTP_409_CONFLICT,
            "port_belegt": status.HTTP_409_CONFLICT,
            "kein_programm": status.HTTP_412_PRECONDITION_FAILED,
            "kein_modell": status.HTTP_404_NOT_FOUND,
        }.get(fehler.grund, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(lage, t(f"fehler.runner_{fehler.grund}", sprache)) from None
    # Deliberately NOT registered with the discovery. This model writes repair
    # suggestions; a model picker offering it would let somebody send a
    # conversation to a server started for something else entirely.
    return _auskunft(request)


@router.post("/stop", response_model=Auskunft, summary="Extended Workflow ausschalten")
def stoppen(request: Request) -> Auskunft:
    _runner(request).stoppen()
    return _auskunft(request)
