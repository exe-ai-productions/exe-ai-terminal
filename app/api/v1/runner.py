"""The model server, seen and switched from the program.

Everything this offers is a fact the window can show: is the program there,
which files could be loaded, what is running with which settings, and what
the server itself is saying right now.

The command is handed out as well, and deliberately so — it is the same list
that gets executed, so what the window shows cannot drift away from what
actually starts.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_sprache
from app.config import EndpointConfig
from app.i18n import t
from app.modelldownload import DownloadFehler, Modelldownload
from app.modellrunner import Modellrunner, RunnerFehler
from app.systemspeicher import gesamt_gb
from app.ordner_oeffnen import OeffnenNichtMoeglich, ordner_oeffnen
from app.serverdownload import Serverdownload, ServerdownloadFehler

router = APIRouter(prefix="/runner", tags=["runner"])

# The id under which the started server appears among the models. Fixed, so
# a second start replaces the first entry instead of adding one.
RUNNER_ID = "runner"


def _runner_endpunkt(port: int) -> EndpointConfig:
    """The endpoint the started server answers on.

    Built here and not written to the configuration: the entry lives exactly
    as long as the server it describes, and its port is whatever the form
    said at start.
    """
    return EndpointConfig(
        id=RUNNER_ID,
        base_url=f"http://127.0.0.1:{port}/v1",
        provider="openai_compatible",
        parameter_dialect="llama_cpp",
        group="local",
    )


class Modelldatei(BaseModel):
    name: str
    groesse_gb: float


class Auskunft(BaseModel):
    programm: str | None
    ordner: str
    modelle: list[Modelldatei]
    # Vision companions in the folder. Their own list, not model entries:
    # they cannot start, but the window needs to know they are there.
    mmproj: list[str] = []
    # The machine's memory — the honest ceiling any start plan has to fit.
    speicher_gb: float | None = None
    # What the running server holds right now — None while it is off.
    belegt_gb: float | None = None
    laeuft: bool
    modell: str | None = None
    kontext: int | None = None
    schichten: int | None = None
    port: int | None = None
    drafter: str | None = None


class Start(BaseModel):
    modell: str
    kontext: int = Field(8192, ge=512, le=1_048_576)
    schichten: int = Field(99, ge=0, le=999)
    port: int = Field(8080, ge=1024, le=65535)
    # Optional draft model for speculative decoding — a small file from the
    # same folder that guesses ahead while the big one only checks.
    drafter: str | None = None


def hole_runner(request: Request) -> Modellrunner:
    return request.app.state.modellrunner


def _fehler(grund: str, sprache: str) -> HTTPException:
    lage = {
        "laeuft_schon": status.HTTP_409_CONFLICT,
        "port_belegt": status.HTTP_409_CONFLICT,
        "kein_programm": status.HTTP_412_PRECONDITION_FAILED,
        "kein_modell": status.HTTP_404_NOT_FOUND,
    }.get(grund, status.HTTP_400_BAD_REQUEST)
    return HTTPException(lage, t(f"fehler.runner_{grund}", sprache))


@router.get("", response_model=Auskunft, summary="Modellserver — Auskunft")
def auskunft(runner: Modellrunner = Depends(hole_runner)) -> Auskunft:
    lauf = runner.lauf()
    return Auskunft(
        programm=str(runner.programm) if runner.programm else None,
        ordner=str(runner.ordner),
        modelle=[Modelldatei(name=m.name, groesse_gb=m.groesse_gb) for m in runner.modelle()],
        mmproj=runner.mmproj(),
        speicher_gb=gesamt_gb(),
        belegt_gb=runner.belegt_gb(),
        laeuft=runner.laeuft(),
        modell=lauf.modell if lauf else None,
        kontext=lauf.kontext if lauf else None,
        schichten=lauf.schichten if lauf else None,
        port=lauf.port if lauf else None,
        drafter=lauf.drafter if lauf else None,
    )


@router.get("/log", response_model=list[str], summary="Was der Server sagt")
def protokoll(runner: Modellrunner = Depends(hole_runner)) -> list[str]:
    return runner.protokoll()


@router.post("/start", response_model=Auskunft, summary="Modellserver starten")
async def starten(
    daten: Start,
    request: Request,
    runner: Modellrunner = Depends(hole_runner),
    sprache: str = Depends(hole_sprache),
) -> Auskunft:
    try:
        runner.starten(
            daten.modell,
            kontext=daten.kontext,
            schichten=daten.schichten,
            port=daten.port,
            drafter=daten.drafter,
        )
    except RunnerFehler as fehler:
        raise _fehler(fehler.grund, sprache) from None
    # The started server joins the model list by itself. Without this the
    # chain broke exactly at its last link: fetch, start — and the chat still
    # said no model was reachable, because nobody had told the discovery.
    await request.app.state.discovery.anmelden(_runner_endpunkt(daten.port))
    return auskunft(runner)


@router.post("/stop", response_model=Auskunft, summary="Modellserver anhalten")
async def stoppen(
    request: Request, runner: Modellrunner = Depends(hole_runner)
) -> Auskunft:
    runner.stoppen()
    await request.app.state.discovery.abmelden(RUNNER_ID)
    return auskunft(runner)


# --- Fetching a model -----------------------------------------------------


class Holen(BaseModel):
    repo: str = Field(min_length=1, max_length=200)
    datei: str = Field(min_length=1, max_length=200)
    # Local name, when it must differ from the remote one — see
    # Modelldownload.starten.
    ziel: str | None = Field(None, min_length=1, max_length=200)


class Fortschritt(BaseModel):
    datei: str
    geladen: int
    gesamt: int
    anteil: float
    fertig: bool
    fehler: str | None = None


def hole_download(request: Request) -> Modelldownload:
    return request.app.state.modelldownload


def _stand(download: Modelldownload) -> Fortschritt | None:
    stand = download.stand()
    if stand is None:
        return None
    return Fortschritt(
        datei=stand.datei,
        geladen=stand.geladen,
        gesamt=stand.gesamt,
        anteil=stand.anteil,
        fertig=stand.fertig,
        fehler=stand.fehler,
    )


@router.get("/download", response_model=Fortschritt | None, summary="Wie weit ist es")
def fortschritt(download: Modelldownload = Depends(hole_download)) -> Fortschritt | None:
    return _stand(download)


@router.post("/download", response_model=Fortschritt, summary="Modell holen")
def holen(
    daten: Holen,
    download: Modelldownload = Depends(hole_download),
    sprache: str = Depends(hole_sprache),
) -> Fortschritt:
    try:
        download.starten(daten.repo, daten.datei, daten.ziel)
    except DownloadFehler as fehler:
        lage = {
            "laeuft_schon": status.HTTP_409_CONFLICT,
            "schon_da": status.HTTP_409_CONFLICT,
        }.get(fehler.grund, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(lage, t(f"fehler.download_{fehler.grund}", sprache)) from None
    stand = _stand(download)
    assert stand is not None
    return stand


@router.delete("/download", response_model=bool, summary="Holen abbrechen")
def abbrechen(download: Modelldownload = Depends(hole_download)) -> bool:
    return download.abbrechen()


# --- Fetching the model server itself -------------------------------------


class ServerFortschritt(BaseModel):
    geladen: int
    gesamt: int
    anteil: float
    fertig: bool
    fehler: str | None = None


def hole_serverdownload(request: Request) -> Serverdownload:
    return request.app.state.serverdownload


def _serverstand(download: Serverdownload) -> ServerFortschritt | None:
    stand = download.stand()
    if stand is None:
        return None
    return ServerFortschritt(
        geladen=stand.geladen,
        gesamt=stand.gesamt,
        anteil=stand.anteil,
        fertig=stand.fertig,
        fehler=stand.fehler,
    )


@router.get(
    "/programm", response_model=ServerFortschritt | None, summary="Wie weit ist der Server"
)
def server_fortschritt(
    download: Serverdownload = Depends(hole_serverdownload),
) -> ServerFortschritt | None:
    return _serverstand(download)


@router.post("/programm", response_model=ServerFortschritt, summary="Modellserver holen")
def server_holen(
    download: Serverdownload = Depends(hole_serverdownload),
    sprache: str = Depends(hole_sprache),
) -> ServerFortschritt:
    """Fetches llama-server from the official llama.cpp release.

    The one step that used to be an instruction ("install llama.cpp") is a
    button now — a machine without the server gets it in one click, into
    the user's data folder, where the runner looks by itself.
    """
    try:
        download.starten()
    except ServerdownloadFehler as fehler:
        lage = {
            "laeuft_schon": status.HTTP_409_CONFLICT,
            "schon_da": status.HTTP_409_CONFLICT,
        }.get(fehler.grund, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(
            lage, t(f"fehler.serverdownload_{fehler.grund}", sprache)
        ) from None
    stand = _serverstand(download)
    assert stand is not None
    return stand


@router.post("/folder", response_model=bool, summary="Modellordner zeigen")
def ordner_zeigen(
    runner: Modellrunner = Depends(hole_runner),
    sprache: str = Depends(hole_sprache),
) -> bool:
    """Opens the model folder in the file manager.

    Always this one folder and never a path from outside — the request
    carries no body on purpose.
    """
    try:
        ordner_oeffnen(runner.ordner)
    except OeffnenNichtMoeglich:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, t("fehler.ordner_oeffnen", sprache)
        ) from None
    return True
