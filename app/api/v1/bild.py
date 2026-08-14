"""Drawing a picture on this machine.

Separate from ``bilder.py`` next door on purpose: that one takes pictures IN
(an upload for vision) and hands them back out again. This one makes them,
which is a different act with a different set of things that can go wrong —
no program installed, no room in memory, a run already going.

Everything a request can influence is clamped here rather than at the
generator. A number that arrives out of range is not an error to report but
a value to bring into range: a slider that was dragged is not a mistake, and
the one case that IS refused — a model name that is not a model — is refused
because it is the only one where guessing would be dangerous.
"""

from __future__ import annotations

import asyncio
import secrets
import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.bildrunner import (
    Auftrag, BildFehler, Bildrunner, LoRA, loras, lora_pfad, modelle, modell_pfad,
)
from app import bildwahlen
from app import bildlauf, bildspeicher, systemspeicher
from pathlib import Path

from app.config import Config
from app.i18n import t
from app.ordner_oeffnen import OeffnenNichtMoeglich, ordner_oeffnen
from app.sddownload import Sddownload, SddownloadFehler

router = APIRouter(tags=["bild"])

# The ceilings. Wide enough for anything SD-1.5-class models do well, narrow
# enough that no single request can tie the machine up for an hour.
MAX_KANTE = 1536
MIN_KANTE = 256
MAX_SCHRITTE = 80
MIN_SCHRITTE = 1
MAX_CFG = 30.0
# Edges are rounded down to a multiple of this: the latent space works in
# blocks of eight, and an odd number would be silently rounded by the
# generator anyway — better to say what will happen than to have it happen.
RASTER = 8


class LoRAWunsch(BaseModel):
    name: str
    staerke: float = bildwahlen.LORA_VORGABE


class BildWunsch(BaseModel):
    modell: str
    # Where the picture should land. Without a chat the picture is only
    # made and named — useful for a script, and the one case in which
    # nothing is written to the history.
    chat_id: str | None = None
    # Which chat's little history this RUN is written into. Normally the same
    # chat the picture lands in; the picture server's test run sets only this
    # one, because that run is worth showing but the picture is not worth
    # keeping.
    lauf_chat: str | None = None
    prompt: str = Field(min_length=1, max_length=2000)
    negativ: str = Field(default="", max_length=2000)
    # The first model is trained on 512; 1024 stays available and costs
    # both time and quality on it.
    breite: int = 512
    hoehe: int = 512
    schritte: int = 20
    cfg: float = 7.0
    # -1 means: the generator picks one. Anything else is repeatable.
    seed: int = -1
    sampler: str = bildwahlen.SAMPLER_VORGABE
    scheduler: str = bildwahlen.SCHEDULER_VORGABE
    loras: list[LoRAWunsch] = Field(default_factory=list, max_length=8)
    # A picture already in this installation to start from, by the name the
    # server gave it — never a path.
    startbild: str | None = None
    staerke: float = bildwahlen.STAERKE_VORGABE
    # The mask, by the name this server gave it — like the starting image.
    maske: str | None = None


class BildAntwort(BaseModel):
    bild: str
    seed: int
    frage_id: str | None = None
    antwort_id: str | None = None


class BildmodellAntwort(BaseModel):
    modelle: list[str]
    loras: list[str] = Field(default_factory=list)
    sampler: list[str] = Field(default_factory=list)
    scheduler: list[str] = Field(default_factory=list)
    programm_da: bool
    ordner: str
    # `bereit` | `kein_modell` | `kein_programm` | `zeichnet`. Deliberately
    # not "running": sd.cpp is not a service that stands, it is a program
    # that is called. A tile claiming a server would be a tile that lies.
    stand: str


def _kante(wert: int) -> int:
    geklemmt = max(MIN_KANTE, min(MAX_KANTE, int(wert)))
    return geklemmt - (geklemmt % RASTER)


def _bildordner(config: Config) -> Path:
    return config.pfad(config.app.bildmodelle_verzeichnis)


def _runner(request: Request) -> Bildrunner:
    """The one runner, built at startup — so the lock is one lock.

    Deliberately NOT created here on first use. Two requests arriving at the
    same moment would both find nothing and both build one, and two runners
    hold two locks: exactly the situation the lock exists to prevent.
    """
    return request.app.state.bildrunner


@router.get("/bild/modelle", response_model=BildmodellAntwort, summary="Bildmodelle")
def bildmodelle(request: Request, config: Config = Depends(hole_config)) -> BildmodellAntwort:
    runner = _runner(request)
    gefunden = modelle(_bildordner(config))
    programm_da = runner.programm is not None
    return BildmodellAntwort(
        modelle=gefunden,
        loras=loras(_bildordner(config)),
        sampler=list(bildwahlen.SAMPLER),
        scheduler=list(bildwahlen.SCHEDULER),
        programm_da=programm_da,
        ordner=str(_bildordner(config)),
        stand=(
            "zeichnet" if runner.laeuft()
            else "kein_programm" if not programm_da
            else "bereit" if gefunden
            else "kein_modell"
        ),
    )


@router.post("/bild/folder", response_model=bool, summary="Bildmodelle zeigen")
def bildordner_zeigen(
    config: Config = Depends(hole_config), sprache: str = Depends(hole_sprache)
) -> bool:
    """Its OWN folder — every kind of model gets its own button."""
    try:
        ordner_oeffnen(_bildordner(config))
    except OeffnenNichtMoeglich:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, t("fehler.ordner_oeffnen", sprache)
        ) from None
    return True


# --- Fetching the generator itself ----------------------------------------


class GeneratorFortschritt(BaseModel):
    geladen: int
    gesamt: int
    anteil: float
    fertig: bool
    fehler: str | None = None


# One fetch object for the whole service, built on first ask and kept. Two
# requests arriving in the same moment would otherwise each build one, and
# two of them would download the same archive into the same file. The lock
# is what makes "check, then create" a single step.
_bauschloss = threading.Lock()


def hole_sddownload(request: Request, config: Config = Depends(hole_config)) -> Sddownload:
    with _bauschloss:
        vorhanden = getattr(request.app.state, "sddownload", None)
        if vorhanden is None:
            vorhanden = Sddownload(config.datenverzeichnis)
            request.app.state.sddownload = vorhanden
        return vorhanden


def _generatorstand(download: Sddownload) -> GeneratorFortschritt | None:
    stand = download.stand()
    if stand is None:
        return None
    return GeneratorFortschritt(
        geladen=stand.geladen,
        gesamt=stand.gesamt,
        anteil=stand.anteil,
        fertig=stand.fertig,
        fehler=stand.fehler,
    )


@router.get(
    "/bild/programm",
    response_model=GeneratorFortschritt | None,
    summary="Wie weit ist der Generator",
)
def generator_fortschritt(
    download: Sddownload = Depends(hole_sddownload),
) -> GeneratorFortschritt | None:
    return _generatorstand(download)


@router.post(
    "/bild/programm", response_model=GeneratorFortschritt, summary="Bildgenerator holen"
)
def generator_holen(
    download: Sddownload = Depends(hole_sddownload),
    sprache: str = Depends(hole_sprache),
) -> GeneratorFortschritt:
    """Fetches sd-cli from the official stable-diffusion.cpp release.

    The one thing this panel could not do was the one thing a fresh
    installation needs: it said the generator was missing and left it at
    that. Now the same sentence carries a button, and the program lands in
    the data folder where the runner looks by itself.
    """
    try:
        download.starten()
    except SddownloadFehler as fehler:
        lage = {
            "laeuft_schon": status.HTTP_409_CONFLICT,
            "schon_da": status.HTTP_409_CONFLICT,
        }.get(fehler.grund, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(lage, t(f"fehler.sddownload_{fehler.grund}", sprache)) from None
    stand = _generatorstand(download)
    assert stand is not None
    return stand


@router.post("/bild/stop", response_model=bool, summary="Bild abbrechen")
def bild_stoppen(request: Request) -> bool:
    """Ends the running picture. False when there was none.

    No id and no body: one picture runs at a time, so there is exactly one
    thing this can mean.
    """
    return _runner(request).stoppen()


@router.post("/bild/lora-folder", response_model=bool, summary="LoRA-Ordner zeigen")
def loraordner_zeigen(
    config: Config = Depends(hole_config), sprache: str = Depends(hole_sprache)
) -> bool:
    """Its own folder too — a stack nobody can fill is not a stack."""
    ordner = _bildordner(config) / bildwahlen.LORA_ORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    try:
        ordner_oeffnen(ordner)
    except OeffnenNichtMoeglich:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, t("fehler.ordner_oeffnen", sprache)
        ) from None
    return True


@router.post(
    "/bild",
    response_model=BildAntwort,
    status_code=status.HTTP_201_CREATED,
    summary="Bild erzeugen (offline)",
)
async def bild_erzeugen(
    wunsch: BildWunsch,
    request: Request,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> BildAntwort:
    runner = _runner(request)
    if runner.programm is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, t("bild.kein_programm", sprache)
        )
    try:
        pfad = modell_pfad(_bildordner(config), wunsch.modell)
    except BildFehler as fehler:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t(fehler.grund, sprache)) from fehler

    startbild = _startbild(config, wunsch.startbild, sprache)
    # A mask without a starting image has nothing to mask — dropped here
    # rather than passed on, so the command line stays honest.
    maske = _startbild(config, wunsch.maske, sprache) if startbild else None
    _speicher_pruefen(request, pfad, sprache)

    auftrag = Auftrag(
        modell=pfad,
        prompt=wunsch.prompt,
        negativ=wunsch.negativ,
        breite=_kante(wunsch.breite),
        hoehe=_kante(wunsch.hoehe),
        schritte=max(MIN_SCHRITTE, min(MAX_SCHRITTE, int(wunsch.schritte))),
        cfg=max(0.0, min(MAX_CFG, float(wunsch.cfg))),
        # "Let the generator pick" is turned into a real number HERE, not
        # left to the generator. The answer reports the seed, and a seed of
        # -1 tells nobody how to draw the same picture again — which is the
        # only reason to report one at all.
        seed=int(wunsch.seed) if wunsch.seed >= 0 else secrets.randbelow(2**31),
        # An unknown name is not an error to report but a value to bring
        # into range: the program would answer a usage message, which
        # reaches the user as "could not be drawn" and explains nothing.
        sampler=bildwahlen.sampler_pruefen(wunsch.sampler),
        scheduler=bildwahlen.scheduler_pruefen(wunsch.scheduler),
        loras=_loras(config, wunsch, sprache),
        lora_ordner=_bildordner(config) / bildwahlen.LORA_ORDNER,
        startbild=startbild,
        maske=maske,
        # Without a starting image the strength has nothing to act on.
        staerke=max(0.0, min(1.0, float(wunsch.staerke))) if startbild else 1.0,
    )
    name = uuid.uuid4().hex + ".png"
    ziel = config.datenverzeichnis / "bilder" / name

    # The run appears in the chat's little history the moment it starts, so a
    # picture that takes half a minute is visible as work rather than as
    # nothing happening.
    lauf = bildlauf.beginnen(wunsch.lauf_chat or wunsch.chat_id, wunsch.prompt)

    # The generator is a separate program that runs for half a minute; run
    # in a thread so the service keeps answering while it draws.
    try:
        await asyncio.to_thread(runner.erzeugen, auftrag, ziel)
    except BildFehler as fehler:
        schluessel = fehler.grund
        bildlauf.beenden(
            lauf,
            gescheitert=schluessel != "bild.abgebrochen",
            abgebrochen=schluessel == "bild.abgebrochen",
        )
        code = {
            "bild.laeuft_schon": status.HTTP_409_CONFLICT,
            # Asked for, not gone wrong — the window says nothing and the
            # working message simply disappears.
            "bild.abgebrochen": status.HTTP_499_CLIENT_CLOSED_REQUEST
            if hasattr(status, "HTTP_499_CLIENT_CLOSED_REQUEST")
            else 499,
        }.get(schluessel, status.HTTP_503_SERVICE_UNAVAILABLE)
        raise HTTPException(code, t(schluessel, sprache)) from fehler
    except BaseException:
        bildlauf.beenden(lauf, gescheitert=True)
        raise
    bildlauf.beenden(lauf)

    # Prompt and picture land in the chat as a message pair — the question
    # carries the prompt, the answer carries the image. Exactly as the
    # picture server's path next door does it, so the history shows both
    # kinds the same way and no second display path is needed.
    frage_id, antwort_id = _ins_gespraech(request, wunsch, name, sprache)
    return BildAntwort(
        bild=name, seed=auftrag.seed, frage_id=frage_id, antwort_id=antwort_id
    )


def _ins_gespraech(
    request: Request, wunsch: BildWunsch, name: str, sprache: str
) -> tuple[str | None, str | None]:
    if not wunsch.chat_id:
        return None, None
    from app.api.abhaengigkeiten import STANDARD_BENUTZER

    repositories = request.app.state.repositories
    benutzer = getattr(request.app.state, "standard_benutzer", STANDARD_BENUTZER)
    chat = repositories.chats.holen(wunsch.chat_id, user_id=benutzer)
    if chat is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, t("fehler.chat_nicht_gefunden", sprache)
        )
    frage = repositories.messages.speichern(
        chat_id=chat.id, role="user", content=wunsch.prompt
    )
    antwort = repositories.messages.speichern(
        chat_id=chat.id, role="assistant", content="", bild=name
    )
    repositories.chats.zeitstempel_auffrischen(chat.id)
    return frage.id, antwort.id


def _loras(config: Config, wunsch: BildWunsch, sprache: str) -> tuple[LoRA, ...]:
    """The stack, every name checked against the folder it must lie in."""
    gewaehlt = []
    for eintrag in wunsch.loras:
        try:
            lora_pfad(_bildordner(config), eintrag.name)
        except BildFehler as fehler:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, t(fehler.grund, sprache)
            ) from fehler
        gewaehlt.append(LoRA(name=eintrag.name, staerke=max(0.0, min(2.0, eintrag.staerke))))
    return tuple(gewaehlt)


def _startbild(config: Config, name: str | None, sprache: str) -> Path | None:
    """A picture to start from — by the name this server gave it.

    The same rule as a model name: only a bare name, and only one that is
    really lying in the picture folder. A path from a request never becomes
    a path on disk.
    """
    if not name:
        return None
    if "/" in name or "\\" in name or name != Path(name).name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("bild.startbild_fehlt", sprache))
    pfad = config.datenverzeichnis / "bilder" / name
    if not pfad.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("bild.startbild_fehlt", sprache))
    return pfad


def _speicher_pruefen(request: Request, modellpfad, sprache: str) -> None:
    """An honest sentence instead of a machine brought to its knees."""
    try:
        modell_gb = modellpfad.stat().st_size / (1024**3)
    except OSError:
        return
    # What the running servers are holding RIGHT NOW, not what their files
    # weigh: a server started with a small context holds less than one
    # started with a large one, and the file cannot tell them apart. All of
    # them, not just the chat model — see `bildspeicher` for why asking one
    # of several is worse than not asking at all.
    belegt = bildspeicher.gehaltene_gb(request.app.state)
    gesamt = systemspeicher.gesamt_gb()
    if bildspeicher.passt(gesamt, belegt, modell_gb):
        return
    raise HTTPException(
        status.HTTP_507_INSUFFICIENT_STORAGE,
        t("bild.kein_platz", sprache, gb=bildspeicher.fehlend_gb(gesamt, belegt, modell_gb)),
    )
