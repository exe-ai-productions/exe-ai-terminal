"""The embedding server, from outside.

The same three questions the model server answers — what is there, is it
running, start and stop it — and deliberately nothing more. It is a small
service with one job, so it needs no context size, no layer count, no draft
model, no projector.

Its own route rather than a mode of the runner route next door: the two
servers must be startable independently, and a shared route is exactly how
they end up sharing a port.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.config import Config
from app.einbettung import modelle as einbettungsmodelle
from app.einbettungsserver import STAPEL
from app.i18n import t
from app.modellrunner import RunnerFehler
from app.ordner_oeffnen import OeffnenNichtMoeglich, ordner_oeffnen

router = APIRouter(prefix="/einbettungsserver", tags=["einbettungsserver"])


class Auskunft(BaseModel):
    programm: str | None = None
    ordner: str
    modelle: list[str]
    laeuft: bool
    modell: str | None = None
    port: int | None = None


class Start(BaseModel):
    modell: str = Field(min_length=1, max_length=200)
    # The one number this server has. Its own, because sharing a port with
    # the chat model is exactly what this server exists apart from.
    port: int | None = Field(default=None, ge=1024, le=65535)


def _runner(request: Request):
    return request.app.state.einbettungsrunner


def _auskunft(request: Request, config: Config) -> Auskunft:
    runner = _runner(request)
    lauf = runner.lauf()
    return Auskunft(
        programm=str(runner.programm) if runner.programm else None,
        ordner=str(runner.ordner),
        modelle=einbettungsmodelle(runner.ordner),
        laeuft=runner.laeuft(),
        modell=lauf.modell if lauf else None,
        port=lauf.port if lauf else runner.port_vorgabe,
    )


@router.get("", response_model=Auskunft, summary="Einbettungsserver — Auskunft")
def auskunft(request: Request, config: Config = Depends(hole_config)) -> Auskunft:
    return _auskunft(request, config)


@router.get("/log", response_model=list[str], summary="Was der Server sagt")
def protokoll(request: Request) -> list[str]:
    return _runner(request).protokoll()


@router.post("/start", response_model=Auskunft, summary="Einbettungsserver starten")
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
        _runner(request).starten(daten.modell, port=daten.port, kontext=STAPEL)
    except RunnerFehler as fehler:
        lage = {
            "laeuft_schon": status.HTTP_409_CONFLICT,
            "port_belegt": status.HTTP_409_CONFLICT,
            "kein_programm": status.HTTP_412_PRECONDITION_FAILED,
            "kein_modell": status.HTTP_404_NOT_FOUND,
        }.get(fehler.grund, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(lage, t(f"fehler.runner_{fehler.grund}", sprache)) from None
    # Deliberately NOT registered with the discovery: this server answers
    # embeddings, not chat. A model picker that offered it would let somebody
    # send a conversation to something that cannot hold one.
    return _auskunft(request, config)


@router.post("/stop", response_model=Auskunft, summary="Einbettungsserver anhalten")
def stoppen(request: Request, config: Config = Depends(hole_config)) -> Auskunft:
    _runner(request).stoppen()
    return _auskunft(request, config)


@router.post("/folder", response_model=bool, summary="Einbettungsmodelle zeigen")
def ordner_zeigen(request: Request, sprache: str = Depends(hole_sprache)) -> bool:
    """Its OWN folder — the button that used to point at the wrong one."""
    try:
        ordner_oeffnen(Path(_runner(request).ordner))
    except OeffnenNichtMoeglich:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, t("fehler.ordner_oeffnen", sprache)
        ) from None
    return True
