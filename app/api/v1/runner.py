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
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app import modellzuordnung
from app.api.abhaengigkeiten import hole_sprache
from app.config import EndpointConfig
from app.i18n import t
from app.modelldownload import BILD_ENDUNGEN, DownloadFehler, Modelldownload
from app.feineinstellungen import Feineinstellungen
from app.modellrunner import Modellrunner, RunnerFehler, SCHLUESSEL_VARIABLE
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
        # The runner hands its server a fresh key at every start; requests
        # without it are turned away — the lock against web pages knocking
        # on localhost from inside the user's browser.
        api_key_env=SCHLUESSEL_VARIABLE,
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
    # Prediction modules in the folder — the built-in drafts. Their own
    # list for the same reason, with sizes because a draft is a passenger
    # in the memory plan.
    mtp: list[Modelldatei] = []
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
    # The engine levers the running server was started with, so the drawer
    # can show what is actually in force instead of its own defaults. None
    # while nothing runs — then the form falls back to the stored choice.
    fein: dict | None = None
    # Whether flash attention ended up on — read off the server's own log,
    # not off what was asked for, because the flag sent is always "auto".
    # None while nothing runs yet or the log has not reached that line.
    flash_aktiv: bool | None = None
    # Whether the drafter (MTP / speculative decoding) actually engaged — read
    # off the server's own log, not off the fact that one was configured.
    # None → none asked for or still loading; "aktiv" → its init line passed
    # (the bolt lights blue); "fehler" → the server came up without it, so a
    # drafter was set but never took (the bolt turns red).
    mtp_aktiv: str | None = None
    # The declared bond of each model to its companions, read from the folder
    # manifest and filtered to files that are still there. Keyed by model
    # file name; each value carries the projector and the draft, or null. The
    # window shows the association and pre-selects the right draft without
    # guessing from name prefixes.
    zuordnung: dict[str, dict[str, str | None]] = {}


class Start(BaseModel):
    modell: str
    kontext: int = Field(8192, ge=512, le=1_048_576)
    schichten: int = Field(99, ge=0, le=999)
    port: int = Field(8080, ge=1024, le=65535)
    # Optional draft model for speculative decoding — a small file from the
    # same folder that guesses ahead while the big one only checks.
    drafter: str | None = None
    # The advanced section's levers, as sent. Kept loose on purpose: the
    # clamping and the fallback for an unknown name live in one place, next
    # to the flags they turn into.
    fein: dict | None = None


def hole_runner(request: Request) -> Modellrunner:
    return request.app.state.modellrunner


def _zuordnung(runner: Modellrunner) -> dict[str, dict[str, str | None]]:
    """The folder manifest, filtered to model files that are still present.

    A model whose file is gone drops out entirely, and inside each entry a
    deleted companion drops out too, so the window never offers a bond to a
    file that is no longer there. The same folder boundary as the start: a
    key that resolves outside the model folder is ignored.
    """
    ordner = Path(runner.ordner)
    basis = ordner.resolve()
    ergebnis: dict[str, dict[str, str | None]] = {}
    for modell in modellzuordnung.lade(ordner):
        ziel = (ordner / modell).resolve()
        if ziel.parent != basis or not ziel.is_file():
            continue
        ergebnis[modell] = modellzuordnung.fuer(ordner, modell)
    return ergebnis


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
        mtp=[Modelldatei(name=m.name, groesse_gb=m.groesse_gb) for m in runner.mtp()],
        speicher_gb=gesamt_gb(),
        belegt_gb=runner.belegt_gb(),
        laeuft=runner.laeuft(),
        modell=lauf.modell if lauf else None,
        kontext=lauf.kontext if lauf else None,
        schichten=lauf.schichten if lauf else None,
        port=lauf.port if lauf else None,
        drafter=lauf.drafter if lauf else None,
        fein=lauf.fein.als_daten() if lauf and lauf.fein else None,
        flash_aktiv=runner.flash_attn_zustand(),
        mtp_aktiv=runner.mtp_zustand(),
        zuordnung=_zuordnung(runner),
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
            fein=Feineinstellungen.aus_daten(daten.fein),
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
    # The model this file is a companion of, and which place it takes next to
    # it. Set together, they write the bond into the folder manifest once the
    # file has arrived; absent, the download behaves as before. The role is
    # constrained here, so nothing but a projector or a draft is ever
    # declared.
    gehoert_zu: str | None = Field(None, min_length=1, max_length=200)
    rolle: Literal["mmproj", "mtp"] | None = None
    # Which kind of model this is — one of the catalogue's tabs. It decides
    # the destination folder, because each server reads only its own folder:
    # an embedding model in the chat folder is invisible to the embedding
    # server and a broken entry in the chat list.
    art: Literal["chat", "einbettung", "bild"] = "chat"
    # A companion lands in a sub-folder of its server, so it shows up where it
    # belongs at once and its folder shows only its own kind: a VAE in vae/, a
    # LoRA in lora/, a face detector in adetailer/ on the picture side; a
    # drafter in mtp/, a projector in vision/ on the chat side. A closed
    # whitelist, never a free path — the download can never write outside these.
    unterordner: Literal["vae", "lora", "adetailer", "mtp", "vision"] | None = None


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
    request: Request,
    download: Modelldownload = Depends(hole_download),
    sprache: str = Depends(hole_sprache),
) -> Fortschritt:
    wurzel = request.app.state.modellordner_je_art.get(daten.art)
    # A companion goes into its sub-folder of the same art. The whitelist on
    # the field is what makes the join safe — no "../" can reach this point.
    # The manifest stays with the model (the art root), not in the sub-folder,
    # so the runner reads the bond from where the model lies.
    ordner = wurzel
    if wurzel is not None and daten.unterordner:
        ordner = str(Path(wurzel) / daten.unterordner)
    # An image model may be safetensors; a chat or embedding model is GGUF
    # only — the one form the runner can start.
    endungen = BILD_ENDUNGEN if daten.art == "bild" else (".gguf",)
    try:
        download.starten(
            daten.repo, daten.datei, daten.ziel, daten.gehoert_zu, daten.rolle,
            ordner=ordner, endungen=endungen, manifest_ordner=wurzel,
        )
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


@router.post("/begleiter-folder/{unterordner}", response_model=bool,
             summary="Begleiter-Ordner zeigen")
def begleiterordner_zeigen(
    unterordner: Literal["mtp", "vision"],
    runner: Modellrunner = Depends(hole_runner),
    sprache: str = Depends(hole_sprache),
) -> bool:
    """Open the drafter or projector sub-folder of the model folder so a file
    can be dropped in by hand. Created if missing; the whitelist on the path is
    what keeps this from opening anything but a companion folder."""
    ordner = runner.ordner / unterordner
    ordner.mkdir(parents=True, exist_ok=True)
    try:
        ordner_oeffnen(ordner)
    except OeffnenNichtMoeglich:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, t("fehler.ordner_oeffnen", sprache)
        ) from None
    return True
