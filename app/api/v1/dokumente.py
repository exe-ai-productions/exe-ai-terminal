"""Document upload (phase 4.1).

The path is the same as for images: upload raw bytes BEFORE sending the
message. The difference: what gets stored is not the file but its
**extracted text** — the ``documents`` table has been ready for that since
phase 1 (``extracted_text``). The original bytes are not kept: only what
the model can read is needed (smallest solution).

Extraction means READING from the file — nothing is generated. PDFs are
read by pypdf (pure Python library, everything stays local); TXT and MD are
already text. Above the character limit the text is truncated, but never
silently: the ``gekuerzt`` flag travels all the way into the chat bubble.
"""

from __future__ import annotations

import io
from pathlib import PurePosixPath, PureWindowsPath

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.abhaengigkeiten import hole_repositories, hole_sprache
from app.db import Repositories
from app.i18n import t

router = APIRouter(tags=["dokumente"])

ERLAUBTE_ENDUNGEN = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
MAX_BYTES = 20 * 1024 * 1024
# Whatever goes beyond the limit is cut off — with a visible notice in the
# bubble (decision: truncate instead of reject). The limit protects the
# context window of the local models.
TEXT_GRENZE = 24_000


def _anzeigename(roh: str) -> str:
    """Only the file name, never a path — no matter which system it comes from."""
    name = PureWindowsPath(PurePosixPath(roh).name).name
    return name[:120] or "Dokument"


class DokumentMeta(BaseModel):
    id: str
    name: str
    typ: str  # "pdf" | "txt" | "md"
    seiten: int | None = None
    kb: int
    gekuerzt: bool


class DokumentHochgeladen(BaseModel):
    dokument: DokumentMeta


@router.post(
    "/documents",
    response_model=DokumentHochgeladen,
    status_code=status.HTTP_201_CREATED,
    summary="Dokument für eine Nachricht hochladen (rohe Bytes) und Text auslesen",
)
async def dokument_hochladen(
    chat_id: str,
    name: str,
    request: Request,
    repositories: Repositories = Depends(hole_repositories),
    sprache: str = Depends(hole_sprache),
) -> DokumentHochgeladen:
    # The switch in the config really counts (interface close-out C):
    # off means off, even if someone talks to the API directly.
    if not request.app.state.config.features.document_upload:
        raise HTTPException(status.HTTP_403_FORBIDDEN, t("fehler.funktion_aus", sprache))

    chat = repositories.chats.holen(chat_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.chat_nicht_gefunden", sprache))

    anzeigename = _anzeigename(name)
    endung = ("." + anzeigename.rsplit(".", 1)[-1].lower()) if "." in anzeigename else ""
    if endung not in ERLAUBTE_ENDUNGEN:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, t("fehler.dokument_typ", sprache)
        )

    daten = await request.body()
    if len(daten) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, t("fehler.dokument_zu_gross", sprache)
        )
    if not daten:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, t("fehler.dokument_typ", sprache))

    seiten: int | None = None
    if endung == ".pdf":
        try:
            from pypdf import PdfReader

            leser = PdfReader(io.BytesIO(daten))
            seiten = len(leser.pages)
            text = "\n\n".join((seite.extract_text() or "") for seite in leser.pages)
        except Exception as fehler:  # pypdf throws various things depending on the file
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                t("fehler.dokument_unlesbar", sprache),
            ) from fehler
    else:
        text = daten.decode("utf-8", errors="replace")

    text = text.strip()
    if not text:
        # A scan without a text layer, for example — reject honestly instead
        # of slipping the model an empty document.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, t("fehler.dokument_unlesbar", sprache)
        )

    gekuerzt = len(text) > TEXT_GRENZE
    if gekuerzt:
        text = text[:TEXT_GRENZE]

    dokument = repositories.documents.speichern(
        chat_id=chat.id,
        filename=anzeigename,
        mime_type=ERLAUBTE_ENDUNGEN[endung],
        size_bytes=len(daten),
        extracted_text=text,
        pages=seiten,
        truncated=gekuerzt,
    )
    return DokumentHochgeladen(dokument=meta_bauen(dokument))


def meta_bauen(dokument) -> DokumentMeta:
    """The meta card for the window — always built from the database row,
    never from client input. The message retrieval uses it too."""
    typen = {v: k for k, v in ERLAUBTE_ENDUNGEN.items()}
    endung = typen.get(dokument.mime_type or "", ".txt")
    return DokumentMeta(
        id=dokument.id,
        name=dokument.filename,
        typ=endung[1:],
        seiten=dokument.pages,
        kb=max(1, round((dokument.size_bytes or 0) / 1024)),
        gekuerzt=dokument.truncated,
    )
