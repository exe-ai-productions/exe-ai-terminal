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
import base64
import functools
import secrets
import threading
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_config, hole_repositories, hole_sprache
from app import bildvorgabenwahl
from app.bildmetadaten import metadaten_entfernen
from app.bildschutz import putzen_an
from app.bildturbo import Bildturbo, BildturboFehler
from app.bildrunner import (
    Auftrag, BildFehler, Bildrunner, LoRA, loras, lora_pfad, modelle, modell_pfad,
    vaes, vae_pfad, yolos, yolo_pfad,
)
from app import bildwahlen
from app import bildlauf, bildspeicher, systemspeicher
from pathlib import Path

from app.config import Config
from app.i18n import t
from app.ordner_oeffnen import OeffnenNichtMoeglich, ordner_oeffnen
from app.speicherorte import ort
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
    # The quality companions, all optional. -1 clip-skip means "let the class
    # decide"; an empty VAE/detector name means the pass is simply off. Names,
    # never paths — resolved against their own folders like a LoRA is.
    clip_skip: int = -1
    vae: str | None = None
    ad_modell: str | None = None
    ad_prompt: str = Field(default="", max_length=2000)
    # Highres fix: a second pass at a larger size for finer detail. Off by
    # default; the scale is how much larger.
    hires: bool = False
    hires_scale: float = Field(default=2.0, ge=1.0, le=4.0)


class BildAntwort(BaseModel):
    bild: str
    seed: int
    frage_id: str | None = None
    antwort_id: str | None = None


class BildmodellAntwort(BaseModel):
    modelle: list[str]
    loras: list[str] = Field(default_factory=list)
    vaes: list[str] = Field(default_factory=list)
    yolos: list[str] = Field(default_factory=list)
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
    return ort(config, "bildmodelle")


def _embd_ordner(config: Config) -> Path | None:
    """The embeddings folder, or nothing while it does not exist yet."""
    ordner = _bildordner(config) / bildwahlen.EMBEDDING_ORDNER
    return ordner if ordner.is_dir() else None


def _bilderziel(config: Config) -> Path:
    """Where a finished picture is written and read back from — one named
    location, so the folder is asked for and never spelled out."""
    return ort(config, "bilder")


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
        vaes=vaes(_bildordner(config)),
        yolos=yolos(_bildordner(config)),
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


# --- Image-Turbo: the optional persistent server ---------------------------


def _turbo(request: Request) -> Bildturbo:
    return request.app.state.bildturbo


class TurboAntwort(BaseModel):
    # aus (grey) | bereit (green) | zeichnet (blue) | fehler (red)
    zustand: str
    modell: str | None = None
    programm_da: bool


def _turbo_stand(turbo: Bildturbo) -> TurboAntwort:
    return TurboAntwort(
        zustand=turbo.zustand(), modell=turbo.modell,
        programm_da=turbo.programm is not None,
    )


@router.get("/bild/turbo", response_model=TurboAntwort, summary="Image-Turbo — Zustand")
def turbo_stand(request: Request) -> TurboAntwort:
    return _turbo_stand(_turbo(request))


class TurboStart(BaseModel):
    modell: str


@router.post("/bild/turbo/start", response_model=TurboAntwort, summary="Image-Turbo einschalten")
def turbo_starten(
    daten: TurboStart, request: Request,
    config: Config = Depends(hole_config), sprache: str = Depends(hole_sprache),
) -> TurboAntwort:
    turbo = _turbo(request)
    try:
        pfad = modell_pfad(_bildordner(config), daten.modell)
    except BildFehler as fehler:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t(fehler.grund, sprache)) from fehler
    try:
        # Switched on by hand on a bare Gespann — just the model, no VAE and no
        # detector yet. The LoRA folder is pointed at from the start, so a LoRA
        # picture works straight away without a restart; a request that later
        # wants a VAE or a detector restarts onto that Gespann on its own.
        turbo.starten(
            pfad,
            lora_ordner=_bildordner(config) / bildwahlen.LORA_ORDNER,
            embd_ordner=_embd_ordner(config),
        )
    except BildturboFehler as fehler:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED, t(fehler.grund, sprache)
        ) from fehler
    return _turbo_stand(turbo)


@router.post("/bild/turbo/stop", response_model=TurboAntwort, summary="Image-Turbo ausschalten")
def turbo_stoppen(request: Request) -> TurboAntwort:
    turbo = _turbo(request)
    turbo.stoppen()
    return _turbo_stand(turbo)


class BildVorgabenAntwort(BaseModel):
    breite: int
    hoehe: int
    schritte: int
    sampler: str = ""
    scheduler: str = ""
    klasse: str


@router.get("/bild/vorgaben", response_model=BildVorgabenAntwort, summary="Startwerte je Modell")
def bild_vorgaben(
    modell: str | None = None,
    repositories=Depends(hole_repositories),
) -> BildVorgabenAntwort:
    """The values the picture window opens on for a given model.

    Class-aware: an SDXL model comes back at 1024/28, an SD-1.5 at 512/22,
    and a stored override — global, per-model or per-chat — wins over the
    class default. The window asks again whenever the chosen model changes,
    so switching from an SD-1.5 to an SDXL model moves the fields with it
    instead of drawing the big model at the small model's resolution.
    """
    aufgeloest = bildvorgabenwahl.vorgaben(repositories, modell=modell)
    return BildVorgabenAntwort(
        breite=aufgeloest.get("breite", 512),
        hoehe=aufgeloest.get("hoehe", 512),
        schritte=aufgeloest.get("schritte", 22),
        sampler=aufgeloest.get("sampler", ""),
        scheduler=aufgeloest.get("scheduler", ""),
        klasse=bildwahlen.klasse_aus_name(modell or ""),
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


class FortschrittAntwort(BaseModel):
    """The running picture's honest step counter, for the filling frame.

    `laeuft` False means: nothing to show — the interface keeps its quiet
    wave without a number. The share is overall across the run's passes
    (base, highres, detailer), capped just under one until the file truly
    exists."""

    laeuft: bool
    anteil: float = 0.0
    schritt: int = 0
    gesamt: int = 0


@router.get("/bild/fortschritt", response_model=FortschrittAntwort, summary="Bildfortschritt")
def bild_fortschritt(request: Request) -> FortschrittAntwort:
    stand = _runner(request).fortschritt() or _turbo(request).fortschritt()
    if not stand:
        return FortschrittAntwort(laeuft=False)
    return FortschrittAntwort(laeuft=True, **stand)


@router.post("/bild/stop", response_model=bool, summary="Bild abbrechen")
def bild_stoppen(request: Request) -> bool:
    """Ends the running picture. False when there was none.

    No id and no body: one picture runs at a time, so there is exactly one
    thing this can mean. Both paths are reached: the sd-cli runner, and a
    turbo draw — which blocks in an HTTP call with no cancel, so ending its
    server is what breaks it off.
    """
    gestoppt = _runner(request).stoppen()
    return _turbo(request).abbrechen() or gestoppt


@router.post("/bild/begleiter-folder/{unterordner}", response_model=bool,
             summary="Begleiter-Ordner zeigen")
def begleiterordner_zeigen(
    unterordner: Literal["vae", "lora", "adetailer", "embedding"],
    config: Config = Depends(hole_config), sprache: str = Depends(hole_sprache),
) -> bool:
    """Open one of the picture server's companion sub-folders so a file can be
    dropped in by hand — a stack nobody can fill is not a stack, so the folder
    is created if it is not there yet. The whitelist on the path is what keeps
    this from opening anything but a companion folder."""
    ordner = _bildordner(config) / unterordner
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
        embd_ordner=_embd_ordner(config),
        startbild=startbild,
        maske=maske,
        # Without a starting image the strength has nothing to act on.
        staerke=max(0.0, min(1.0, float(wunsch.staerke))) if startbild else 1.0,
        # The quality companions, each resolved against its own folder.
        clip_skip=max(-1, min(12, int(wunsch.clip_skip))),
        vae=_begleiter(vae_pfad, config, wunsch.vae, sprache),
        ad_modell=_begleiter(yolo_pfad, config, wunsch.ad_modell, sprache),
        ad_prompt=wunsch.ad_prompt,
        hires=bool(wunsch.hires),
        hires_scale=max(1.0, min(4.0, float(wunsch.hires_scale))),
    )
    name = uuid.uuid4().hex + ".png"
    ziel = _bilderziel(config) / name

    # The run appears in the chat's little history the moment it starts, so a
    # picture that takes half a minute is visible as work rather than as
    # nothing happening.
    lauf = bildlauf.beginnen(wunsch.lauf_chat or wunsch.chat_id, wunsch.prompt)

    # The generator is a separate program that runs for half a minute; run
    # in a thread so the service keeps answering while it draws.
    #
    # Image-Turbo takes the picture whenever it is up. LoRA travels in the
    # prompt (the server is always started with the LoRA folder), VAE and
    # detector are the "Gespann" the server is started on; a request wanting a
    # different Gespann restarts the turbo ONCE with the new flags, so the load
    # is paid a single time and the whole series runs warm.
    #
    # A starting image, a mask, highres fix and clip-skip used to fall back to
    # sd-cli here, on the belief that this server had no per-request fields for
    # them. The pinned build does, and each was checked against the running
    # server: the picture really is used rather than swallowed, the mask is
    # read with the same polarity the rest of the program uses, highres reaches
    # the asked-for size, clip-skip changes the result, and a size that differs
    # from the starting picture is scaled exactly as sd-cli scales it.
    #
    # The rule behind the switch stands unchanged: whatever the turbo cannot
    # do goes to sd-cli. A control silently dropped is the worst outcome —
    # worse than slow.
    turbo = request.app.state.bildturbo
    ueber_turbo = turbo.laeuft()
    try:
        if ueber_turbo:
            # The turbo path borrows the runner's one-picture lock: a second
            # request cannot restart the server under a running draw, and a
            # turbo picture and an sd-cli picture can never run at once.
            runner.reservieren()
            try:
                if not turbo.passt_zu(
                    wunsch.modell, wunsch.vae or None,
                    wunsch.ad_modell or None, auftrag.ad_prompt,
                ):
                    # A different Gespann — bring the server up on it and wait
                    # for the model to load before the first draw. Both steps
                    # block, so they run off the event loop.
                    await asyncio.to_thread(
                        turbo.starten, pfad,
                        vae=auftrag.vae, ad_modell=auftrag.ad_modell,
                        ad_prompt=auftrag.ad_prompt, lora_ordner=auftrag.lora_ordner,
                        embd_ordner=auftrag.embd_ordner,
                    )
                    if not await asyncio.to_thread(turbo.bereit_abwarten):
                        raise BildturboFehler("bild.turbo_ladefehler")
                # A body carrying a starting picture belongs at the other
                # entrance; which one it is stays the caller's judgement.
                koerper = _turbo_auftrag(auftrag)
                daten = await asyncio.to_thread(
                    functools.partial(
                        turbo.zeichnen,
                        koerper,
                        weg="img2img" if "init_images" in koerper else "txt2img",
                        paesse=_erwartete_paesse(auftrag),
                    )
                )
                ziel.parent.mkdir(parents=True, exist_ok=True)
                ziel.write_bytes(daten)
            finally:
                runner.freigeben()
        else:
            await asyncio.to_thread(runner.erzeugen, auftrag, ziel)
    except BildturboFehler as fehler:
        if fehler.grund == "bild.abgebrochen":
            # A stop pressed during a turbo draw ends the server, which breaks
            # off the draw. Asked for, not gone wrong — the same silent 499 the
            # sd-cli path returns, so the window says nothing and the working
            # message just disappears.
            bildlauf.beenden(lauf, abgebrochen=True)
            code = (status.HTTP_499_CLIENT_CLOSED_REQUEST
                    if hasattr(status, "HTTP_499_CLIENT_CLOSED_REQUEST") else 499)
            raise HTTPException(code, t(fehler.grund, sprache)) from fehler
        bildlauf.beenden(lauf, gescheitert=True)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, t(fehler.grund, sprache)
        ) from fehler
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
        satz = t(schluessel, sprache)
        if getattr(fehler, "protokoll", None):
            # The painter's REAL last words, verbatim below the sentence —
            # no rewritten error catalogue, the raw log is the truth.
            satz = f"{satz}\n\n{fehler.protokoll}"
        raise HTTPException(code, satz) from fehler
    except BaseException:
        bildlauf.beenden(lauf, gescheitert=True)
        raise
    bildlauf.beenden(lauf)

    # The generator writes the prompt, seed and every setting into the file.
    # Stripped here, once the finished picture lies on disk, so both painters
    # pass the same gate and nothing but the pixels is stored or handed on.
    if putzen_an(request.app.state.repositories):
        ziel.write_bytes(metadaten_entfernen(ziel.read_bytes()))

    # Prompt and picture land in the chat as a message pair — the question
    # carries the prompt, the answer carries the image. Exactly as the
    # picture server's path next door does it, so the history shows both
    # kinds the same way and no second display path is needed.
    frage_id, antwort_id = _ins_gespraech(request, wunsch, name, sprache, auftrag.seed)
    return BildAntwort(
        bild=name, seed=auftrag.seed, frage_id=frage_id, antwort_id=antwort_id
    )


def _turbo_auftrag(auftrag: Auftrag) -> dict:
    """The A1111 body Image-Turbo speaks.

    The base fields, plus the LoRA stack written into the prompt in WebUI
    syntax — the same way sd-cli takes it (``<lora:name:strength>``), which
    the server resolves against the ``--lora-model-dir`` it was started with.
    VAE and detector are NOT here: they are bound to the running server as
    start flags, not per-request body fields.

    A starting image, a mask, highres and clip-skip DO travel this path. They
    were kept from it for a long time on the belief that the server had no
    fields for them; the build this program pins does, and each was checked
    against the running server before being opened up. The mask keeps the
    polarity the rest of the program uses — white means "draw this again" —
    because the server was measured to read it the same way, so no inversion
    flag is set.
    """
    prompt = auftrag.prompt
    for lora in auftrag.loras:
        prompt += f" <lora:{Path(lora.name).stem}:{lora.staerke}>"
    body = {
        "prompt": prompt,
        "width": auftrag.breite,
        "height": auftrag.hoehe,
        "steps": auftrag.schritte,
        "cfg_scale": auftrag.cfg,
        "seed": auftrag.seed,
        "sampler_name": auftrag.sampler,
    }
    if auftrag.negativ:
        body["negative_prompt"] = auftrag.negativ
    if auftrag.scheduler:
        body["scheduler"] = auftrag.scheduler
    if auftrag.startbild is not None:
        body["init_images"] = [_alsb64(auftrag.startbild)]
        body["denoising_strength"] = auftrag.staerke
        # Only ever alongside a starting image — the caller already dropped a
        # mask that arrived without one.
        if auftrag.maske is not None:
            body["mask"] = _alsb64(auftrag.maske)
    if auftrag.hires:
        body["enable_hr"] = True
        body["hr_scale"] = auftrag.hires_scale
    if auftrag.clip_skip > 0:
        body["clip_skip"] = auftrag.clip_skip
    return body


def _erwartete_paesse(auftrag: Auftrag) -> int:
    """How many painting passes this run takes: the base one, plus highres,
    plus the detailer's repaint.

    The same arithmetic the sd-cli runner does (see ``app/bildrunner.py``),
    and it has to stay the same: two paths that count differently would draw
    the same picture behind two different bars. WHOEVER CHANGES ONE READS
    THE OTHER.
    """
    return 1 + (1 if auftrag.hires else 0) + (1 if auftrag.ad_modell else 0)


def _alsb64(pfad: Path) -> str:
    """A picture on disk as the base64 the server takes. The bytes go from
    the file into the request and nowhere else — nothing about the picture
    is read, logged or kept."""
    return base64.b64encode(pfad.read_bytes()).decode()


def _ins_gespraech(
    request: Request, wunsch: BildWunsch, name: str, sprache: str, seed: int
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
    # The seed rides along in the message's stats (no schema change needed),
    # so every saved picture carries the number it was drawn with — shown
    # under the picture and copyable, exactly like the chat's own values.
    antwort = repositories.messages.speichern(
        chat_id=chat.id, role="assistant", content="", bild=name,
        stats={"seed": seed},
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


def _begleiter(aufloeser, config: Config, name: str | None, sprache: str) -> Path | None:
    """A VAE or detector NAME turned into a path, or None when unset — every
    name checked against the folder it must lie in, like a LoRA."""
    if not name:
        return None
    try:
        return aufloeser(_bildordner(config), name)
    except BildFehler as fehler:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, t(fehler.grund, sprache)
        ) from fehler


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
    pfad = _bilderziel(config) / name
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
