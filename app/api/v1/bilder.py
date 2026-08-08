"""Images for vision input.

An image is uploaded BEFORE the message is sent and then lives as a file
under ``data/bilder/`` — the message only carries the file name. The bytes
belong in the filesystem, not in the database, and not in the API's chat
history.

The upload accepts raw bytes with a Content-Type (no multipart — that would
mean an extra dependency for a single purpose). Allowed are the three
formats that all vision servers understand. The server assigns the names
itself — nothing from the client reaches the filesystem.
"""

from __future__ import annotations

import asyncio
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.config import Config
from app.i18n import t

router = APIRouter(tags=["bilder"])

ERLAUBTE_TYPEN = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
MAX_BYTES = 10 * 1024 * 1024

# Only names this server assigned itself — the barrier against path tricks,
# same approach as with the agent files.
BILD_NAME_MUSTER = re.compile(r"^[a-f0-9]{32}\.(png|jpg|webp)$")


def bilder_verzeichnis(config: Config):
    return config.datenverzeichnis / "bilder"


class BildAntwort(BaseModel):
    bild: str


@router.post(
    "/images",
    response_model=BildAntwort,
    status_code=status.HTTP_201_CREATED,
    summary="Bild für eine Nachricht hochladen (rohe Bytes)",
)
async def bild_hochladen(
    request: Request,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> BildAntwort:
    typ = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if typ not in ERLAUBTE_TYPEN:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, t("fehler.bild_typ", sprache)
        )
    daten = await request.body()
    if len(daten) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, t("fehler.bild_zu_gross", sprache)
        )
    if not daten:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, t("fehler.bild_typ", sprache))

    name = uuid.uuid4().hex + ERLAUBTE_TYPEN[typ]
    verzeichnis = bilder_verzeichnis(config)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    (verzeichnis / name).write_bytes(daten)
    return BildAntwort(bild=name)



class BildEndpunktAntwort(BaseModel):
    id: str
    dialect: str
    erreichbar: bool


class BildKonfiguration(BaseModel):
    content: str
    kaputt: str | None


@router.get(
    "/images/endpoints",
    response_model=list[BildEndpunktAntwort],
    summary="Konfigurierte Bild-Generatoren samt Erreichbarkeit",
)
async def bild_endpunkte(config: Config = Depends(hole_config)) -> list[BildEndpunktAntwort]:
    """Checked fresh on every call — image mode asks rarely, and the answer
    should be honest, not a minute old."""
    from app.bildgeneratoren import generatoren

    antworten = []
    for generator in generatoren(config):
        antworten.append(
            BildEndpunktAntwort(
                id=generator.id,
                dialect=generator.dialect,
                erreichbar=await generator.erreichbar(),
            )
        )
    return antworten


class BildErzeugen(BaseModel):
    chat_id: str
    prompt: str
    endpoint_id: str | None = None
    # Assigned by the client so it can stop this very generation —
    # after all, the response only arrives once everything is over.
    generation_id: str | None = None


class BildErzeugtAntwort(BaseModel):
    """With `abgebrochen` the remaining fields are empty — there is no image
    and nothing was saved; the chat remains untouched."""

    frage_id: str | None = None
    antwort_id: str | None = None
    bild: str | None = None
    dialekt: str | None = None
    abgebrochen: bool = False


# Running generations, for the stop button: generation_id -> stop event.
# In memory is enough — a generation doesn't survive the process anyway.
_laufende: dict[str, "asyncio.Event"] = {}


class BildStoppen(BaseModel):
    generation_id: str


@router.post(
    "/images/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    summary="Eine laufende Bild-Erzeugung stoppen",
)
def bild_stoppen(daten: BildStoppen, sprache: str = Depends(hole_sprache)) -> Response:
    ereignis = _laufende.get(daten.generation_id)
    if ereignis is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, t("fehler.bilderzeugung_fehlt", sprache)
        )
    ereignis.set()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/images/generate",
    response_model=BildErzeugtAntwort,
    summary="Bild erzeugen (Bildmodus) — roher Prompt an den Generator",
)
async def bild_erzeugen(
    daten: BildErzeugen,
    request: Request,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> BildErzeugtAntwort:
    """Runs synchronously — a generation takes a while, the caller waits along.

    Prompt and image end up in the chat as a message pair: the question
    carries the raw prompt, the answer carries the image — the history shows
    both like any other exchange, without a separate display path.
    """
    from app.api.abhaengigkeiten import STANDARD_BENUTZER, hole_repositories
    from app.bildgeneratoren import BildAbbruch, BildFehler, generatoren

    # The switch in the config really counts (interface close-out C):
    # off means off, even if someone talks to the API directly.
    if not config.features.image_generation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, t("fehler.funktion_aus", sprache))

    repositories = request.app.state.repositories
    benutzer = getattr(request.app.state, "standard_benutzer", STANDARD_BENUTZER)
    chat = repositories.chats.holen(daten.chat_id, user_id=benutzer)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.chat_nicht_gefunden", sprache))

    kandidaten = generatoren(config)
    if daten.endpoint_id:
        kandidaten = [g for g in kandidaten if g.id == daten.endpoint_id]
    generator = None
    for kandidat in kandidaten:
        if await kandidat.erreichbar():
            generator = kandidat
            break
    if generator is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, t("fehler.bildserver_fehlt", sprache)
        )

    stopp = asyncio.Event()
    schluessel = daten.generation_id or uuid.uuid4().hex
    _laufende[schluessel] = stopp
    try:
        ergebnis = await generator.erzeugen(daten.prompt, stopp=stopp)
    except BildAbbruch:
        return BildErzeugtAntwort(abgebrochen=True)
    except BildFehler as fehler:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(fehler)) from fehler
    finally:
        _laufende.pop(schluessel, None)

    name = uuid.uuid4().hex + ergebnis.endung
    verzeichnis = bilder_verzeichnis(config)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    (verzeichnis / name).write_bytes(ergebnis.daten)

    frage = repositories.messages.speichern(
        chat_id=chat.id, role="user", content=daten.prompt
    )
    antwort = repositories.messages.speichern(
        chat_id=chat.id, role="assistant", content="", bild=name
    )
    repositories.chats.zeitstempel_auffrischen(chat.id)
    return BildErzeugtAntwort(
        frage_id=frage.id, antwort_id=antwort.id, bild=name, dialect=generator.dialect
    )


@router.get("/images/{name}", summary="Ein hochgeladenes Bild ausliefern")
def bild_holen(
    name: str,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> FileResponse:
    if not BILD_NAME_MUSTER.match(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.bild_fehlt", sprache))
    datei = bilder_verzeichnis(config) / name
    if not datei.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.bild_fehlt", sprache))
    endung = datei.suffix
    medientyp = {v: k for k, v in ERLAUBTE_TYPEN.items()}[endung]
    return FileResponse(datei, media_type=medientyp)
