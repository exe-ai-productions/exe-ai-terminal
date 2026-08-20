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

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.bildmetadaten import metadaten_entfernen
from app.bildschutz import putzen_an
from app.config import Config
from app.i18n import t
from app.speicherorte import ort

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
    return ort(config, "bilder")


class BildAntwort(BaseModel):
    bild: str


class BilderListe(BaseModel):
    # The saved pictures, newest first — names only; the caller builds each
    # address with the existing /images/{name} route.
    bilder: list[str]


@router.get("/bilder", response_model=BilderListe, summary="Gespeicherte Bilder auflisten")
def bilder_auflisten(config: Config = Depends(hole_config)) -> BilderListe:
    """Every saved picture in the picture folder, newest first. A missing
    folder is not an error — it is the state before the first picture, and
    the answer is simply an empty list."""
    ordner = bilder_verzeichnis(config)
    if not ordner.is_dir():
        return BilderListe(bilder=[])
    # Skip anything too small to be a real picture: a stray file dropped into
    # the folder by hand would otherwise show as a broken tile. The smallest
    # valid PNG is around 67 bytes; 100 clears junk without touching a real
    # image, which is never that small.
    treffer = [
        p for p in ordner.iterdir()
        if p.is_file() and BILD_NAME_MUSTER.match(p.name) and p.stat().st_size >= 100
    ]
    treffer.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return BilderListe(bilder=[p.name for p in treffer])


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
    # An uploaded photo can carry EXIF — camera, time, place — and it would
    # travel to a cloud vision model untouched. Stripped here when the switch
    # is on, on the one path every upload takes to disk.
    if putzen_an(request.app.state.repositories):
        daten = metadaten_entfernen(daten)
    (verzeichnis / name).write_bytes(daten)
    return BildAntwort(bild=name)


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
